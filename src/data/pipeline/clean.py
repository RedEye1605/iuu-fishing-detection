"""
Phase 2: Dedup, Validate, and Normalize ALL Data

Merges deduplication and cleaning from previous step_2_1_dedup.py,
step_2_2_clean.py, and step_2_7_clean_rest.py.

Functions:
- dedup_events: Dedup GFW events on event_id
- dedup_sar: Dedup SAR presence + MMSI filter
- dedup_effort: Dedup fishing effort + sum hours
- dedup_zenodo: Dedup Zenodo grid effort (memory-efficient)
- clean_events: Null handling, coords, dates, flags, outliers on events
- clean_grid_data: Clean SAR, effort, zenodo (flag standardize, dates, coords)
- run_clean_all: Run all clean functions, return mapping
"""

from __future__ import annotations

import gc
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from ..constants import (
    PROCESSED_DIR, FLAG_MAP, INDONESIA_BBOX, DATA_START,
    GFW_EVENTS_FLAT, SAR_PRESENCE_FLAT, FISHING_EFFORT_FLAT, VESSEL_REGISTRY,
    ZENODO_EFFORT_FLAT,
    GFW_EVENTS_DEDUP, SAR_PRESENCE_DEDUP, FISHING_EFFORT_DEDUP,
    ZENODO_EFFORT_DEDUP, VESSEL_REGISTRY_DEDUP,
    GFW_EVENTS_CLEAN, SAR_PRESENCE_CLEAN, FISHING_EFFORT_CLEAN, ZENODO_EFFORT_CLEAN,
)

logger = logging.getLogger(__name__)

LAT_MIN = INDONESIA_BBOX["lat_min"]
LAT_MAX = INDONESIA_BBOX["lat_max"]
LON_MIN = INDONESIA_BBOX["lon_min"]
LON_MAX = INDONESIA_BBOX["lon_max"]


# =========================================================================
# Dedup functions
# =========================================================================

def dedup_events() -> Path:
    """Dedup GFW events on event_id.

    Returns:
        Path to gfw_events_dedup.parquet
    """
    logger.info("Loading gfw_events_flat...")
    df = pd.read_parquet(PROCESSED_DIR / GFW_EVENTS_FLAT)
    before = len(df)

    dupes = df.duplicated(subset=["event_id"], keep=False).sum()
    logger.info(f"  Before: {before:,} rows, duplicate event_ids: {dupes:,}")

    df = df.drop_duplicates(subset=["event_id"], keep="first")
    logger.info(f"  After dedup: {len(df):,} rows (removed {before - len(df):,})")

    out = PROCESSED_DIR / GFW_EVENTS_DEDUP
    df.to_parquet(out, index=False)
    del df; gc.collect()
    logger.info(f"  ✅ {GFW_EVENTS_DEDUP}")
    return out


def dedup_sar() -> Path:
    """Dedup SAR presence: drop grid-only rows (no MMSI), then dedup on key.

    Returns:
        Path to sar_presence_dedup.parquet
    """
    logger.info("Loading sar_presence_flat...")
    df = pd.read_parquet(PROCESSED_DIR / SAR_PRESENCE_FLAT)
    before = len(df)

    no_mmsi = (df["mmsi"] == "").sum()
    logger.info(f"  Before: {before:,} rows, no MMSI: {no_mmsi:,}")
    df = df[df["mmsi"] != ""].copy()
    logger.info(f"  After MMSI filter: {len(df):,}")

    dupes = df.duplicated(subset=["mmsi", "date", "lat", "lon"], keep=False).sum()
    logger.info(f"  Duplicate keys: {dupes:,}")
    df = df.drop_duplicates(subset=["mmsi", "date", "lat", "lon"], keep="first")
    logger.info(f"  After dedup: {len(df):,}")

    out = PROCESSED_DIR / SAR_PRESENCE_DEDUP
    df.to_parquet(out, index=False)
    del df; gc.collect()
    logger.info(f"  ✅ {SAR_PRESENCE_DEDUP}")
    return out


def dedup_effort() -> Path:
    """Dedup fishing effort: sum hours if duplicate keys.

    Returns:
        Path to fishing_effort_dedup.parquet
    """
    logger.info("Loading fishing_effort_flat...")
    df = pd.read_parquet(PROCESSED_DIR / FISHING_EFFORT_FLAT)
    before = len(df)

    dupes = df.duplicated(subset=["mmsi", "date", "lat", "lon"], keep=False).sum()
    logger.info(f"  Before: {before:,} rows, duplicate keys: {dupes:,}")

    if dupes > 0:
        df = df.groupby(["mmsi", "date", "lat", "lon"], as_index=False).agg({
            "fishing_hours": "sum",
            "flag": "first", "geartype": "first", "vessel_type": "first",
            "vessel_id": "first", "vessel_name": "first", "callsign": "first",
            "entry_timestamp": "first", "exit_timestamp": "first",
        })
        logger.info(f"  After dedup+sum: {len(df):,}")

    out = PROCESSED_DIR / FISHING_EFFORT_DEDUP
    df.to_parquet(out, index=False)
    del df; gc.collect()
    logger.info(f"  ✅ {FISHING_EFFORT_DEDUP}")
    return out


