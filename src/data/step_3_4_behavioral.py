"""
Phase 3 Step 3.4: Behavioral Features (per vessel, rolling windows)

Compute per-vessel behavioral profile using 7-day and 30-day rolling windows.
Output: data/processed/vessel_behavioral_features.parquet
"""

from __future__ import annotations
import gc, logging
from pathlib import Path
import pandas as pd
import numpy as np

from .constants import PROCESSED_DIR, GFW_EVENTS_ENRICHED, VESSEL_BEHAVIORAL

logger = logging.getLogger(__name__)
INPUT = PROCESSED_DIR
OUTPUT = PROCESSED_DIR


def run_step_3_4():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    logger.info("=" * 60 + "\nSTEP 3.4: BEHAVIORAL FEATURES (PER VESSEL)\n" + "=" * 60)

    # Load enriched events - only columns we need
    cols = ["mmsi", "event_type", "start_time", "lat", "lon", "duration_hours",
            "vessel_flag", "total_distance_km", "avg_speed_knots",
            "distance_shore_start_km", "grid_lat", "grid_lon",
            "nearest_port_dist_km", "is_domestic"]

    df = pd.read_parquet(INPUT / GFW_EVENTS_ENRICHED, columns=cols)
    logger.info(f"Loaded: {len(df):,} events from {df['mmsi'].nunique():,} vessels")

    df = df.sort_values(["mmsi", "start_time"]).reset_index(drop=True)

    # ===== PER-VESSEL AGGREGATES (overall) =====
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

    # Event type counts per vessel
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

    # Spatial patterns — FIX: proper unique_grid_cells using two-stage groupby
    logger.info("  Spatial patterns...")
    spatial_base = df.groupby("mmsi").agg(
        avg_distance_shore=("distance_shore_start_km", "mean"),
        max_distance_shore=("distance_shore_start_km", "max"),
        lat_min=("lat", "min"),
        lat_max=("lat", "max"),
        lon_min=("lon", "min"),
        lon_max=("lon", "max"),
    ).reset_index()

    # Stage 1: unique (mmsi, grid_lat, grid_lon) combinations
    grid_unique = df.drop_duplicates(subset=["mmsi", "grid_lat", "grid_lon"])
    # Stage 2: count unique grid cells per vessel
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
    enc_stats = encounters.groupby("mmsi").agg(
        encounters_total=("event_type", "count"),
    ).reset_index()

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

    # Fill NaN for vessels without certain event types
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

    # ===== VALIDATION =====
    logger.info(f"--- Validation ---")
    logger.info(f"Shape: {len(vessel_stats):,} vessels × {len(vessel_stats.columns)} cols")
    logger.info(f"Event count distribution:\n{vessel_stats['total_events'].describe().to_string()}")
    logger.info(f"Encounter rate stats:\n{vessel_stats['encounter_rate'].describe().to_string()}")

    out = OUTPUT / VESSEL_BEHAVIORAL
    vessel_stats.to_parquet(out, index=False)
    sz = out.stat().st_size / 1024 / 1024
    logger.info(f"✅ Saved to {out} ({sz:.1f} MB)")


if __name__ == "__main__":
    run_step_3_4()
