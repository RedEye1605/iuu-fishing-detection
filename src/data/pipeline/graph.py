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

from ..constants import PROCESSED_DIR, GFW_EVENTS_LABELED, VESSEL_BEHAVIORAL, TRAIN_CUTOFF

logger = logging.getLogger(__name__)
INPUT = PROCESSED_DIR
OUTPUT = PROCESSED_DIR

# ===== GRAPH PARAMETERS =====
GRID_RESOLUTION = 0.1  # degrees (~11km at equator)
MIN_VESSELS_PER_SNAPSHOT = 3  # skip snapshots with too few vessels


def build_vessel_node_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build per-vessel node feature matrix.

    Aggregates event-level data to vessel-level features suitable for
    graph neural network input. Behavioral and temporal aggregations use
    training period only to prevent information leakage. Registry and
    grid-level context features use all available data (static properties).

    Args:
        df: Labeled events DataFrame.

    Returns:
        Tuple of (DataFrame with one row per vessel, feature column list).
    """
    logger.info("--- Building Vessel Node Features ---")

    # Split: training period for behavioral/temporal features, all data for static
    train_cutoff = pd.Timestamp(TRAIN_CUTOFF, tz="UTC")
    df_train = df[df["start_time"] < train_cutoff]
    logger.info(f"  Training period: {len(df_train):,} events, {df_train['mmsi'].nunique():,} vessels")
    logger.info(f"  All data: {len(df):,} events, {df['mmsi'].nunique():,} vessels")

    # Start with behavioral features (already train-only from Phase 3)
    behavioral = pd.read_parquet(INPUT / VESSEL_BEHAVIORAL)
    logger.info(f"  Behavioral features: {len(behavioral):,} vessels × {len(behavioral.columns)} cols")

    # Create node_df from ALL unique vessels, LEFT JOIN behavioral
    all_mmsi = sorted(df["mmsi"].unique())
    node_df = pd.DataFrame({"mmsi": all_mmsi}).set_index("mmsi")
    node_df = node_df.join(behavioral.set_index("mmsi"), how="left")
    logger.info(f"  After behavioral join: {len(node_df):,} vessels "
                f"({node_df['total_events'].notna().sum():,} with behavioral data)")

    # Indicator: vessel had training period activity
    node_df["has_behavioral_data"] = node_df["total_events"].notna().astype(int)

    # Aggregate event-level features — training period only
    logger.info("  Aggregating event-level features (training period)...")

    # Spatial features (train-only)
    spatial = df_train.groupby("mmsi").agg(
        mean_lat=("lat", "mean"),
        mean_lon=("lon", "mean"),
        std_lat=("lat", "std"),
        std_lon=("lon", "std"),
    )

    # Temporal features (train-only)
    temporal = df_train.groupby("mmsi").agg(
        mean_hour=("hour_of_day", "mean"),
        nighttime_ratio=("is_nighttime", "mean"),
        weekend_ratio=("is_weekend", "mean"),
    )

    # Risk-proximate features (train-only — prevents label leakage)
    risk = df_train.groupby("mmsi").agg(
        unauthorized_count=("ind_unauthorized_foreign", "sum"),
        highseas_count=("ind_high_seas_fishing", "sum"),
        mpa_count=("ind_fishing_in_mpa", "sum"),
    )

    # Registry features (all data — static vessel properties, no leakage)
    reg_cols = ["reg_length_m", "reg_tonnage_gt", "reg_engine_power_kw",
                "reg_vessel_class", "vessel_flag", "is_domestic"]
    registry = df.groupby("mmsi")[reg_cols].first()

    # Grid-level context features: location properties (all data) + behavioral (train-only)
    # mean_sar_detections and mean_effort_hours are grid-cell context → all data
    # in_highseas_ratio is vessel behavior → training period only (prevents leakage)
    context_all = df.groupby("mmsi").agg(
        mean_sar_detections=("sar_total_detections", "mean"),
        mean_effort_hours=("effort_hours_in_cell", "mean"),
    )
    context_train = df_train.groupby("mmsi").agg(
        in_highseas_ratio=("in_highseas", "mean"),
    )

    # IUU label: take the max label across all events for this vessel
    label_map = {"normal": 0, "suspicious": 1, "probable_iuu": 2, "hard_iuu": 3}
    vessel_labels = df.groupby("mmsi")["iuu_label"].apply(
        lambda x: x.map(label_map).max()
    ).rename("vessel_iuu_label")

    # Merge all — LEFT JOIN preserves ALL vessels, NaN for test-only
    for agg_df in [spatial, temporal, risk, registry, context_all, context_train]:
        # Avoid column collisions
        overlap = [c for c in agg_df.columns if c in node_df.columns]
        if overlap:
            agg_df = agg_df.drop(columns=overlap)
        node_df = node_df.join(agg_df, how="left")

    # Remove redundant features: fishing_lat/lon_mean ≈ mean_lat/lon (r>0.98)
    redundant = ["fishing_lat_mean", "fishing_lon_mean",
                 "max_distance_shore",      # r=0.955 with avg_distance_shore
                 "encounters_with_foreign", # r=0.946 with encounter_count
                 "avg_fishing_distance",    # r=0.913 with avg_fishing_duration
                 ]
    for c in redundant:
        if c in node_df.columns:
            node_df = node_df.drop(columns=[c])
            logger.info(f"  Removed redundant feature: {c}")

    # Add indicator features for high-NaN columns (helps model distinguish 0 vs unknown)
    node_df["has_fishing_data"] = node_df["fishing_count"].notna().astype(int)
    node_df["has_port_data"] = node_df["avg_port_duration"].notna().astype(int)

    node_df = node_df.join(vessel_labels, how="left")

    # Add has_registry indicator (many vessels have no registry match)
    node_df["has_registry"] = node_df["reg_length_m"].notna().astype(int)

    # Log NaN rates for key feature groups
    logger.info(f"  Node features: {len(node_df):,} vessels × {len(node_df.columns)} cols")
    for col in ["has_behavioral_data", "has_fishing_data", "has_port_data", "has_registry"]:
        if col in node_df.columns:
            n = node_df[col].sum()
            logger.info(f"    {col}: {n:,} / {len(node_df):,} ({n/len(node_df)*100:.1f}%)")

    # Log feature groups
    logger.info(f"  Feature groups:")
    logger.info(f"    Spatial: mean_lat, mean_lon, std_lat, std_lon")
    logger.info(f"    Temporal: mean_hour, nighttime_ratio, weekend_ratio")
    logger.info(f"    Behavioral: {len([c for c in node_df.columns if c in behavioral.columns])} cols")
    logger.info(f"    Registry: reg_length_m, reg_tonnage_gt, etc. + has_registry")
    logger.info(f"    Risk proxies: unauthorized_count, highseas_count, mpa_count")
    logger.info(f"    Context: mean_sar_detections, mean_effort_hours, in_highseas_ratio")
    logger.info(f"    Label: vessel_iuu_label")

    # Label distribution
    logger.info(f"  Vessel IUU label distribution:")
    for label, code in label_map.items():
        n = (node_df["vessel_iuu_label"] == code).sum()
        logger.info(f"    {label}: {n:,} ({n/len(node_df)*100:.1f}%)")

    return node_df.reset_index(), node_df.columns.tolist()


def build_encounter_edges(df: pd.DataFrame) -> pd.DataFrame:
    """Extract vessel-to-vessel encounter edges with attributes.

    Uses encounter events where both vessels have known MMSIs.
    Includes edge attributes: duration and median distance.

    Args:
        df: Labeled events DataFrame.

    Returns:
        DataFrame with columns [mmsi_1, mmsi_2, timestamp, edge_type,
        edge_duration_hours, edge_distance_km].
    """
    logger.info("--- Building Encounter Edges ---")

    encounters = df[df["event_type"] == "encounter"].copy()
    encounters = encounters[encounters["mmsi_2"].notna() & (encounters["mmsi_2"] != "")]

    edge_cols = ["mmsi", "mmsi_2", "start_time", "lat", "lon"]
    available = [c for c in edge_cols if c in encounters.columns]
    edges = encounters[available].copy()
    edges.columns = ["mmsi_1", "mmsi_2", "timestamp", "lat", "lon"][:len(available)]
    # Ensure consistent columns
    for c in ["mmsi_1", "mmsi_2", "timestamp"]:
        if c not in edges.columns:
            edges[c] = ""
    edges["edge_type"] = "encounter"

    # Edge attributes: duration and distance
    if "duration_hours" in encounters.columns:
        edges["edge_duration_hours"] = encounters["duration_hours"].values
    if "encounter_median_distance_km" in encounters.columns:
        edges["edge_distance_km"] = encounters["encounter_median_distance_km"].values

    # Remove self-loops
    edges = edges[edges["mmsi_1"] != edges["mmsi_2"]]

    # Deduplicate (same pair, same timestamp)
    edges = edges.drop_duplicates(subset=["mmsi_1", "mmsi_2", "timestamp"])

    logger.info(f"  Unique encounter edges: {len(edges):,}")
    logger.info(f"  Unique vessel pairs: {edges.groupby(['mmsi_1','mmsi_2']).ngroups:,}")
    if "edge_duration_hours" in edges.columns:
        logger.info(f"  Duration stats: mean={edges['edge_duration_hours'].mean():.1f}h, "
                     f"median={edges['edge_duration_hours'].median():.1f}h")

    return edges


def build_colocation_edges(df: pd.DataFrame, max_vessels_per_cell: int = 15, distance_km: float = 5.0) -> pd.DataFrame:
    """Build co-location edges — vessels within distance threshold in same grid cell on same day.

    Replaces the previous arbitrary cap (10 per vessel) with a distance-based filter.
    Within each (date, grid_cell) group, only connects vessels that are actually close
    (within distance_km), keeping at most max_vessels_per_cell nearest neighbors.

    Args:
        df: Labeled events DataFrame.
        max_vessels_per_cell: Maximum vessels to connect per cell per day.
        distance_km: Maximum inter-vessel distance in km for co-location edge.

    Returns:
        DataFrame with columns [mmsi_1, mmsi_2, event_date, edge_type, edge_distance_km].
    """
    logger.info(f"--- Building Co-location Edges (distance<{distance_km}km, max_per_cell={max_vessels_per_cell}) ---")

    df["event_date"] = pd.to_datetime(df["start_time"]).dt.date

    # Get representative position per vessel per (date, grid_cell)
    vessel_pos = df.groupby(["event_date", "grid_lat", "grid_lon", "mmsi"]).agg(
        lat=("lat", "mean"),
        lon=("lon", "mean"),
    ).reset_index()

    edge_list = []
    for (date, _, _), cell_df in vessel_pos.groupby(["event_date", "grid_lat", "grid_lon"]):
        if len(cell_df) < 2:
            continue
        mmsis = cell_df["mmsi"].values
        lats = cell_df["lat"].values
        lons = cell_df["lon"].values

        n = len(mmsis)
        # Precompute pairwise distances (haversine approx: 1 degree ≈ 111km)
        dist_threshold_deg = distance_km / 111.0
        for i in range(min(n, max_vessels_per_cell)):
            for j in range(i + 1, n):
                dlat = lats[j] - lats[i]
                dlon = lons[j] - lons[i]
                approx_dist_deg = np.sqrt(dlat**2 + dlon**2)
                if approx_dist_deg <= dist_threshold_deg:
                    dist_km = approx_dist_deg * 111.0
                    edge_list.append((mmsis[i], mmsis[j], date, dist_km))

    if not edge_list:
        logger.warning("  No co-location edges found")
        return pd.DataFrame(columns=["mmsi_1", "mmsi_2", "event_date", "edge_type", "edge_distance_km"])

    edges = pd.DataFrame(edge_list, columns=["mmsi_1", "mmsi_2", "event_date", "edge_distance_km"])
    edges["edge_type"] = "colocation"

    # Deduplicate (same pair, same date)
    edges = edges.drop_duplicates(subset=["mmsi_1", "mmsi_2", "event_date"])

    logger.info(f"  Unique co-location edge-date pairs: {len(edges):,}")
    logger.info(f"  Unique vessel pairs: {edges.groupby(['mmsi_1','mmsi_2']).ngroups:,}")
    logger.info(f"  Mean distance: {edges['edge_distance_km'].mean():.2f} km")

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
    # Include edge attributes: duration_hours and distance_km
    enc_edge_cols = ["mmsi_1", "mmsi_2"]
    if "edge_duration_hours" in enc.columns:
        enc_edge_cols.append("edge_duration_hours")
    if "edge_distance_km" in enc.columns:
        enc_edge_cols.append("edge_distance_km")
    enc_by_week = enc.groupby("year_week")[enc_edge_cols].apply(
        lambda g: list(g.itertuples(index=False, name=None))
    ).to_dict()

    # Pre-compute year_week for co-location edges using event_date
    coloc = colocation_edges.copy()
    coloc["event_date_dt"] = pd.to_datetime(coloc["event_date"])
    coloc_iso = coloc["event_date_dt"].dt.isocalendar()
    coloc["year_week"] = coloc["event_date_dt"].dt.year.astype(str) + "_W" + coloc_iso["week"].astype(str).str.zfill(2)

    # Co-location edges with distance attribute
    coloc_edge_cols = ["mmsi_1", "mmsi_2"]
    if "edge_distance_km" in coloc.columns:
        coloc_edge_cols.append("edge_distance_km")

    # Pre-index co-location by week for temporal scoping
    coloc_by_week = coloc.groupby("year_week")[coloc_edge_cols].apply(
        lambda g: list(g.itertuples(index=False, name=None))
    ).to_dict()
    logger.info(f"  Co-location indexed for {len(coloc_by_week)} weeks")

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

        src, dst, etypes, edge_durations, edge_distances = [], [], [], [], []

        # Resolve active vessels that are in our node feature set
        snap_vessels = sorted(active.intersection(mmsi_to_idx.keys()))

        # Encounter edges (pre-grouped, with attributes)
        for edge_data in enc_by_week.get(week, []):
            m1, m2 = edge_data[0], edge_data[1]
            if m1 in local_idx and m2 in local_idx:
                src.append(local_idx[m1])
                dst.append(local_idx[m2])
                etypes.append("encounter")
                # Extract optional attributes
                dur = edge_data[2] if len(edge_data) > 2 and edge_data[2] is not None else 0.0
                dist = edge_data[3] if len(edge_data) > 3 and edge_data[3] is not None else 0.0
                edge_durations.append(dur)
                edge_distances.append(dist)

        # Co-location edges (temporally scoped — only edges from this week)
        seen = set()
        for edge_data in coloc_by_week.get(week, []):
            m1, m2 = edge_data[0], edge_data[1]
            if m1 in local_idx and m2 in local_idx:
                pair = (min(m1, m2), max(m1, m2))
                if pair not in seen:
                    src.append(local_idx[m1])
                    dst.append(local_idx[m2])
                    etypes.append("colocation")
                    dist = edge_data[2] if len(edge_data) > 2 and edge_data[2] is not None else 0.0
                    edge_durations.append(0.0)  # co-location has no duration
                    edge_distances.append(dist)
                    seen.add(pair)

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
            "edge_durations": edge_durations,
            "edge_distances": edge_distances,
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
    node_df, feature_cols = build_vessel_node_features(df)

    # Step 1b: Normalize numeric features (RobustScaler fit on training vessels only)
    # RobustScaler uses median/IQR — resistant to maritime data outliers
    from sklearn.preprocessing import RobustScaler
    import pickle as pkl

    numeric_cols = node_df.select_dtypes(include=[np.number]).columns.tolist()
    # Exclude the label and indicator features from normalization
    exclude_from_norm = {"vessel_iuu_label", "has_behavioral_data", "has_fishing_data",
                         "has_port_data", "has_registry", "is_domestic", "is_foc_flag"}
    normalize_cols = [c for c in numeric_cols if c not in exclude_from_norm]
    logger.info(f"  Normalizing {len(normalize_cols)} numeric features...")
    logger.info(f"  Excluded from normalization (binary/indicator): {sorted(exclude_from_norm & set(numeric_cols))}")

    # Impute NaN with 0 BEFORE scaling (vessels without training period data)
    nan_counts = node_df[normalize_cols].isnull().sum()
    nan_cols = nan_counts[nan_counts > 0]
    if len(nan_cols):
        logger.info(f"  Imputing NaN → 0 for {len(nan_cols)} columns:")
        for col, n in nan_cols.items():
            logger.info(f"    {col}: {n:,} NaN ({n/len(node_df)*100:.1f}%)")
    node_df[normalize_cols] = node_df[normalize_cols].fillna(0)

    # Fit scaler on training-period vessels only, apply to all
    train_mask = node_df["has_behavioral_data"] == 1
    scaler = RobustScaler()
    scaler.fit(node_df.loc[train_mask, normalize_cols])
    node_df[normalize_cols] = scaler.transform(node_df[normalize_cols])
    logger.info(f"  RobustScaler fit on {train_mask.sum():,} training vessels, applied to all {len(node_df):,}")

    # Log scale stats
    logger.info(f"  After normalization — sample stats:")
    for col in normalize_cols[:5]:
        logger.info(f"    {col}: mean={node_df[col].mean():.4f}, std={node_df[col].std():.4f}")

    node_path = OUTPUT / "vessel_node_features.parquet"
    node_df.to_parquet(node_path, index=False)
    logger.info(f"  ✅ Saved to {node_path}")
    results["node_features"] = node_path

    # Save scaler for inference
    scaler_path = OUTPUT / "feature_scaler.pkl"
    with open(scaler_path, "wb") as f:
        pkl.dump({"scaler": scaler, "columns": normalize_cols}, f)
    logger.info(f"  ✅ Scaler saved to {scaler_path}")
    results["scaler"] = scaler_path

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
