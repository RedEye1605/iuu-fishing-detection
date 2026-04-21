"""
Phase 1 Step 1.2: Flatten SAR Presence & Fishing Effort (GFW 4Wings)

Input: 4wings_sar_presence_indonesia_corrected.json.gz (1.2M records)
       4wings_fishing_effort_indonesia_corrected.json.gz (890K records)
Output: data/processed/sar_presence_flat.parquet
        data/processed/fishing_effort_flat.parquet

Structure: {metadata: {...}, entries: [{dataset_key: [records]}, ...]}
Each entry is one year's worth of gridded data.
"""

from __future__ import annotations

import gzip
import json
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

DATA_DIR = Path("data/raw/gfw")
OUTPUT_DIR = Path("data/processed")


def flatten_sar_presence() -> pd.DataFrame:
    """Flatten SAR presence data."""
    logger.info("Loading SAR presence...")
    with gzip.open(DATA_DIR / "4wings_sar_presence_indonesia_corrected.json.gz", "rt") as f:
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
    with gzip.open(DATA_DIR / "4wings_fishing_effort_indonesia_corrected.json.gz", "rt") as f:
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
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # SAR Presence
    df_sar = flatten_sar_presence()
    
    print(f"\n{'='*60}")
    print("STEP 1.2a — SAR PRESENCE VALIDATION")
    print(f"{'='*60}")
    print(f"Total rows: {len(df_sar):,}")
    print(f"Columns: {df_sar.columns.tolist()}")
    print(f"\nDate range: {df_sar['date'].unique()[:10]}")
    print(f"\nMMSI coverage:")
    print(f"  Non-empty MMSI: {(df_sar['mmsi'] != '').sum():,} ({(df_sar['mmsi'] != '').mean()*100:.1f}%)")
    print(f"  Empty MMSI (grid-only): {(df_sar['mmsi'] == '').sum():,}")
    print(f"\nDetections stats:")
    print(df_sar['detections'].describe().to_string())
    print(f"\nFlag distribution (top 5):")
    flags = df_sar[df_sar['flag'] != '']['flag'].value_counts()
    print(flags.head(5).to_string() if len(flags) > 0 else "  No flag data")

    sar_path = OUTPUT_DIR / "sar_presence_flat.parquet"
    df_sar.to_parquet(sar_path, index=False)
    print(f"\n✅ Saved to {sar_path} ({sar_path.stat().st_size / 1024 / 1024:.1f} MB)")

    # Fishing Effort
    df_effort = flatten_fishing_effort()
    
    print(f"\n{'='*60}")
    print("STEP 1.2b — FISHING EFFORT VALIDATION")
    print(f"{'='*60}")
    print(f"Total rows: {len(df_effort):,}")
    print(f"Columns: {df_effort.columns.tolist()}")
    print(f"\nMMSI coverage:")
    print(f"  Non-empty MMSI: {(df_effort['mmsi'] != '').sum():,} ({(df_effort['mmsi'] != '').mean()*100:.1f}%)")
    print(f"\nFishing hours stats:")
    print(df_effort['fishing_hours'].describe().to_string())
    print(f"\nGeartype distribution:")
    print(df_effort['geartype'].value_counts().head(10).to_string())
    print(f"\nFlag distribution (top 5):")
    print(df_effort['flag'].value_counts().head(5).to_string())

    eff_path = OUTPUT_DIR / "fishing_effort_flat.parquet"
    df_effort.to_parquet(eff_path, index=False)
    print(f"\n✅ Saved to {eff_path} ({eff_path.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    run_step_1_2()
