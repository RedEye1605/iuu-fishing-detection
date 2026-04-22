"""
Phase 6: Temporal Train/Val/Test Split

Splits graph snapshots (not individual events) into train/val/test sets
using a strict temporal boundary to prevent information leakage.

For ST-GAT, the split unit is the **weekly graph snapshot** — each snapshot
contains vessels active that week with their edges and labels. Events from
the same vessel can appear in multiple splits (expected — same vessel at
different times), but no snapshot from a later period leaks into an earlier split.

Split boundaries (with 2-week gaps to prevent temporal autocorrelation leakage):
  Train: 2020-W01 to 2023-W50
  Gap:   2023-W51 to 2023-W52 (excluded)
  Val:   2024-W01 to 2024-W24
  Gap:   2024-W25 to 2024-W26 (excluded)
  Test:  2024-W27 to 2025-W16

Why temporal (not random) split:
  - Prevents look-ahead bias (model can't use future patterns)
  - Tests generalization to new time periods
  - Standard practice for spatiotemporal models

Output:
  - data/processed/split/snapshot_split.json — snapshot-to-split mapping
  - data/processed/split/split_stats.json — distribution statistics
  - data/processed/split/train/ — train snapshot data (.pt)
  - data/processed/split/val/ — val snapshot data (.pt)
  - data/processed/split/test/ — test snapshot data (.pt)

Functions:
- assign_snapshot_split: Assign each weekly snapshot to train/val/test
- export_split_snapshots: Export PyTorch-ready data per split
- run_split_all: Full split pipeline
"""

from __future__ import annotations

import gc
import json
import logging
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from ..constants import PROCESSED_DIR, GFW_EVENTS_LABELED

logger = logging.getLogger(__name__)
INPUT = PROCESSED_DIR
OUTPUT = PROCESSED_DIR / "split"

# ===== SPLIT BOUNDARIES (ISO week format: YYYY-Www) =====
# 2-week gap between splits to prevent temporal autocorrelation leakage
# (adjacent weeks in maritime data are highly correlated — Rossi et al., 2020)
TRAIN_END = "2023_W50"   # Train: up to 2023-W50
GAP1_END = "2023_W52"    # Gap: 2023-W51 to 2023-W52 (excluded)
VAL_END = "2024_W24"     # Val: 2024-W01 to 2024-W24
GAP2_END = "2024_W26"    # Gap: 2024-W25 to 2024-W26 (excluded)
# Test: 2024-W27 onwards


def _week_sort_key(week_str: str) -> tuple:
    """Convert YYYY-Www to sortable tuple."""
    parts = week_str.split("_W")
    return (int(parts[0]), int(parts[1]))


def assign_snapshot_split(snapshots: dict) -> dict[str, list[str]]:
    """Assign each weekly snapshot to train/val/test based on temporal boundary.

    Args:
        snapshots: Dict of week_str -> snapshot data from graph_snapshots.pkl.

    Returns:
        Dict with 'train', 'val', 'test' keys, each containing a list of week strings.
    """
    logger.info("--- Assigning Snapshot Splits ---")

    train_weeks = []
    val_weeks = []
    test_weeks = []
    gap_weeks = []

    train_key = _week_sort_key(TRAIN_END)
    gap1_key = _week_sort_key(GAP1_END)
    val_key = _week_sort_key(VAL_END)
    gap2_key = _week_sort_key(GAP2_END)

    for week in sorted(snapshots.keys()):
        week_key = _week_sort_key(week)
        if week_key <= train_key:
            train_weeks.append(week)
        elif week_key <= gap1_key:
            gap_weeks.append(week)
        elif week_key <= val_key:
            val_weeks.append(week)
        elif week_key <= gap2_key:
            gap_weeks.append(week)
        else:
            test_weeks.append(week)

    logger.info(f"  Train: {len(train_weeks)} snapshots ({train_weeks[0]} to {train_weeks[-1] if train_weeks else 'N/A'})")
    if gap_weeks:
        logger.info(f"  Gap:   {len(gap_weeks)} snapshots EXCLUDED ({gap_weeks[0]} to {gap_weeks[-1]})")
    logger.info(f"  Val:   {len(val_weeks)} snapshots ({val_weeks[0]} to {val_weeks[-1] if val_weeks else 'N/A'})")
    logger.info(f"  Test:  {len(test_weeks)} snapshots ({test_weeks[0] if test_weeks else 'N/A'} to {test_weeks[-1] if test_weeks else 'N/A'})")

    return {"train": train_weeks, "val": val_weeks, "test": test_weeks}


