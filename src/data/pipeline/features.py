"""
Phase 3a: Vessel Profile + Behavioral Features

Merges vessel profile features from step_3_1 and behavioral features from step_3_4.

Functions:
- add_vessel_profiles: Join events with vessel registry, add vessel features
- add_spatial_features: Grid cells, nearest port, sea zone
- add_temporal_features: Duration categories
- compute_behavioral_features: Per-vessel behavioral profile
- run_features_all: Run all feature functions
"""

from __future__ import annotations

import gc
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from ..constants import (
    PROCESSED_DIR, GFW_RAW_DIR, PORTS_FILE,
    GFW_EVENTS_CLEAN, VESSEL_REGISTRY_DEDUP,
    GFW_EVENTS_ENRICHED, VESSEL_BEHAVIORAL,
)

logger = logging.getLogger(__name__)
INPUT = PROCESSED_DIR
OUTPUT = PROCESSED_DIR


def add_vessel_profiles() -> Path:
    """Join events with vessel registry and add vessel features.

    Also adds spatial and temporal features (grid cells, nearest port,
    sea zone, duration categories).

    Returns:
        Path to gfw_events_enriched.parquet
    """
    logger.info("Loading events...")
    df = pd.read_parquet(INPUT / GFW_EVENTS_CLEAN)
    logger.info(f"Events: {len(df):,} rows × {len(df.columns)} cols")

    # Load vessel registry
    vessels = pd.read_parquet(INPUT / VESSEL_REGISTRY_DEDUP)
    vessels["mmsi"] = vessels["mmsi"].astype(str)
    logger.info(f"Vessel registry: {len(vessels):,} rows")

    v_lookup = vessels.drop_duplicates(subset=["mmsi"]).copy()
    v_lookup.index = v_lookup["mmsi"]
    v_lookup = v_lookup.drop(columns=["mmsi"])

    # Map vessel features to events
    logger.info("Mapping vessel features...")
    registry_cols = {
        "vessel_class": "reg_vessel_class",
        "length_m": "reg_length_m",
        "engine_power_kw": "reg_engine_power_kw",
        "tonnage_gt": "reg_tonnage_gt",
        "self_reported_fishing_vessel": "reg_self_reported_fishing",
        "flag_ais": "reg_flag_ais",
    }
    for src, dst in registry_cols.items():
        if src in v_lookup.columns:
            df[dst] = df["mmsi"].map(v_lookup[src].to_dict())
            filled = df[dst].notna().sum()
            logger.info(f"  {dst}: {filled:,} filled ({filled/len(df)*100:.1f}%)")

    # Derived features
    df["is_fishing_vessel"] = (
        (df.get("reg_self_reported_fishing", pd.Series(dtype=bool)) == True) |
        (df.get("reg_vessel_class", pd.Series(dtype=str)).str.contains(
            "fishing|trawl|seine|longline|gillnet|dredge|squid", case=False, na=False)) |
        (df["vessel_type"].str.contains("fishing|trawl|seine|longline|gillnet", case=False, na=False))
    )

    def size_cat(length):
        if pd.isna(length) or length <= 0:
            return "unknown"
        if length < 12:
            return "small"
        if length < 24:
            return "medium"
        return "large"

    df["size_category"] = df["reg_length_m"].map(size_cat)
    df["tonnage_per_length"] = np.where(
        df["reg_length_m"] > 0, df["reg_tonnage_gt"] / df["reg_length_m"], np.nan
    )

    # --- Spatial features ---
    add_spatial_features(df)

    # --- Temporal features ---
    add_temporal_features(df)

    del v_lookup, vessels; gc.collect()

    # Validation
    logger.info(f"Shape: {len(df):,} rows × {len(df.columns)} cols")
    logger.info(f"Size category:\n{df['size_category'].value_counts().to_string()}")
    logger.info(f"Sea zone (top 10):\n{df['sea_zone'].value_counts().head(10).to_string()}")

    out = OUTPUT / GFW_EVENTS_ENRICHED
    df.to_parquet(out, index=False, compression="snappy")
    logger.info(f"✅ Saved to {out} ({out.stat().st_size / 1024 / 1024:.1f} MB)")
    del df; gc.collect()
    return out


