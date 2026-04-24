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
  ├── vessel_flag_embed.npy       # (121, 8) flag embedding init
  ├── vessel_class_embed.npy      # (17, 8) class embedding init
  ├── vessel_flag_indices.npy     # (N,) int64 flag embedding indices
  ├── vessel_class_indices.npy    # (N,) int64 class embedding indices
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


def compute_training_weights(split_assignment: dict, snapshots: dict) -> dict:
    """Compute class weights from per-snapshot training labels.

    Uses snapshot-level label distribution from training split (not vessel-level)
    because the model trains on per-snapshot vessel labels.

    Args:
        split_assignment: Dict with train/val/test week lists.
        snapshots: Full graph snapshot data.

    Returns:
        Dict with 'class_weights' and 'class_counts'.
    """
    logger.info("--- Computing Training Weights (snapshot-level) ---")

    # Collect all per-snapshot labels from training split
    train_weeks = set(split_assignment["train"])
    all_labels = []
    for week, data in snapshots.items():
        if week in train_weeks:
            all_labels.extend(data["labels"])

    labels = np.array(all_labels, dtype=np.int64)
    unique, counts = np.unique(labels, return_counts=True)
    total = len(labels)
    n_classes = 4  # Always 4 classes for stable weights

    # Inverse frequency weighting: w_c = N / (C * n_c)
    # Use full 4-class range even if some classes have 0 count in a split
    weight_arr = np.ones(n_classes, dtype=np.float32)
    for cls, cnt in zip(unique.tolist(), counts.tolist()):
        if cls < n_classes:
            weight_arr[cls] = total / (n_classes * cnt)

    # Cap extreme weights (probable_iuu can be very rare at vessel level)
    weight_arr = np.clip(weight_arr, 0.1, 10.0)

    # Normalize so weights sum to n_classes (keeps loss scale consistent)
    weight_arr = weight_arr / weight_arr.sum() * n_classes

    label_map = {0: "normal", 1: "suspicious", 2: "probable_iuu", 3: "hard_iuu"}
    logger.info(f"  Snapshot-level label counts (train): {total:,} total")
    for cls in range(n_classes):
        cnt = counts[unique == cls][0] if cls in unique else 0
        logger.info(f"    {label_map[cls]:15s}: {cnt:>8,} ({cnt/total*100:5.1f}%), weight={weight_arr[cls]:.3f}")

    result = {
        "class_weights": weight_arr.tolist(),
        "class_counts": counts.tolist(),
        "total": total,
    }

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
                # Edge attributes: [duration_hours, distance_km]
                edge_durations = np.array(snap.get("edge_durations", [0]*len(src)), dtype=np.float32)
                edge_distances = np.array(snap.get("edge_distances", [0]*len(src)), dtype=np.float32)
                edge_attr = np.stack([edge_durations, edge_distances], axis=-1)
            else:
                edge_index = np.zeros((2, 0), dtype=np.int64)
                edge_types = np.zeros(0, dtype=np.int64)
                edge_attr = np.zeros((0, 2), dtype=np.float32)

            all_data[week] = {
                "vessel_indices": vessel_indices,
                "edge_index": edge_index,
                "edge_type": edge_types,
                "labels": labels,
                "edge_attr": edge_attr,
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

    # Step 2: Build feature matrix — separate embedding indices from continuous features
    label_col = "vessel_iuu_label"
    # Embedding indices: used for lookup tables, NOT as continuous features
    embed_cols = {"vessel_flag_code", "vessel_class_code"}
    # Non-feature columns to drop
    drop_cols = {label_col, "first_seen", "last_seen"}

    labels = nodes[label_col].values.astype(np.int64)

    # Extract embedding indices separately
    if "vessel_flag_code" in nodes.columns:
        flag_indices = nodes["vessel_flag_code"].values.astype(np.int64)
        np.save(OUTPUT / "vessel_flag_indices.npy", flag_indices)
        logger.info(f"  ✅ Flag indices saved: {flag_indices.shape} (range 0-{flag_indices.max()})")
    if "vessel_class_code" in nodes.columns:
        class_indices = nodes["vessel_class_code"].values.astype(np.int64)
        np.save(OUTPUT / "vessel_class_indices.npy", class_indices)
        logger.info(f"  ✅ Class indices saved: {class_indices.shape} (range 0-{class_indices.max()})")

    # Continuous feature matrix (exclude embedding indices + non-features)
    all_drop = drop_cols | embed_cols
    feature_cols = [c for c in nodes.columns if c not in all_drop]
    features_df = nodes[feature_cols].copy()

    # Impute remaining NaN (vessels without flag → is_domestic=0, etc.)
    nan_per_col = features_df.isnull().sum()
    nan_cols = nan_per_col[nan_per_col > 0]
    if len(nan_cols):
        logger.info(f"  Final NaN imputation for {len(nan_cols)} columns:")
        for col, n in nan_cols.items():
            default = 0 if col != "is_domestic" else 0
            logger.info(f"    {col}: {n:,} NaN → {default}")
            features_df[col] = features_df[col].fillna(default)

    features = features_df.values.astype(np.float32)

    with open(OUTPUT / "feature_names.json", "w") as f:
        json.dump(feature_cols, f)

    np.save(OUTPUT / "node_features.npy", features)
    np.save(OUTPUT / "node_labels.npy", labels)

    logger.info(f"  ✅ Feature matrix: {features.shape} ({features.dtype})")
    logger.info(f"     NaN: {np.isnan(features).sum()}, Inf: {np.isinf(features).sum()}")
    logger.info(f"     Continuous features ({len(feature_cols)}): {feature_cols}")
    logger.info(f"     Embedding indices (separate): {sorted(embed_cols & set(nodes.columns))}")

    # Step 3: Compute class weights from training snapshot labels
    weight_info = compute_training_weights(split_assignment, snapshots)
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
    assert features.shape[0] == labels.shape[0]
    logger.info(f"  ✅ {features.shape[0]} nodes × {features.shape[1]} continuous features")
    logger.info(f"  ✅ Labels ∈ [0, 3]")
    logger.info(f"  ✅ No NaN, No Inf")

    logger.info("✅ Model data preparation complete")
    return {
        "features": str(OUTPUT / "node_features.npy"),
        "labels": str(OUTPUT / "node_labels.npy"),
        "snapshots": snap_results,
    }