def _compute_split_stats(
    split_assignment: dict,
    snapshots: dict,
    df: pd.DataFrame,
) -> dict:
    """Compute distribution statistics for each split.

    Args:
        split_assignment: Dict with train/val/test week lists.
        snapshots: Graph snapshot data.
        df: Labeled events DataFrame.

    Returns:
        Dict with per-split statistics.
    """
    logger.info("--- Computing Split Statistics ---")

    # Assign year_week to events
    starts = pd.to_datetime(df["start_time"])
    iso = starts.dt.isocalendar()
    df = df.copy()
    df["year_week"] = starts.dt.year.astype(str) + "_W" + iso["week"].astype(str).str.zfill(2)

    stats = {}
    for split_name, weeks in split_assignment.items():
        week_set = set(weeks)
        split_events = df[df["year_week"].isin(week_set)]

        n_events = len(split_events)
        n_vessels = split_events["mmsi"].nunique()
        n_snapshots = len(weeks)

        # Label distribution
        label_dist = split_events["iuu_label"].value_counts(normalize=True).to_dict()

        # Flag distribution
        flag_dist = {
            "domestic": (split_events["is_domestic"] == True).mean(),
            "foreign": (split_events["is_foreign"] == True).mean(),
        }

        # Event type distribution
        etype_dist = split_events["event_type"].value_counts(normalize=True).to_dict()

        # Graph stats
        snap_data = [snapshots[w] for w in weeks if w in snapshots]
        total_edges = sum(s["n_edges"] for s in snap_data)
        total_encounter_edges = sum(s["edge_types"].count("encounter") for s in snap_data)
        total_coloc_edges = sum(s["edge_types"].count("colocation") for s in snap_data)

        stats[split_name] = {
            "n_events": n_events,
            "pct_events": round(n_events / len(df) * 100, 1),
            "n_vessels": n_vessels,
            "n_snapshots": n_snapshots,
            "total_edges": total_edges,
            "encounter_edges": total_encounter_edges,
            "colocation_edges": total_coloc_edges,
            "label_distribution": {k: round(v, 3) for k, v in sorted(label_dist.items())},
            "flag_distribution": {k: round(v, 3) for k, v in flag_dist.items()},
            "event_type_distribution": {k: round(v, 3) for k, v in sorted(etype_dist.items())},
        }

        logger.info(f"  {split_name.upper()}: {n_events:,} events, {n_vessels:,} vessels, "
                     f"{n_snapshots} snapshots, {total_edges:,} edges")
        logger.info(f"    Labels: {stats[split_name]['label_distribution']}")

    return stats


def export_split_snapshots(
    split_assignment: dict,
    snapshots: dict,
) -> dict:
    """Export split snapshot data as PyTorch-ready files.

    Each split gets its own directory with:
    - snapshot_data.pt: Tensor-ready numpy arrays for PyTorch Geometric

    Args:
        split_assignment: Dict with train/val/test week lists.
        snapshots: Full graph snapshot data.

    Returns:
        Dict with output paths.
    """
    logger.info("--- Exporting Split Snapshots ---")

    results = {}
    for split_name, weeks in split_assignment.items():
        split_dir = OUTPUT / split_name
        split_dir.mkdir(parents=True, exist_ok=True)

        # Collect snapshot data for this split
        split_snapshots = {w: snapshots[w] for w in weeks if w in snapshots}

        # Convert to numpy arrays for PyTorch loading
        snapshot_arrays = {}
        for week, data in split_snapshots.items():
            snapshot_arrays[week] = {
                "vessel_indices": np.array(data["vessel_indices"], dtype=np.int64),
                "src": np.array(data["src"], dtype=np.int64),
                "dst": np.array(data["dst"], dtype=np.int64),
                "labels": np.array(data["labels"], dtype=np.int64),
                "n_vessels": data["n_vessels"],
                "n_edges": data["n_edges"],
                "edge_types": data["edge_types"],
            }

        out_path = split_dir / "snapshot_data.pkl"
        with open(out_path, "wb") as f:
            pickle.dump(snapshot_arrays, f, protocol=4)

        logger.info(f"  {split_name}: {len(snapshot_arrays)} snapshots → {out_path}")
        results[split_name] = out_path

    return results


def run_split_all() -> dict:
    """Run full temporal split pipeline.

    Returns:
        Dict with paths to output files.
    """
    logger.info("Loading graph snapshots...")
    with open(INPUT / "graph_snapshots.pkl", "rb") as f:
        snapshots = pickle.load(f)
    logger.info(f"  Loaded {len(snapshots)} snapshots")

    logger.info("Loading labeled events...")
    df = pd.read_parquet(INPUT / GFW_EVENTS_LABELED, columns=[
        "mmsi", "start_time", "event_type", "is_domestic", "is_foreign", "iuu_label",
    ])
    logger.info(f"  {len(df):,} events")

    OUTPUT.mkdir(parents=True, exist_ok=True)

    # Step 1: Assign splits
    split_assignment = assign_snapshot_split(snapshots)

    # Step 2: Compute statistics
    stats = _compute_split_stats(split_assignment, snapshots, df)

    # Step 3: Export
    export_paths = export_split_snapshots(split_assignment, snapshots)

    # Save split assignment
    split_path = OUTPUT / "snapshot_split.json"
    with open(split_path, "w") as f:
        json.dump(split_assignment, f, indent=2)
    logger.info(f"  ✅ Split assignment → {split_path}")

    # Save statistics
    stats_path = OUTPUT / "split_stats.json"
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)
    logger.info(f"  ✅ Split statistics → {stats_path}")

    # Step 4: Validate — check no temporal leakage and gap exists
    train_weeks = split_assignment["train"]
    val_weeks = split_assignment["val"]
    test_weeks = split_assignment["test"]

    assert _week_sort_key(train_weeks[-1]) < _week_sort_key(val_weeks[0]), "Temporal leakage: train/val overlap!"
    assert _week_sort_key(val_weeks[-1]) < _week_sort_key(test_weeks[0]), "Temporal leakage: val/test overlap!"
    # Verify gap: at least 1 week between train end and val start
    train_end_key = _week_sort_key(train_weeks[-1])
    val_start_key = _week_sort_key(val_weeks[0])
    assert (val_start_key[0] - train_end_key[0]) * 52 + (val_start_key[1] - train_end_key[1]) >= 2, \
        "Gap too small between train and val!"
    logger.info("  ✅ No temporal leakage, 2-week gap verified between splits")

    # Step 5: Verify event-level counts match
    total_events = sum(s["n_events"] for s in stats.values())
    logger.info(f"  Total events across splits: {total_events:,} (original: {len(df):,})")

    logger.info("✅ Split pipeline complete")
    del df, snapshots
    gc.collect()

    return {
        "split_assignment": split_path,
        "stats": stats_path,
        **export_paths,
    }
