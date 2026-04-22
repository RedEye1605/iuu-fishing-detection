"""
Phase 7: Model Data Preparation

Transforms pipeline output into model-ready tensors:
1. Encode categorical features (vessel_flag, reg_vessel_class)
2. Build node feature matrix (all numeric, no NaN)
3. Build PyG-compatible temporal graph dataset
4. Compute class weights for imbalanced labels
5. Save everything for direct model consumption

Design decisions based on data characteristics:
- vessel_flag (127 unique): Frequency encoding → captures how common a flag is
  (proxy for regulatory oversight — rare flags may correlate with IUU)
- reg_vessel_class (16 unique): Label encoding + embedding lookup table
  (ordinal relationship doesn't exist between vessel types)
- Class weights: Inverse frequency weighted (hard_iuu 3.6x, normal 1.6x)
- Edge type: Binary (0=encounter, 1=colocation), 12%/88% ratio

Output:
  data/processed/model/
  ├── node_features.npy          # (N, F) float32 node feature matrix
  ├── node_labels.npy            # (N,) int64 vessel-level labels
  ├── feature_names.json         # Feature column names (ordered)
  ├── encoders.pkl               # LabelEncoder + frequency maps
  ├── class_weights.npy           # (4,) float32 class weights
  ├── edge_type_weights.npy       # (2,) float32 edge type weights
  ├── vessel_flag_embed.npy       # (127, 8) flag embedding init
  ├── vessel_class_embed.npy      # (16, 8) class embedding init
  ├── mmsi_index.json             # MMSI → index mapping
  └── snapshots/
      ├── {split}/
      │   ├── edge_index.npy      # (2, E) int64 per snapshot
      │   ├── edge_type.npy       # (E,) int64 per snapshot
      │   ├── vessel_indices.npy  # (V,) int64 per snapshot
      │   └── labels.npy          # (V,) int64 per snapshot
      └── snapshot_order.json     # Ordered list of snapshot IDs per split

Functions:
- encode_categorical_features: Frequency/label encoding
- build_model_node_features: Final feature matrix
- build_pyg_snapshots: Snapshot tensors per split
- compute_training_weights: Class + edge type weights
- run_prepare_all: Full preparation pipeline
"""

from __future__ import annotations

import json
import logging
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

from ..constants import PROCESSED_DIR

logger = logging.getLogger(__name__)
INPUT = PROCESSED_DIR
OUTPUT = PROCESSED_DIR / "model"


