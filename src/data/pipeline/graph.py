"""
Phase 5: Graph Construction for ST-GAT

Build vessel-centric spatiotemporal graphs for the ST-GAT model.

Graph Structure:
  NODES: Vessels (14,857 unique MMSIs)
  NODE FEATURES: Aggregated behavioral + registry + IUU features per vessel

  EDGES: Two types
  1. Encounter edges: Vessels that met at sea (from encounter events)
     - Direct transshipment/contact evidence
  2. Co-location edges: Vessels in same grid cell on same day
     - Proximity-based spatial connections

  TEMPORAL SNAPSHOTS: Weekly windows
  - Each snapshot contains vessels active in that week
  - Spatial edges computed per snapshot
  - Temporal edges connect same vessel across consecutive weeks

Output: PyTorch Geometric Data objects saved as .pt files

Functions:
- build_vessel_node_features: Aggregate per-vessel feature matrix
- build_encounter_edges: Extract vessel-to-vessel encounter edges
- build_colocation_edges: Compute co-location spatial edges
- build_temporal_edges: Connect vessels across time snapshots
- build_weekly_snapshots: Partition data into weekly graph snapshots
- run_graph_all: Full pipeline, save graph dataset
"""

from __future__ import annotations

import gc
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from ..constants import PROCESSED_DIR, GFW_EVENTS_LABELED, VESSEL_BEHAVIORAL

logger = logging.getLogger(__name__)
INPUT = PROCESSED_DIR
OUTPUT = PROCESSED_DIR

# ===== GRAPH PARAMETERS =====
GRID_RESOLUTION = 0.1  # degrees (~11km at equator)
MIN_VESSELS_PER_SNAPSHOT = 3  # skip snapshots with too few vessels