def dedup_zenodo() -> Path:
    """Dedup Zenodo grid effort with memory-efficient chunked processing.

    Returns:
        Path to zenodo_effort_dedup.parquet
    """
    import pyarrow.parquet as pq

    logger.info("Loading zenodo_effort_flat (memory-efficient)...")
    pf = pq.ParquetFile(PROCESSED_DIR / ZENODO_EFFORT_FLAT)
    batch_size = 2_000_000

    chunks = []
    total_before = 0
    total_dupes = 0

    for batch in pf.iter_batches(batch_size=batch_size):
        df_chunk = batch.to_pandas()
        total_before += len(df_chunk)

        dupes = df_chunk.duplicated(
            subset=["date", "cell_ll_lat", "cell_ll_lon", "flag", "geartype"],
            keep=False
        ).sum()
        total_dupes += dupes

        if dupes > 0:
            df_chunk = df_chunk.groupby(
                ["date", "cell_ll_lat", "cell_ll_lon", "flag", "geartype"],
                as_index=False
            ).agg({"hours": "sum", "fishing_hours": "sum", "mmsi_present": "max",
                   "year": "first", "month": "first"})

        chunks.append(df_chunk)
        del df_chunk; gc.collect()

    df = pd.concat(chunks, ignore_index=True)
    logger.info(f"  Before: {total_before:,}, dupes: {total_dupes:,}, after: {len(df):,}")

    out = PROCESSED_DIR / ZENODO_EFFORT_DEDUP
    df.to_parquet(out, index=False)
    del df, chunks; gc.collect()
    logger.info(f"  ✅ {ZENODO_EFFORT_DEDUP}")
    return out


# =========================================================================
# Clean functions
# =========================================================================

def clean_events() -> Path:
    """Clean GFW events: null handling, coordinate validation, date normalization,
    flag standardization, and outlier removal.

    Returns:
        Path to gfw_events_clean.parquet
    """
    logger.info("Loading deduped events...")
    df = pd.read_parquet(PROCESSED_DIR / GFW_EVENTS_DEDUP)
    logger.info(f"Loaded: {len(df):,} rows × {len(df.columns)} cols")

    # Load vessel registry for enrichment
    df_vessels = pd.read_parquet(PROCESSED_DIR / VESSEL_REGISTRY_DEDUP)
    df_vessels["mmsi"] = df_vessels["mmsi"].astype(str)
    vessel_lookup = df_vessels.drop_duplicates(subset=["mmsi"]).set_index("mmsi")
    logger.info(f"Vessel registry: {len(vessel_lookup):,} unique MMSIs")
    del df_vessels; gc.collect()

    # --- Null handling ---
    logger.info("--- Null Handling ---")
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

    # --- Coordinate validation ---
    logger.info("--- Coordinate Validation ---")
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

    # --- Date normalization ---
    logger.info("--- Date Normalization ---")
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

    # Cyclical encoding for temporal features (sin/cos preserves adjacency)
    df["hour_sin"] = np.sin(2 * np.pi * df["hour_of_day"] / 24).astype(np.float32)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour_of_day"] / 24).astype(np.float32)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12).astype(np.float32)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12).astype(np.float32)

    df["duration_hours"] = (df["end_time"] - df["start_time"]).dt.total_seconds() / 3600
    df["duration_hours"] = df["duration_hours"].clip(lower=0)

    logger.info(f"  Date range: {df['start_time'].min()} → {df['start_time'].max()}")

    # --- Filter pre-2020 outliers ---
    data_start = pd.Timestamp(DATA_START, tz="UTC")
    pre_start = df["start_time"] < data_start
    n_pre_start = pre_start.sum()
    if n_pre_start > 0:
        df = df[~pre_start].copy()
        logger.info(f"  Removed {n_pre_start:,} events before {DATA_START}")

    # --- Flag standardization ---
    logger.info("--- Flag Standardization ---")
    df["vessel_flag"] = df["vessel_flag"].str.upper().map(lambda x: FLAG_MAP.get(x, x))
    df["is_domestic"] = df["vessel_flag"] == "IDN"
    df["is_foreign"] = ~df["is_domestic"]

    # Flag-of-Convenience (FoC): ITF-listed countries with minimal regulatory oversight
    # Boerder et al. (2018): FoC-flagged vessels ~3x more likely involved in IUU fishing
    from ..constants import FOC_FLAGS
    df["is_foc_flag"] = df["vessel_flag"].isin(FOC_FLAGS).astype(int)
    n_foc = df["is_foc_flag"].sum()
    logger.info(f"  FoC-flagged events: {n_foc:,} ({n_foc/len(df)*100:.1f}%)")

    logger.info(f"  Flag distribution:\n{df['vessel_flag'].value_counts().head(10).to_string()}")

    # --- Outlier removal ---
    logger.info("--- Outlier Handling ---")
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
            logger.info(f"  {etype}: capped {capped:,} events > {cap}h")

    df["implied_speed_knots"] = np.where(
        df["duration_hours"] > 0,
        df["total_distance_km"].fillna(0) / (df["duration_hours"] * 1.852),
        np.nan
    )
    df["speed_outlier"] = df["implied_speed_knots"] > 30
    logger.info(f"  Speed outliers (>30 knots): {df['speed_outlier'].sum():,}")

    # --- Save ---
    logger.info(f"Final shape: {len(df):,} rows × {len(df.columns)} cols")
    out = PROCESSED_DIR / GFW_EVENTS_CLEAN
    df.to_parquet(out, index=False, compression="snappy")
    logger.info(f"✅ Saved to {out} ({out.stat().st_size / 1024 / 1024:.1f} MB)")
    del df, vessel_lookup; gc.collect()
    return out


