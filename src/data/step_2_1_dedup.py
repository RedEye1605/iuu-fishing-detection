"""
Phase 2 Step 2.1: Deduplication

GFW Events: Dedup on event_id
SAR Presence: Dedup on (mmsi, date, lat, lon), drop grid-only (empty mmsi)
Fishing Effort: Dedup on (mmsi, date, lat, lon), sum hours if duplicate
Vessel Registry: Keep latest year per MMSI (already done in Phase 1)
Zenodo Effort: Dedup on (date, cell_ll_lat, cell_ll_lon, flag, geartype)
"""

from __future__ import annotations

import gc
import logging
from pathlib import Path

import pandas as pd

from .constants import (
    PROCESSED_DIR,
    GFW_EVENTS_FLAT, SAR_PRESENCE_FLAT, FISHING_EFFORT_FLAT, VESSEL_REGISTRY,
    GFW_EVENTS_DEDUP, SAR_PRESENCE_DEDUP, FISHING_EFFORT_DEDUP, ZENODO_EFFORT_DEDUP, VESSEL_REGISTRY_DEDUP,
    ZENODO_EFFORT_FLAT,
)

logger = logging.getLogger(__name__)

INPUT_DIR = PROCESSED_DIR
OUTPUT_DIR = PROCESSED_DIR


def dedup_gfw_events() -> pd.DataFrame:
    """Step 2.1a: Dedup GFW events on event_id."""
    logger.info("Loading gfw_events_flat...")
    df = pd.read_parquet(INPUT_DIR / GFW_EVENTS_FLAT)
    before = len(df)

    dupes = df.duplicated(subset=["event_id"], keep=False).sum()
    logger.info(f"  Before: {before:,} rows, duplicate event_ids: {dupes:,}")

    df = df.drop_duplicates(subset=["event_id"], keep="first")
    logger.info(f"  After dedup: {len(df):,} rows (removed {before - len(df):,})")
    return df


def dedup_sar_presence() -> pd.DataFrame:
    """Step 2.1b: Dedup SAR presence. Drop grid-only rows (no MMSI), then dedup on key."""
    logger.info("Loading sar_presence_flat...")
    df = pd.read_parquet(INPUT_DIR / SAR_PRESENCE_FLAT)
    before = len(df)

    no_mmsi = (df["mmsi"] == "").sum()
    logger.info(f"  Before: {before:,} rows, no MMSI: {no_mmsi:,}")
    df = df[df["mmsi"] != ""].copy()
    logger.info(f"  After MMSI filter: {len(df):,}")

    dupes = df.duplicated(subset=["mmsi", "date", "lat", "lon"], keep=False).sum()
    logger.info(f"  Duplicate keys: {dupes:,}")
    df = df.drop_duplicates(subset=["mmsi", "date", "lat", "lon"], keep="first")
    logger.info(f"  After dedup: {len(df):,}")
    return df


def dedup_fishing_effort() -> pd.DataFrame:
    """Step 2.1c: Dedup fishing effort. Sum hours if duplicate keys."""
    logger.info("Loading fishing_effort_flat...")
    df = pd.read_parquet(INPUT_DIR / FISHING_EFFORT_FLAT)
    before = len(df)

    dupes = df.duplicated(subset=["mmsi", "date", "lat", "lon"], keep=False).sum()
    logger.info(f"  Before: {before:,} rows, duplicate keys: {dupes:,}")

    if dupes > 0:
        df = df.groupby(["mmsi", "date", "lat", "lon"], as_index=False).agg({
            "fishing_hours": "sum",
            "flag": "first",
            "geartype": "first",
            "vessel_type": "first",
            "vessel_id": "first",
            "vessel_name": "first",
            "callsign": "first",
            "entry_timestamp": "first",
            "exit_timestamp": "first",
        })
        logger.info(f"  After dedup+sum: {len(df):,} (removed {before - len(df):,})")
    else:
        logger.info("  No duplicates found")

    return df


def dedup_zenodo_effort() -> pd.DataFrame:
    """Step 2.1d: Dedup Zenodo grid effort. Process year-by-year to save memory."""
    logger.info("Loading zenodo_effort_flat (memory-efficient)...")

    import pyarrow.parquet as pq

    pf = pq.ParquetFile(INPUT_DIR / ZENODO_EFFORT_FLAT)
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
        del df_chunk
        gc.collect()

    df = pd.concat(chunks, ignore_index=True)
    logger.info(f"  Before: {total_before:,}, dupes: {total_dupes:,}, after: {len(df):,}")
    return df


def dedup_vessel_registry() -> pd.DataFrame:
    """Step 2.1e: Vessel registry already deduped in Phase 1. Just load and verify."""
    logger.info("Loading vessel_registry...")
    df = pd.read_parquet(INPUT_DIR / VESSEL_REGISTRY)
    dupes = df.duplicated(subset=["mmsi"], keep=False).sum()
    logger.info(f"  {len(df):,} rows, duplicate MMSIs: {dupes:,}")
    # Ensure MMSI is string
    df["mmsi"] = df["mmsi"].astype(str)
    return df


def run_step_2_1():
    """Execute Phase 2 Step 2.1: Deduplication."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    logger.info("=" * 60 + "\nSTEP 2.1 — DEDUPLICATION\n" + "=" * 60)

    # 2.1a
    df_events = dedup_gfw_events()
    df_events.to_parquet(OUTPUT_DIR / GFW_EVENTS_DEDUP, index=False)
    logger.info(f"  ✅ {GFW_EVENTS_DEDUP} ({len(df_events):,} rows)")
    del df_events; gc.collect()

    # 2.1b
    df_sar = dedup_sar_presence()
    df_sar.to_parquet(OUTPUT_DIR / SAR_PRESENCE_DEDUP, index=False)
    logger.info(f"  ✅ {SAR_PRESENCE_DEDUP} ({len(df_sar):,} rows)")
    del df_sar; gc.collect()

    # 2.1c
    df_effort = dedup_fishing_effort()
    df_effort.to_parquet(OUTPUT_DIR / FISHING_EFFORT_DEDUP, index=False)
    logger.info(f"  ✅ {FISHING_EFFORT_DEDUP} ({len(df_effort):,} rows)")
    del df_effort; gc.collect()

    # 2.1d
    df_zenodo = dedup_zenodo_effort()
    df_zenodo.to_parquet(OUTPUT_DIR / ZENODO_EFFORT_DEDUP, index=False)
    logger.info(f"  ✅ {ZENODO_EFFORT_DEDUP} ({len(df_zenodo):,} rows)")
    del df_zenodo; gc.collect()

    # 2.1e
    df_vessels = dedup_vessel_registry()
    df_vessels.to_parquet(OUTPUT_DIR / VESSEL_REGISTRY_DEDUP, index=False)
    logger.info(f"  ✅ {VESSEL_REGISTRY_DEDUP} ({len(df_vessels):,} rows)")

    logger.info("✅ Step 2.1 complete!")


if __name__ == "__main__":
    run_step_2_1()
