"""
Phase 2 Steps 2.2–2.7: Clean & Validate GFW Events

2.2: Null handling - fill flags/geartype from registry, drop bad rows
2.3: Coordinate validation - Indonesia bounding box
2.4: Date normalization - add temporal features
2.5: Flag standardization - ISO 3166, add is_domestic
2.6: Outlier removal - cap durations, flag speeds
Output: data/processed/gfw_events_clean.parquet
"""

from __future__ import annotations

import gc
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from .constants import (
    PROCESSED_DIR, FLAG_MAP, INDONESIA_BBOX,
    GFW_EVENTS_DEDUP, VESSEL_REGISTRY_DEDUP, GFW_EVENTS_CLEAN,
)

logger = logging.getLogger(__name__)

INPUT_DIR = PROCESSED_DIR
OUTPUT_DIR = PROCESSED_DIR

LAT_MIN = INDONESIA_BBOX["lat_min"]
LAT_MAX = INDONESIA_BBOX["lat_max"]
LON_MIN = INDONESIA_BBOX["lon_min"]
LON_MAX = INDONESIA_BBOX["lon_max"]


def run_step_2_2_to_2_6():
    """Execute Steps 2.2-2.6 on GFW events."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    logger.info("=" * 60 + "\nSTEPS 2.2–2.6: CLEAN & VALIDATE GFW EVENTS\n" + "=" * 60)

    # Load deduped events
    df = pd.read_parquet(INPUT_DIR / GFW_EVENTS_DEDUP)
    logger.info(f"Loaded: {len(df):,} rows × {len(df.columns)} cols")

    # Load vessel registry for enrichment — MMSI as string for join
    df_vessels = pd.read_parquet(INPUT_DIR / VESSEL_REGISTRY_DEDUP)
    df_vessels["mmsi"] = df_vessels["mmsi"].astype(str)
    vessel_lookup = df_vessels.drop_duplicates(subset=["mmsi"]).set_index("mmsi")
    logger.info(f"Vessel registry: {len(vessel_lookup):,} unique MMSIs")
    del df_vessels; gc.collect()

    # ===== 2.2: NULL HANDLING =====
    logger.info("--- Step 2.2: Null Handling ---")
    logger.info(f"Null MMSI: {df['mmsi'].isna().sum():,}")
    logger.info(f"Empty MMSI: {(df['mmsi'] == '').sum():,}")
    logger.info(f"Null lat/lon: {df['lat'].isna().sum():,} / {df['lon'].isna().sum():,}")
    logger.info(f"Null vessel_flag: {(df['vessel_flag'].isna() | (df['vessel_flag'] == '')).sum():,}")

    missing_flag = df['vessel_flag'].isna() | (df['vessel_flag'] == '')
    if missing_flag.any():
        mmsi_to_flag = vessel_lookup["flag_ais"].to_dict()
        df.loc[missing_flag, "vessel_flag"] = df.loc[missing_flag, "mmsi"].map(mmsi_to_flag)
        logger.info(f"  Filled {missing_flag.sum():,} vessel_flags from registry")

    missing_type = df['vessel_type'].isna() | (df['vessel_type'] == '')
    if missing_type.any():
        mmsi_to_class = vessel_lookup["vessel_class"].to_dict()
        df.loc[missing_type, "vessel_type"] = df.loc[missing_type, "mmsi"].map(mmsi_to_class)
        logger.info(f"  Filled {missing_type.sum():,} vessel_types from registry")

    # ===== 2.3: COORDINATE VALIDATION =====
    logger.info("--- Step 2.3: Coordinate Validation ---")
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")

    bad_coords = df["lat"].isna() | df["lon"].isna()
    logger.info(f"  Invalid coords: {bad_coords.sum():,}")

    in_bbox = (
        (df["lat"] >= LAT_MIN - 2) & (df["lat"] <= LAT_MAX + 2) &
        (df["lon"] >= LON_MIN - 2) & (df["lon"] <= LON_MAX + 2)
    )
    outside_bbox = ~in_bbox & ~bad_coords
    logger.info(f"  Outside Indonesia bbox (±2°): {outside_bbox.sum():,}")
    df["in_indonesia_bbox"] = in_bbox

    # ===== 2.4: DATE NORMALIZATION =====
    logger.info("--- Step 2.4: Date Normalization ---")
    df["start_time"] = pd.to_datetime(df["start_time"], utc=True)
    df["end_time"] = pd.to_datetime(df["end_time"], utc=True)

    wib_offset = pd.Timedelta(hours=7)
    start_wib = df["start_time"] + wib_offset

    df["hour_of_day"] = start_wib.dt.hour
    df["day_of_week"] = start_wib.dt.dayofweek
    df["month"] = start_wib.dt.month
    df["year"] = start_wib.dt.year
    df["is_nighttime"] = df["hour_of_day"].isin(list(range(0, 6)) + list(range(18, 24)))
    df["is_weekend"] = df["day_of_week"].isin([5, 6])
    df["season"] = df["month"].map(lambda m: "wet" if m in [11, 12, 1, 2, 3] else "dry")

    df["duration_hours"] = (df["end_time"] - df["start_time"]).dt.total_seconds() / 3600
    df["duration_hours"] = df["duration_hours"].clip(lower=0)

    logger.info(f"  Date range: {df['start_time'].min()} → {df['start_time'].max()}")
    logger.info(f"  Year distribution:\n{df['year'].value_counts().sort_index().to_string()}")

    # ===== 2.5: FLAG STANDARDIZATION =====
    logger.info("--- Step 2.5: Flag Standardization ---")
    df["vessel_flag"] = df["vessel_flag"].str.upper().map(lambda x: FLAG_MAP.get(x, x))
    df["is_domestic"] = df["vessel_flag"] == "IDN"
    df["is_foreign"] = ~df["is_domestic"]

    logger.info(f"  Flag distribution:\n{df['vessel_flag'].value_counts().head(10).to_string()}")

    # ===== 2.6: OUTLIER REMOVAL =====
    logger.info("--- Step 2.6: Outlier Handling ---")

    duration_caps = {
        "fishing": 72, "loitering": 168, "encounter": 48, "port_visit": 720,
    }

    for etype, cap in duration_caps.items():
        mask = (df["event_type"] == etype) & (df["duration_hours"] > cap)
        capped = mask.sum()
        if capped > 0:
            p99 = df.loc[df["event_type"] == etype, "duration_hours"].quantile(0.99)
            actual_cap = min(cap, p99 * 1.5)
            df.loc[mask, "duration_hours"] = actual_cap
            logger.info(f"  {etype}: capped {capped:,} events > {cap}h (actual cap: {actual_cap:.1f}h)")

    df["implied_speed_knots"] = np.where(
        df["duration_hours"] > 0,
        df["total_distance_km"].fillna(0) / (df["duration_hours"] * 1.852),
        np.nan
    )
    speed_outliers = (df["implied_speed_knots"] > 30).sum()
    df["speed_outlier"] = df["implied_speed_knots"] > 30
    logger.info(f"  Speed outliers (>30 knots): {speed_outliers:,}")

    # ===== FINAL VALIDATION =====
    logger.info(f"--- Final Validation ---")
    logger.info(f"Final shape: {len(df):,} rows × {len(df.columns)} cols")
    logger.info(f"By event type:\n{df['event_type'].value_counts().to_string()}")

    output_path = OUTPUT_DIR / GFW_EVENTS_CLEAN
    df.to_parquet(output_path, index=False, compression="snappy")
    sz = output_path.stat().st_size / 1024 / 1024
    logger.info(f"✅ Saved to {output_path} ({sz:.1f} MB)")

    del df, vessel_lookup; gc.collect()


if __name__ == "__main__":
    run_step_2_2_to_2_6()