def build_vessel_node_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build per-vessel node feature matrix.

    Aggregates event-level data to vessel-level features suitable for
    graph neural network input. Features are kept raw — normalization
    happens in the model's data loader.

    Args:
        df: Labeled events DataFrame.

    Returns:
        DataFrame with one row per vessel, columns are node features.
    """
    logger.info("--- Building Vessel Node Features ---")

    # Start with behavioral features (already computed per vessel)
    behavioral = pd.read_parquet(INPUT / VESSEL_BEHAVIORAL)
    logger.info(f"  Behavioral features: {len(behavioral):,} vessels × {len(behavioral.columns)} cols")

    # Aggregate event-level features per vessel
    logger.info("  Aggregating event-level features per vessel...")

    # Spatial features
    spatial = df.groupby("mmsi").agg(
        mean_lat=("lat", "mean"),
        mean_lon=("lon", "mean"),
        std_lat=("lat", "std"),
        std_lon=("lon", "std"),
    ).fillna(0)

    # Temporal features
    temporal = df.groupby("mmsi").agg(
        mean_hour=("hour_of_day", "mean"),
        nighttime_ratio=("is_nighttime", "mean"),
        weekend_ratio=("is_weekend", "mean"),
    )

    # Risk features
    risk = df.groupby("mmsi").agg(
        max_iuu_score=("iuu_score", "max"),
        mean_iuu_score=("iuu_score", "mean"),
        iuu_event_count=("ind_fishing_in_mpa", "sum"),
        unauthorized_count=("ind_unauthorized_foreign", "sum"),
        encounter_count_ind=("ind_encounter_at_sea", "sum"),
        highseas_count=("ind_high_seas_fishing", "sum"),
        mpa_count=("ind_fishing_in_mpa", "sum"),
    )

    # Registry features (take first non-null per vessel)
    reg_cols = ["reg_length_m", "reg_tonnage_gt", "reg_engine_power_kw",
                "reg_vessel_class", "vessel_flag", "is_domestic"]
    registry = df.groupby("mmsi")[reg_cols].first()

    # SAR + effort features
    context = df.groupby("mmsi").agg(
        mean_sar_detections=("sar_total_detections", "mean"),
        mean_effort_hours=("effort_hours_in_cell", "mean"),
        mean_distance_shore=("distance_shore_start_km", "mean"),
        in_highseas_ratio=("in_highseas", "mean"),
    )

    # IUU label: take the max label across all events for this vessel
    label_map = {"normal": 0, "suspicious": 1, "probable_iuu": 2, "hard_iuu": 3}
    vessel_labels = df.groupby("mmsi")["iuu_label"].apply(
        lambda x: x.map(label_map).max()
    ).rename("vessel_iuu_label")

    # Merge all
    node_df = behavioral.set_index("mmsi")
    for agg_df in [spatial, temporal, risk, registry, context]:
        # Avoid column collisions
        overlap = [c for c in agg_df.columns if c in node_df.columns]
        if overlap:
            agg_df = agg_df.drop(columns=overlap)
        node_df = node_df.join(agg_df, how="left")

    node_df = node_df.join(vessel_labels, how="left")

    logger.info(f"  Node features: {len(node_df):,} vessels × {len(node_df.columns)} cols")

    # Log feature groups
    logger.info(f"  Feature groups:")
    logger.info(f"    Spatial: mean_lat, mean_lon, std_lat, std_lon")
    logger.info(f"    Temporal: mean_hour, nighttime_ratio, weekend_ratio")
    logger.info(f"    Behavioral: {len([c for c in node_df.columns if c in behavioral.columns])} cols")
    logger.info(f"    Registry: reg_length_m, reg_tonnage_gt, etc.")
    logger.info(f"    Risk: max_iuu_score, unauthorized_count, etc.")
    logger.info(f"    Context: mean_sar_detections, mean_effort_hours, etc.")
    logger.info(f"    Label: vessel_iuu_label")

    # Label distribution
    logger.info(f"  Vessel IUU label distribution:")
    for label, code in label_map.items():
        n = (node_df["vessel_iuu_label"] == code).sum()
        logger.info(f"    {label}: {n:,} ({n/len(node_df)*100:.1f}%)")

    return node_df.reset_index()


def build_encounter_edges(df: pd.DataFrame) -> pd.DataFrame:
    """Extract vessel-to-vessel encounter edges.

    Uses encounter events where both vessels have known MMSIs.

    Args:
        df: Labeled events DataFrame.

    Returns:
        DataFrame with columns [mmsi_1, mmsi_2, timestamp, edge_type].
    """
    logger.info("--- Building Encounter Edges ---")

    encounters = df[df["event_type"] == "encounter"].copy()
    encounters = encounters[encounters["mmsi_2"].notna() & (encounters["mmsi_2"] != "")]

    edges = encounters[["mmsi", "mmsi_2", "start_time", "lat", "lon"]].copy()
    edges.columns = ["mmsi_1", "mmsi_2", "timestamp", "lat", "lon"]
    edges["edge_type"] = "encounter"

    # Remove self-loops
    edges = edges[edges["mmsi_1"] != edges["mmsi_2"]]

    # Deduplicate (same pair, same timestamp)
    edges = edges.drop_duplicates(subset=["mmsi_1", "mmsi_2", "timestamp"])

    logger.info(f"  Unique encounter edges: {len(edges):,}")
    logger.info(f"  Unique vessel pairs: {edges.groupby(['mmsi_1','mmsi_2']).ngroups:,}")

    return edges


def build_colocation_edges(df: pd.DataFrame) -> pd.DataFrame:
    """Build co-location edges — vessels in same grid cell on same day.

    Args:
        df: Labeled events DataFrame.

    Returns:
        DataFrame with columns [mmsi_1, mmsi_2, date, grid_lat, grid_lon, edge_type].
    """
    logger.info("--- Building Co-location Edges ---")

    df["event_date"] = pd.to_datetime(df["start_time"]).dt.date

    # Group by (date, grid_cell) and find vessel pairs
    grouped = df.groupby(["event_date", "grid_lat", "grid_lon"])["mmsi"].unique()

    edge_list = []
    for (_, _, _), vessels in grouped.items():
        if len(vessels) < 2:
            continue
        # Create all pairs (undirected)
        for i in range(len(vessels)):
            for j in range(i + 1, min(i + 10, len(vessels))):  # cap at 10 per vessel
                edge_list.append((vessels[i], vessels[j]))

    if not edge_list:
        logger.warning("  No co-location edges found")
        return pd.DataFrame(columns=["mmsi_1", "mmsi_2", "edge_type"])

    edges = pd.DataFrame(edge_list, columns=["mmsi_1", "mmsi_2"])
    edges["edge_type"] = "colocation"

    # Deduplicate
    edges = edges.drop_duplicates()

    logger.info(f"  Unique co-location edges: {len(edges):,}")
    logger.info(f"  Unique vessel pairs: {edges.groupby(['mmsi_1','mmsi_2']).ngroups:,}")

    return edges


def build_weekly_snapshots(
    df: pd.DataFrame,
    node_df: pd.DataFrame,
    encounter_edges: pd.DataFrame,
    colocation_edges: pd.DataFrame,
) -> dict:
    """Build weekly graph snapshots.

    Each snapshot contains:
    - vessel_ids: list of MMSIs active that week
    - edge indices: src/dst pairs (snapshot-local)
    - edge types: encounter or colocation
    - labels: vessel IUU labels

    Uses vectorized operations for performance.

    Args:
        df: Labeled events DataFrame.
        node_df: Vessel node features.
        encounter_edges: Encounter edges with timestamps.
        colocation_edges: Co-location edges.

    Returns:
        Dict with snapshot data and metadata.
    """
    logger.info("--- Building Weekly Snapshots ---")

    # Pre-compute year_week for events
    starts = pd.to_datetime(df["start_time"])
    iso = starts.dt.isocalendar()
    df["year_week"] = starts.dt.year.astype(str) + "_W" + iso["week"].astype(str).str.zfill(2)

    # Pre-compute year_week for encounter edges
    enc = encounter_edges.copy()
    enc_starts = pd.to_datetime(enc["timestamp"])
    enc_iso = enc_starts.dt.isocalendar()
    enc["year_week"] = enc_starts.dt.year.astype(str) + "_W" + enc_iso["week"].astype(str).str.zfill(2)

    # Pre-compute year_week for co-location: use event dates
    # Co-location edges are derived from events, so assign them year_week from source events
    df["event_date"] = starts.dt.date
    event_yw = df[["mmsi", "event_date", "year_week"]].drop_duplicates()

    # Build MMSI → node index mapping
    mmsi_to_idx = {m: i for i, m in enumerate(node_df["mmsi"].values)}

    # Pre-index: active vessels per week (set lookup)
    weeks = sorted(df["year_week"].unique())
    week_vessel_sets = {}
    for w in weeks:
        active = set(df.loc[df["year_week"] == w, "mmsi"].unique())
        week_vessel_sets[w] = active

    logger.info(f"  Total weeks: {len(weeks)}")

    # Pre-filter encounter edges by week (vectorized groupby)
    enc_by_week = enc.groupby("year_week")[["mmsi_1", "mmsi_2"]].apply(
        lambda g: list(zip(g["mmsi_1"], g["mmsi_2"]))
    ).to_dict()

    # Pre-index co-location: map vessel -> set of co-located vessels (O(1) per lookup)
    coloc_by_vessel = {}
    for m1, m2 in zip(colocation_edges["mmsi_1"], colocation_edges["mmsi_2"]):
        coloc_by_vessel.setdefault(m1, set()).add(m2)
        coloc_by_vessel.setdefault(m2, set()).add(m1)
    logger.info(f"  Co-location indexed for {len(coloc_by_vessel)} vessels")

    snapshots = {}
    skipped = 0
    label_map = {"normal": 0, "suspicious": 1, "probable_iuu": 2, "hard_iuu": 3}

    for week in weeks:
        active = week_vessel_sets[week]

        if len(active) < MIN_VESSELS_PER_SNAPSHOT:
            skipped += 1
            continue

        # Create local index map
        local_idx = {m: i for i, m in enumerate(sorted(active)) if m in mmsi_to_idx}
        if len(local_idx) < MIN_VESSELS_PER_SNAPSHOT:
            skipped += 1
            continue

        src, dst, etypes = [], [], []

        # Resolve active vessels that are in our node feature set
        snap_vessels = sorted(active.intersection(mmsi_to_idx.keys()))

        # Encounter edges (pre-grouped)
        for m1, m2 in enc_by_week.get(week, []):
            if m1 in local_idx and m2 in local_idx:
                src.append(local_idx[m1])
                dst.append(local_idx[m2])
                etypes.append("encounter")

        # Co-location edges: only check vessels with known co-locations
        seen = set()
        for v in snap_vessels:
            if v not in coloc_by_vessel:
                continue
            for v2 in coloc_by_vessel[v]:
                if v2 in local_idx and (v2, v) not in seen:
                    src.append(local_idx[v])
                    dst.append(local_idx[v2])
                    etypes.append("colocation")
                    seen.add((v, v2))

        # Labels: max IUU label across events in this week
        week_df = df[df["year_week"] == week]
        snap_labels = week_df.groupby("mmsi")["iuu_label"].apply(
            lambda x: max(x.map(label_map))
        ).reindex(snap_vessels).fillna(0).astype(int).values

        vessel_indices = [mmsi_to_idx[m] for m in snap_vessels]

        snapshots[week] = {
            "n_vessels": len(snap_vessels),
            "n_edges": len(src),
            "vessel_indices": vessel_indices,
            "src": src,
            "dst": dst,
            "edge_types": etypes,
            "labels": snap_labels,
        }

    logger.info(f"  Built {len(snapshots)} snapshots (skipped {skipped} with <{MIN_VESSELS_PER_SNAPSHOT} vessels)")

    if snapshots:
        n_vessels = [s["n_vessels"] for s in snapshots.values()]
        n_edges = [s["n_edges"] for s in snapshots.values()]
        logger.info(f"  Vessels per snapshot: mean={np.mean(n_vessels):.0f}, "
                    f"min={min(n_vessels)}, max={max(n_vessels)}")
        logger.info(f"  Edges per snapshot: mean={np.mean(n_edges):.0f}, "
                    f"min={min(n_edges)}, max={max(n_edges)}")

    return snapshots


def run_graph_all() -> dict:
    """Run full graph construction pipeline.

    Returns:
        Dict with paths to output files.
    """
    logger.info("Loading labeled events...")
    df = pd.read_parquet(INPUT / GFW_EVENTS_LABELED)
    logger.info(f"Events: {len(df):,} rows × {len(df.columns)} cols")

    results = {}

    # Step 1: Node features
    node_df = build_vessel_node_features(df)
    node_path = OUTPUT / "vessel_node_features.parquet"
    node_df.to_parquet(node_path, index=False)
    logger.info(f"  ✅ Saved to {node_path}")
    results["node_features"] = node_path

    # Step 2: Encounter edges
    encounter_edges = build_encounter_edges(df)
    enc_path = OUTPUT / "encounter_edges.parquet"
    encounter_edges.to_parquet(enc_path, index=False)
    logger.info(f"  ✅ Saved to {enc_path}")
    results["encounter_edges"] = enc_path

    # Step 3: Co-location edges
    colocation_edges = build_colocation_edges(df)
    coloc_path = OUTPUT / "colocation_edges.parquet"
    colocation_edges.to_parquet(coloc_path, index=False)
    logger.info(f"  ✅ Saved to {coloc_path}")
    results["colocation_edges"] = coloc_path

    # Step 4: Weekly snapshots
    snapshots = build_weekly_snapshots(df, node_df, encounter_edges, colocation_edges)

    # Save snapshot metadata
    snap_meta = []
    for week, data in snapshots.items():
        snap_meta.append({
            "week": week,
            "n_vessels": data["n_vessels"],
            "n_edges": data["n_edges"],
            "n_encounter": data["edge_types"].count("encounter"),
            "n_colocation": data["edge_types"].count("colocation"),
        })
    snap_df = pd.DataFrame(snap_meta)
    snap_path = OUTPUT / "snapshot_metadata.parquet"
    snap_df.to_parquet(snap_path, index=False)
    logger.info(f"  ✅ Snapshot metadata saved to {snap_path}")
    results["snapshots"] = snap_path

    # Save snapshot data as compressed numpy
    import pickle
    graph_path = OUTPUT / "graph_snapshots.pkl"
    with open(graph_path, "wb") as f:
        pickle.dump(snapshots, f, protocol=4)
    logger.info(f"  ✅ Graph snapshots saved to {graph_path}")
    results["graph_data"] = graph_path

    logger.info("✅ Graph construction complete")
    del df
    gc.collect()
    return results