def clean_grid_data() -> None:
    """Clean SAR, effort, and zenodo grid data: flag standardize, dates, coords."""
    # SAR and Effort
    for name, in_name, out_name in [
        ("SAR", SAR_PRESENCE_DEDUP, SAR_PRESENCE_CLEAN),
        ("Effort", FISHING_EFFORT_DEDUP, FISHING_EFFORT_CLEAN),
    ]:
        logger.info(f"\n--- Cleaning {name} ---")
        df = pd.read_parquet(PROCESSED_DIR / in_name)
        logger.info(f"  Loaded: {len(df):,}")

        df["flag"] = df["flag"].str.upper().map(lambda x: FLAG_MAP.get(x, x))
        df["is_domestic"] = df["flag"] == "IDN"

        df["date_parsed"] = pd.to_datetime(df["date"], format="mixed", errors="coerce")
        df["year"] = df["date_parsed"].dt.year
        df["month"] = df["date_parsed"].dt.month
        df["season"] = df["month"].map(lambda m: "wet" if m in [11, 12, 1, 2, 3] else "dry")

        df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
        df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
        bad = df["lat"].isna() | df["lon"].isna()
        if bad.any():
            logger.warning(f"  Dropping {bad.sum():,} rows with invalid coords")
            df = df[~bad]

        out = PROCESSED_DIR / out_name
        df.to_parquet(out, index=False)
        logger.info(f"  ✅ {out_name} ({out.stat().st_size / 1024 / 1024:.1f} MB, {len(df):,} rows)")
        del df; gc.collect()

    # Zenodo — memory efficient chunked processing
    logger.info(f"\n--- Cleaning Zenodo Effort ---")
    import pyarrow.parquet as pq
    import pyarrow as pa

    pf = pq.ParquetFile(PROCESSED_DIR / ZENODO_EFFORT_DEDUP)
    out_path = PROCESSED_DIR / ZENODO_EFFORT_CLEAN
    writer = None
    total = 0

    for batch in pf.iter_batches(batch_size=1_500_000):
        df = batch.to_pandas()
        total += len(df)

        df["flag"] = df["flag"].str.upper().map(lambda x: FLAG_MAP.get(x, x))
        df["is_domestic"] = df["flag"] == "IDN"
        df["season"] = df["month"].map(lambda m: "wet" if m in [11, 12, 1, 2, 3] else "dry")
        df["cell_ll_lat"] = pd.to_numeric(df["cell_ll_lat"], errors="coerce")
        df["cell_ll_lon"] = pd.to_numeric(df["cell_ll_lon"], errors="coerce")

        table = pa.Table.from_pandas(df)
        if writer is None:
            writer = pq.ParquetWriter(out_path, table.schema)
        writer.write_table(table)
        del df, table; gc.collect()

    if writer:
        writer.close()
    logger.info(f"  ✅ {ZENODO_EFFORT_CLEAN} ({out_path.stat().st_size / 1024 / 1024:.1f} MB, {total:,} rows)")


def run_clean_all() -> dict[str, Path]:
    """Run all dedup and clean functions.

    Returns:
        Dict mapping dataset name to output parquet path.
    """
    results = {}

    # Dedup phase
    results["gfw_events_dedup"] = dedup_events()
    results["sar_dedup"] = dedup_sar()
    results["effort_dedup"] = dedup_effort()
    results["zenodo_dedup"] = dedup_zenodo()

    # Also dedup vessel registry (already done in extract, just verify)
    logger.info("Verifying vessel registry...")
    df_v = pd.read_parquet(PROCESSED_DIR / VESSEL_REGISTRY)
    df_v["mmsi"] = df_v["mmsi"].astype(str)
    dupes = df_v.duplicated(subset=["mmsi"], keep=False).sum()
    logger.info(f"  {len(df_v):,} rows, duplicate MMSIs: {dupes:,}")
    out = PROCESSED_DIR / VESSEL_REGISTRY_DEDUP
    df_v.to_parquet(out, index=False)
    results["vessel_registry_dedup"] = out
    del df_v; gc.collect()

    # Clean phase
    results["gfw_events_clean"] = clean_events()
    clean_grid_data()

    logger.info("✅ Clean phase complete")
    return results
