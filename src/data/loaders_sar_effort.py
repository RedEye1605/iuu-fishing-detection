"""
Phase 1 Step 1.2: Flatten SAR Presence & Fishing Effort (GFW 4Wings)

Input: 4wings_sar_presence_indonesia_corrected.json.gz (1.2M records)
       4wings_fishing_effort_indonesia_corrected.json.gz (890K records)
Output: data/processed/sar_presence_flat.parquet
        data/processed/fishing_effort_flat.parquet
"""

from __future__ import annotations

import gzip
import json
import logging
from pathlib import Path

import pandas as pd

from .constants import GFW_RAW_DIR, PROCESSED_DIR, GFW_SAR_FILE, GFW_EFFORT_FILE, SAR_PRESENCE_FLAT, FISHING_EFFORT_FLAT

logger = logging.getLogger(__name__)


def flatten_sar_presence() -> pd.DataFrame:
    """Flatten SAR presence data."""
    logger.info("Loading SAR presence...")
    with gzip.open(GFW_RAW_DIR / GFW_SAR_FILE, "rt") as f:
        data = json.load(f)

    metadata = data.get("metadata", {})
    entries = data.get("entries", [])
    logger.info(f"  Metadata: {metadata}")
    logger.info(f"  Entries: {len(entries)}")

    all_records = []
    sar_key = "public-global-sar-presence:v4.0"

    for i, entry in enumerate(entries):
        records = entry.get(sar_key, [])
        logger.info(f"  Entry {i}: {len(records):,} records")
        for rec in records:
            all_records.append({
                "mmsi": rec.get("mmsi", ""),
                "date": rec.get("date", ""),
                "lat": rec.get("lat"),
                "lon": rec.get("lon"),
                "detections": rec.get("detections", 0),
                "flag": rec.get("flag", ""),
                "geartype": rec.get("geartype", ""),
                "vessel_type": rec.get("vesselType", ""),
                "vessel_id": rec.get("vesselId", ""),
                "vessel_name": rec.get("shipName", ""),
                "callsign": rec.get("callsign", ""),
                "entry_timestamp": rec.get("entryTimestamp", ""),
                "exit_timestamp": rec.get("exitTimestamp", ""),
            })

    df = pd.DataFrame(all_records)
    logger.info(f"  Total SAR records: {len(df):,}")
    return df


def flatten_fishing_effort() -> pd.DataFrame:
    """Flatten fishing effort data."""
    logger.info("Loading fishing effort...")
    with gzip.open(GFW_RAW_DIR / GFW_EFFORT_FILE, "rt") as f:
        data = json.load(f)

    metadata = data.get("metadata", {})
    entries = data.get("entries", [])
    logger.info(f"  Metadata: {metadata}")
    logger.info(f"  Entries: {len(entries)}")

    all_records = []
    eff_key = "public-global-fishing-effort:v4.0"

    for i, entry in enumerate(entries):
        records = entry.get(eff_key, [])
        logger.info(f"  Entry {i}: {len(records):,} records")
        for rec in records:
            all_records.append({
                "mmsi": rec.get("mmsi", ""),
                "date": rec.get("date", ""),
                "lat": rec.get("lat"),
                "lon": rec.get("lon"),
                "fishing_hours": rec.get("hours", 0),
                "flag": rec.get("flag", ""),
                "geartype": rec.get("geartype", ""),
                "vessel_type": rec.get("vesselType", ""),
                "vessel_id": rec.get("vesselId", ""),
                "vessel_name": rec.get("shipName", ""),
                "callsign": rec.get("callsign", ""),
                "entry_timestamp": rec.get("entryTimestamp", ""),
                "exit_timestamp": rec.get("exitTimestamp", ""),
            })

    df = pd.DataFrame(all_records)
    logger.info(f"  Total effort records: {len(df):,}")
    return df


def run_step_1_2():
    """Execute Phase 1 Step 1.2."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # SAR Presence
    df_sar = flatten_sar_presence()
    logger.info(f"SAR Presence: {len(df_sar):,} rows, columns: {df_sar.columns.tolist()}")
    logger.info(f"Non-empty MMSI: {(df_sar['mmsi'] != '').sum():,} ({(df_sar['mmsi'] != '').mean()*100:.1f}%)")
    logger.info(f"Detections stats:\n{df_sar['detections'].describe().to_string()}")

    sar_path = PROCESSED_DIR / SAR_PRESENCE_FLAT
    df_sar.to_parquet(sar_path, index=False)
    logger.info(f"✅ Saved to {sar_path} ({sar_path.stat().st_size / 1024 / 1024:.1f} MB)")

    # Fishing Effort
    df_effort = flatten_fishing_effort()
    logger.info(f"Fishing Effort: {len(df_effort):,} rows, columns: {df_effort.columns.tolist()}")
    logger.info(f"Fishing hours stats:\n{df_effort['fishing_hours'].describe().to_string()}")
    logger.info(f"Geartype distribution:\n{df_effort['geartype'].value_counts().head(10).to_string()}")
    logger.info(f"Flag distribution:\n{df_effort['flag'].value_counts().head(5).to_string()}")

    eff_path = PROCESSED_DIR / FISHING_EFFORT_FLAT
    df_effort.to_parquet(eff_path, index=False)
    logger.info(f"✅ Saved to {eff_path} ({eff_path.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    run_step_1_2()