def add_spatial_features(df: pd.DataFrame) -> None:
    """Add spatial features in-place: grid cells, nearest port, sea zone.

    Args:
        df: Events DataFrame (modified in-place).
    """
    logger.info("Adding spatial features...")

    # Grid cell (0.1° ≈ 11km)
    df["grid_lat"] = (df["lat"] * 10).round(0) / 10
    df["grid_lon"] = (df["lon"] * 10).round(0) / 10

    # Nearest port (vectorized)
    with open(GFW_RAW_DIR / PORTS_FILE) as f:
        ports = json.load(f)

    logger.info(f"Computing nearest port from {len(ports)} ports...")
    port_lats = np.array([p["lat"] for p in ports])
    port_lons = np.array([p["lon"] for p in ports])
    port_names = [p["name"] for p in ports]

    event_lats = df["lat"].values
    event_lons = df["lon"].values

    min_idx = np.zeros(len(df), dtype=int)
    min_dist = np.full(len(df), np.inf)

    for i, (plat, plon) in enumerate(zip(port_lats, port_lons)):
        d = np.sqrt((event_lats - plat)**2 + (event_lons - plon)**2)
        mask = d < min_dist
        min_idx[mask] = i
        min_dist[mask] = d[mask]

    df["nearest_port_name"] = [port_names[i] for i in min_idx]
    df["nearest_port_dist_km"] = min_dist * 111

    # Sea zone classification (vectorized)
    lat = df["lat"].values
    lon = df["lon"].values

    conditions = [
        (lat >= -8) & (lat <= -5) & (lon >= 105) & (lon <= 115),
        (lat >= -8) & (lat <= -2) & (lon >= 115) & (lon <= 120),
        (lat >= -5) & (lat <= 2) & (lon >= 108) & (lon <= 120),
        (lat >= 0) & (lat <= 5) & (lon >= 120) & (lon <= 128),
        (lat >= -4) & (lat <= 2) & (lon >= 128) & (lon <= 141),
        (lat >= -8) & (lat <= -3) & (lon >= 110) & (lon <= 116),
        (lat >= 2) & (lat <= 6) & (lon >= 95) & (lon <= 105),
        (lat >= -2) & (lat <= 4) & (lon >= 130) & (lon <= 141),
        (lat >= -8) & (lat <= -2) & (lon >= 120) & (lon <= 130),
    ]
    choices = [
        "Java Sea", "Bali Sea", "Karimata Strait", "Celebes Sea",
        "Banda Sea", "Indian Ocean (S)", "Malacca Strait", "Arafura Sea", "Timor Sea",
    ]

    df["sea_zone"] = np.select(conditions, choices, default="Other")
    df.loc[df["lat"].isna() | df["lon"].isna(), "sea_zone"] = "unknown"


def add_temporal_features(df: pd.DataFrame) -> None:
    """Add temporal features in-place: duration categories.

    Args:
        df: Events DataFrame (modified in-place).
    """
    logger.info("Adding temporal features...")
    df["duration_category"] = pd.cut(
        df["duration_hours"],
        bins=[-0.01, 2, 8, float("inf")],
        labels=["short", "medium", "long"]
    ).astype(str)