def encode_categorical_features(nodes: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Encode categorical columns for model input.

    Strategy:
    - vessel_flag: Frequency encoding (captures regulatory oversight proxy)
    - reg_vessel_class: Label encoding (for embedding lookup)
    - mmsi: Dropped (model uses positional index)

    Args:
        nodes: Node features DataFrame.

    Returns:
        Tuple of (encoded DataFrame, encoder metadata dict).
    """
    logger.info("--- Encoding Categorical Features ---")
    encoders = {}

    # vessel_flag → frequency encoding
    flag_counts = nodes["vessel_flag"].value_counts()
    flag_freq = (flag_counts / len(nodes)).to_dict()
    # Unknown flags get frequency 0
    encoders["vessel_flag_freq"] = flag_freq
    nodes["vessel_flag_freq"] = nodes["vessel_flag"].map(flag_freq).fillna(0).astype(np.float32)
    logger.info(f"  vessel_flag → freq encoding ({len(flag_freq)} flags)")

    # vessel_flag → also label encode for embedding
    flag_le = LabelEncoder()
    flag_le.fit(nodes["vessel_flag"].fillna("UNKNOWN"))
    nodes["vessel_flag_code"] = flag_le.transform(nodes["vessel_flag"].fillna("UNKNOWN")).astype(np.int32)
    encoders["vessel_flag_encoder"] = {
        "classes": flag_le.classes_.tolist(),
        "n_classes": len(flag_le.classes_),
    }
    logger.info(f"  vessel_flag → label encoding ({len(flag_le.classes_)} classes)")

    # reg_vessel_class → label encoding
    class_le = LabelEncoder()
    nodes["reg_vessel_class_filled"] = nodes["reg_vessel_class"].fillna("unknown")
    class_le.fit(nodes["reg_vessel_class_filled"])
    nodes["vessel_class_code"] = class_le.transform(nodes["reg_vessel_class_filled"]).astype(np.int32)
    encoders["vessel_class_encoder"] = {
        "classes": class_le.classes_.tolist(),
        "n_classes": len(class_le.classes_),
    }
    logger.info(f"  reg_vessel_class → label encoding ({len(class_le.classes_)} classes)")

    # Drop original categorical columns + temp
    nodes = nodes.drop(columns=["mmsi", "vessel_flag", "reg_vessel_class", "reg_vessel_class_filled"], errors="ignore")

    return nodes, encoders


def compute_training_weights(labels: np.ndarray) -> dict:
    """Compute class and edge type weights for balanced training.

    Args:
        labels: Vessel-level label array.

    Returns:
        Dict with 'class_weights' and 'class_counts'.
    """
    logger.info("--- Computing Training Weights ---")

    unique, counts = np.unique(labels, return_counts=True)
    total = len(labels)
    n_classes = len(unique)

    # Inverse frequency weighting: w_c = N / (C * n_c)
    weights = total / (n_classes * counts.astype(np.float32))

    result = {
        "class_weights": weights.tolist(),
        "class_counts": counts.tolist(),
        "total": total,
    }

    logger.info(f"  Class weights: {dict(zip(unique.tolist(), [round(w, 3) for w in weights]))}")
    logger.info(f"  Class counts: {dict(zip(unique.tolist(), counts.tolist()))}")

    return result


def build_embedding_init(n_classes: int, dim: int = 8) -> np.ndarray:
    """Xavier uniform initialization for embedding tables.

    Args:
        n_classes: Number of categories.
        dim: Embedding dimension.

    Returns:
        (n_classes, dim) float32 array.
    """
    scale = np.sqrt(6.0 / (n_classes + dim))
    return np.random.uniform(-scale, scale, (n_classes, dim)).astype(np.float32)


def build_pyg_snapshots(
    split_assignment: dict,
    snapshots: dict,
    n_total_nodes: int,
) -> dict:
    """Build PyG-compatible snapshot tensors for each split.

    Each snapshot contains:
    - vessel_indices: Global node indices for this snapshot's vessels
    - edge_index: [2, E] edge connections (snapshot-local indices)
    - edge_type: [E] binary (0=encounter, 1=colocation)
    - labels: [V] vessel labels for this snapshot

    Args:
        split_assignment: Dict with train/val/test week lists.
        snapshots: Full snapshot data.
        n_total_nodes: Total number of vessel nodes.

    Returns:
        Dict with per-split snapshot data.
    """
    logger.info("--- Building PyG Snapshot Tensors ---")

    result = {}
    for split_name, weeks in split_assignment.items():
        split_dir = OUTPUT / "snapshots"
        split_dir.mkdir(parents=True, exist_ok=True)

        snapshot_order = []
        all_data = {}

        for week in weeks:
            if week not in snapshots:
                continue
            snap = snapshots[week]

            vessel_indices = np.array(snap["vessel_indices"], dtype=np.int64)
            labels = np.array(snap["labels"], dtype=np.int64)

            if snap["n_edges"] > 0:
                src = np.array(snap["src"], dtype=np.int64)
                dst = np.array(snap["dst"], dtype=np.int64)
                edge_types = np.array(
                    [0 if t == "encounter" else 1 for t in snap["edge_types"]],
                    dtype=np.int64,
                )
                edge_index = np.stack([src, dst], axis=0)
            else:
                edge_index = np.zeros((2, 0), dtype=np.int64)
                edge_types = np.zeros(0, dtype=np.int64)

            all_data[week] = {
                "vessel_indices": vessel_indices,
                "edge_index": edge_index,
                "edge_type": edge_types,
                "labels": labels,
            }
            snapshot_order.append(week)

        # Save as single pickle per split (much cleaner than 1000+ npy files)
        out_path = split_dir / f"{split_name}_snapshots.pkl"
        with open(out_path, "wb") as f:
            pickle.dump({"order": snapshot_order, "data": all_data}, f, protocol=4)

        total_edges = sum(d["edge_index"].shape[1] for d in all_data.values())
        logger.info(f"  {split_name.upper()}: {len(snapshot_order)} snapshots, "
                     f"{total_edges:,} edges → {out_path.name}")
        result[split_name] = {
            "n_snapshots": len(snapshot_order),
            "total_edges": total_edges,
            "path": str(out_path),
        }

    return result


def run_prepare_all() -> dict:
    """Run full model data preparation pipeline.

    Returns:
        Dict with paths to all output files.
    """
    OUTPUT.mkdir(parents=True, exist_ok=True)

    # Load pipeline outputs
    logger.info("Loading pipeline outputs...")
    nodes = pd.read_parquet(INPUT / "vessel_node_features.parquet")
    logger.info(f"  Nodes: {nodes.shape}")

    with open(INPUT / "graph_snapshots.pkl", "rb") as f:
        snapshots = pickle.load(f)
    logger.info(f"  Snapshots: {len(snapshots)}")

    with open(INPUT / "split" / "snapshot_split.json") as f:
        split_assignment = json.load(f)

    # Save MMSI → index mapping
    mmsi_list = nodes["mmsi"].tolist()
    mmsi_index = {m: i for i, m in enumerate(mmsi_list)}
    with open(OUTPUT / "mmsi_index.json", "w") as f:
        json.dump(mmsi_index, f)
    logger.info("  ✅ MMSI index saved")

    # Step 1: Encode categorical features
    nodes, encoders = encode_categorical_features(nodes)

    # Step 2: Build feature matrix
    label_col = "vessel_iuu_label"
    # Drop non-numeric columns that survived encoding
    drop_cols = [label_col, "first_seen", "last_seen"]
    labels = nodes[label_col].values.astype(np.int64)
    features = nodes.drop(columns=[c for c in drop_cols if c in nodes.columns]).values.astype(np.float32)

    feature_names = nodes.drop(columns=[c for c in drop_cols if c in nodes.columns]).columns.tolist()

    np.save(OUTPUT / "node_features.npy", features)
    np.save(OUTPUT / "node_labels.npy", labels)
    with open(OUTPUT / "feature_names.json", "w") as f:
        json.dump(feature_names, f)

    logger.info(f"  ✅ Feature matrix: {features.shape} ({features.dtype})")
    logger.info(f"     NaN: {np.isnan(features).sum()}, Inf: {np.isinf(features).sum()}")
    logger.info(f"     Features: {feature_names}")

    # Step 3: Compute class weights
    weight_info = compute_training_weights(labels)
    class_weights = np.array(weight_info["class_weights"], dtype=np.float32)
    np.save(OUTPUT / "class_weights.npy", class_weights)
    logger.info(f"  ✅ Class weights saved: {class_weights}")

    # Step 4: Build embedding initialization tables
    flag_enc = encoders["vessel_flag_encoder"]
    class_enc = encoders["vessel_class_encoder"]

    flag_embed = build_embedding_init(flag_enc["n_classes"], dim=8)
    class_embed = build_embedding_init(class_enc["n_classes"], dim=8)
    np.save(OUTPUT / "vessel_flag_embed.npy", flag_embed)
    np.save(OUTPUT / "vessel_class_embed.npy", class_embed)
    logger.info(f"  ✅ Embedding init: flag ({flag_embed.shape}), class ({class_embed.shape})")

    # Step 5: Save encoders
    with open(OUTPUT / "encoders.pkl", "wb") as f:
        pickle.dump(encoders, f)
    logger.info("  ✅ Encoders saved")

    # Step 6: Build PyG snapshot tensors
    snap_results = build_pyg_snapshots(split_assignment, snapshots, len(nodes))

    # Step 7: Validation
    logger.info("--- Validation ---")
    assert not np.isnan(features).any(), "NaN in features!"
    assert not np.isinf(features).any(), "Inf in features!"
    assert labels.min() >= 0 and labels.max() <= 3, f"Labels out of range: [{labels.min()}, {labels.max()}]"
    assert features.shape[0] == labels.shape[0] == 14857
    logger.info(f"  ✅ {features.shape[0]} nodes × {features.shape[1]} features")
    logger.info(f"  ✅ Labels ∈ [0, 3]")
    logger.info(f"  ✅ No NaN, No Inf")

    logger.info("✅ Model data preparation complete")
    return {
        "features": str(OUTPUT / "node_features.npy"),
        "labels": str(OUTPUT / "node_labels.npy"),
        "snapshots": snap_results,
    }