def compute_behavioral_features() -> Path:
    """Compute per-vessel behavioral profile.

    Returns:
        Path to vessel_behavioral_features.parquet
    """
    logger.info("Loading enriched events...")

    cols = ["mmsi", "event_type", "start_time", "lat", "lon", "duration_hours",
            "vessel_flag", "total_distance_km", "avg_speed_knots",
            "distance_shore_start_km", "grid_lat", "grid_lon",
            "nearest_port_dist_km", "is_domestic"]

    df = pd.read_parquet(INPUT / GFW_EVENTS_ENRICHED, columns=cols)
    logger.info(f"Loaded: {len(df):,} events from {df['mmsi'].nunique():,} vessels")

    df = df.sort_values(["mmsi", "start_time"]).reset_index(drop=True)

    # Per-vessel overall stats
    logger.info("Computing per-vessel overall stats...")
    vessel_stats = df.groupby("mmsi").agg(
        total_events=("event_type", "count"),
        first_seen=("start_time", "min"),
        last_seen=("start_time", "max"),
        vessel_flag=("vessel_flag", "first"),
        is_domestic=("is_domestic", "first"),
    ).reset_index()

    vessel_stats["tracking_span_days"] = (
        vessel_stats["last_seen"] - vessel_stats["first_seen"]
    ).dt.total_seconds() / 86400

    # Event type counts
    logger.info("  Event type breakdown...")
    for etype in ["fishing", "encounter", "loitering", "port_visit"]:
        counts = df[df["event_type"] == etype].groupby("mmsi").size().reset_index(name=f"{etype}_count")
        vessel_stats = vessel_stats.merge(counts, on="mmsi", how="left")
        vessel_stats[f"{etype}_count"] = vessel_stats[f"{etype}_count"].fillna(0).astype(int)

    # Fishing patterns
    logger.info("  Fishing patterns...")
    fishing = df[df["event_type"] == "fishing"].groupby("mmsi").agg(
        avg_fishing_duration=("duration_hours", "mean"),
        total_fishing_hours=("duration_hours", "sum"),
        avg_fishing_distance=("total_distance_km", "mean"),
        fishing_lat_mean=("lat", "mean"),
        fishing_lon_mean=("lon", "mean"),
    ).reset_index()
    vessel_stats = vessel_stats.merge(fishing, on="mmsi", how="left")

    # Spatial patterns
    logger.info("  Spatial patterns...")
    spatial_base = df.groupby("mmsi").agg(
        avg_distance_shore=("distance_shore_start_km", "mean"),
        max_distance_shore=("distance_shore_start_km", "max"),
        lat_min=("lat", "min"), lat_max=("lat", "max"),
        lon_min=("lon", "min"), lon_max=("lon", "max"),
    ).reset_index()

    grid_unique = df.drop_duplicates(subset=["mmsi", "grid_lat", "grid_lon"])
    grid_counts = grid_unique.groupby("mmsi").size().reset_index(name="unique_grid_cells")

    spatial_base["spatial_range_km"] = np.sqrt(
        (spatial_base["lat_max"] - spatial_base["lat_min"])**2 +
        (spatial_base["lon_max"] - spatial_base["lon_min"])**2
    ) * 111
    vessel_stats = vessel_stats.merge(
        spatial_base[["mmsi", "avg_distance_shore", "max_distance_shore", "spatial_range_km"]],
        on="mmsi", how="left"
    )
    vessel_stats = vessel_stats.merge(grid_counts, on="mmsi", how="left")

    # Speed patterns
    logger.info("  Speed patterns...")
    speed = df[df["avg_speed_knots"].notna()].groupby("mmsi").agg(
        avg_speed_knots=("avg_speed_knots", "mean"),
        speed_std=("avg_speed_knots", "std"),
    ).reset_index()
    speed["speed_std"] = speed["speed_std"].fillna(0)
    vessel_stats = vessel_stats.merge(speed, on="mmsi", how="left")

    # Encounter patterns
    logger.info("  Encounter patterns...")
    encounters = df[df["event_type"] == "encounter"].copy()
    enc_stats = encounters.groupby("mmsi").agg(encounters_total=("event_type", "count")).reset_index()
    foreign_enc = encounters[~encounters["is_domestic"]].groupby("mmsi").size().reset_index(name="encounters_with_foreign")
    enc_stats = enc_stats.merge(foreign_enc, on="mmsi", how="left")
    enc_stats["encounters_with_foreign"] = enc_stats["encounters_with_foreign"].fillna(0).astype(int)
    vessel_stats = vessel_stats.merge(enc_stats, on="mmsi", how="left")

    # Loitering patterns
    logger.info("  Loitering patterns...")
    loiter = df[df["event_type"] == "loitering"].groupby("mmsi").agg(
        loitering_events=("event_type", "count"),
        total_loitering_hours=("duration_hours", "sum"),
    ).reset_index()
    vessel_stats = vessel_stats.merge(loiter, on="mmsi", how="left")

    # Port visit patterns
    logger.info("  Port visit patterns...")
    ports = df[df["event_type"] == "port_visit"].groupby("mmsi").agg(
        port_visits=("event_type", "count"),
        avg_port_duration=("duration_hours", "mean"),
    ).reset_index()
    vessel_stats = vessel_stats.merge(ports, on="mmsi", how="left")

    # Fill NaN
    fill_zero = ["fishing_count", "encounter_count", "loitering_count", "port_visit_count",
                 "encounters_total", "encounters_with_foreign", "loitering_events",
                 "port_visits", "unique_grid_cells"]
    for col in fill_zero:
        if col in vessel_stats.columns:
            vessel_stats[col] = vessel_stats[col].fillna(0).astype(int)

    # Derived ratios
    vessel_stats["encounter_rate"] = vessel_stats["encounters_total"] / vessel_stats["total_events"].clip(lower=1)
    vessel_stats["loitering_rate"] = vessel_stats["loitering_events"] / vessel_stats["total_events"].clip(lower=1)
    vessel_stats["fishing_ratio"] = vessel_stats["fishing_count"] / vessel_stats["total_events"].clip(lower=1)
    vessel_stats["avg_fishing_hours_per_trip"] = vessel_stats["total_fishing_hours"] / vessel_stats["fishing_count"].clip(lower=1)

    logger.info(f"Shape: {len(vessel_stats):,} vessels × {len(vessel_stats.columns)} cols")

    out = OUTPUT / VESSEL_BEHAVIORAL
    vessel_stats.to_parquet(out, index=False)
    logger.info(f"✅ Saved to {out} ({out.stat().st_size / 1024 / 1024:.1f} MB)")
    del df, vessel_stats; gc.collect()
    return out


def run_features_all() -> dict[str, Path]:
    """Run all feature functions.

    Returns:
        Dict mapping dataset name to output parquet path.
    """
    results = {}
    results["gfw_events_enriched"] = add_vessel_profiles()
    results["vessel_behavioral"] = compute_behavioral_features()
    logger.info("✅ Features phase complete")
    return results
