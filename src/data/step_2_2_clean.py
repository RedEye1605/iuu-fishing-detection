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

logger = logging.getLogger(__name__)

INPUT_DIR = Path("data/processed")
OUTPUT_DIR = Path("data/processed")

# Indonesia bounding box (generous for EEZ buffer)
LAT_MIN, LAT_MAX = -11.5, 6.5
LON_MIN, LON_MAX = 95.0, 141.5

FLAG_MAP = {
    "IDN": "IDN", "INA": "IDN",
    "CHN": "CHN", "CHINA": "CHN",
    "TWN": "TWN", "ROC": "TWN",
    "VNM": "VNM", "VIETNAM": "VNM",
    "MYS": "MYS", "MALAYSIA": "MYS",
    "PHL": "PHL", "PNG": "PNG",
    "THA": "THA", "KOR": "KOR",
    "SGP": "SGP", "LBR": "LBR",
    "PAN": "PAN", "AUS": "AUS",
    "JPN": "JPN", "IND": "IND",
    "SWE": "SWE", "BES": "BES",
    "HKG": "HKG", "KHM": "KHM",
    "MMR": "MMR",
}


def run_step_2_2_to_2_6():
    """Execute Steps 2.2-2.6 on GFW events."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    
    print("=" * 60)
    print("STEPS 2.2–2.6: CLEAN & VALIDATE GFW EVENTS")
    print("=" * 60)
    
    # Load deduped events
    df = pd.read_parquet(INPUT_DIR / "gfw_events_dedup.parquet")
    print(f"Loaded: {len(df):,} rows × {len(df.columns)} cols")
    
    # Load vessel registry for enrichment
    df_vessels = pd.read_parquet(INPUT_DIR / "vessel_registry_dedup.parquet")
    vessel_lookup = df_vessels.drop_duplicates(subset=["mmsi"]).set_index("mmsi")
    print(f"Vessel registry: {len(vessel_lookup):,} unique MMSIs")
    del df_vessels; gc.collect()
    
    # ===== 2.2: NULL HANDLING =====
    print(f"\n--- Step 2.2: Null Handling ---")
    print(f"Null MMSI: {df['mmsi'].isna().sum():,}")
    print(f"Empty MMSI: {(df['mmsi'] == '').sum():,}")
    print(f"Null lat/lon: {df['lat'].isna().sum():,} / {df['lon'].isna().sum():,}")
    print(f"Null vessel_flag: {(df['vessel_flag'].isna() | (df['vessel_flag'] == '')).sum():,}")
    
    # Fill vessel_flag from registry where missing
    missing_flag = df['vessel_flag'].isna() | (df['vessel_flag'] == '')
    if missing_flag.any():
        mmsi_to_flag = vessel_lookup["flag_ais"].to_dict()
        df.loc[missing_flag, "vessel_flag"] = df.loc[missing_flag, "mmsi"].map(mmsi_to_flag)
        print(f"  Filled {missing_flag.sum():,} vessel_flags from registry")
    
    # Fill vessel_type from registry
    missing_type = df['vessel_type'].isna() | (df['vessel_type'] == '')
    if missing_type.any():
        mmsi_to_class = vessel_lookup["vessel_class"].to_dict()
        df.loc[missing_type, "vessel_type"] = df.loc[missing_type, "mmsi"].map(mmsi_to_class)
        print(f"  Filled {missing_type.sum():,} vessel_types from registry")
    
    # ===== 2.3: COORDINATE VALIDATION =====
    print(f"\n--- Step 2.3: Coordinate Validation ---")
    before = len(df)
    
    # Basic range check
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    
    bad_coords = df["lat"].isna() | df["lon"].isna()
    print(f"  Invalid coords: {bad_coords.sum():,}")
    
    # Indonesia bounding box check (with buffer for edge cases)
    in_bbox = (
        (df["lat"] >= LAT_MIN - 2) & (df["lat"] <= LAT_MAX + 2) &
        (df["lon"] >= LON_MIN - 2) & (df["lon"] <= LON_MAX + 2)
    )
    outside_bbox = ~in_bbox & ~bad_coords
    print(f"  Outside Indonesia bbox (±2°): {outside_bbox.sum():,}")
    
    # Keep everything for now but flag out-of-bbox
    df["in_indonesia_bbox"] = in_bbox
    
    # ===== 2.4: DATE NORMALIZATION =====
    print(f"\n--- Step 2.4: Date Normalization ---")
    df["start_time"] = pd.to_datetime(df["start_time"], utc=True)
    df["end_time"] = pd.to_datetime(df["end_time"], utc=True)
    
    # Derive temporal features (in WIB = UTC+7)
    wib_offset = pd.Timedelta(hours=7)
    start_wib = df["start_time"] + wib_offset
    
    df["hour_of_day"] = start_wib.dt.hour
    df["day_of_week"] = start_wib.dt.dayofweek
    df["month"] = start_wib.dt.month
    df["year"] = start_wib.dt.year
    df["is_nighttime"] = df["hour_of_day"].isin(list(range(0, 6)) + list(range(18, 24)))
    df["is_weekend"] = df["day_of_week"].isin([5, 6])
    
    # Season: wet (Nov-Mar), dry (Apr-Oct)
    df["season"] = df["month"].map(lambda m: "wet" if m in [11, 12, 1, 2, 3] else "dry")
    
    # Duration
    df["duration_hours"] = (df["end_time"] - df["start_time"]).dt.total_seconds() / 3600
    df["duration_hours"] = df["duration_hours"].clip(lower=0)
    
    print(f"  Date range: {df['start_time'].min()} → {df['start_time'].max()}")
    print(f"  Year distribution:")
    print(df["year"].value_counts().sort_index().to_string())
    
    # ===== 2.5: FLAG STANDARDIZATION =====
    print(f"\n--- Step 2.5: Flag Standardization ---")
    df["vessel_flag"] = df["vessel_flag"].str.upper().map(lambda x: FLAG_MAP.get(x, x))
    df["is_domestic"] = df["vessel_flag"] == "IDN"
    df["is_foreign"] = ~df["is_domestic"]
    
    print(f"  Flag distribution:")
    print(df["vessel_flag"].value_counts().head(10).to_string())
    
    # ===== 2.6: OUTLIER REMOVAL =====
    print(f"\n--- Step 2.6: Outlier Handling ---")
    
    # Duration caps by event type
    duration_caps = {
        "fishing": 72,       # 3 days max for fishing event
        "loitering": 168,    # 1 week max for loitering
        "encounter": 48,     # 2 days max for encounter
        "port_visit": 720,   # 30 days max in port
    }
    
    for etype, cap in duration_caps.items():
        mask = (df["event_type"] == etype) & (df["duration_hours"] > cap)
        capped = mask.sum()
        if capped > 0:
            p99 = df.loc[df["event_type"] == etype, "duration_hours"].quantile(0.99)
            actual_cap = min(cap, p99 * 1.5)
            df.loc[mask, "duration_hours"] = actual_cap
            print(f"  {etype}: capped {capped:,} events > {cap}h (actual cap: {actual_cap:.1f}h)")
    
    # Speed outliers (flag, don't remove)
    df["implied_speed_knots"] = np.where(
        df["duration_hours"] > 0,
        df["total_distance_km"].fillna(0) / (df["duration_hours"] * 1.852),  # km/h → knots
        np.nan
    )
    speed_outliers = (df["implied_speed_knots"] > 30).sum()
    df["speed_outlier"] = df["implied_speed_knots"] > 30
    print(f"  Speed outliers (>30 knots): {speed_outliers:,}")
    
    # ===== FINAL VALIDATION =====
    print(f"\n--- Final Validation ---")
    print(f"Final shape: {len(df):,} rows × {len(df.columns)} cols")
    print(f"\nBy event type:")
    print(df["event_type"].value_counts().to_string())
    print(f"\nNull summary:")
    null_counts = df.isnull().sum()
    null_cols = null_counts[null_counts > 0].sort_values(ascending=False)
    for col, cnt in null_cols.head(15).items():
        print(f"  {col}: {cnt:,} ({cnt/len(df)*100:.1f}%)")
    
    # Save
    output_path = OUTPUT_DIR / "gfw_events_clean.parquet"
    df.to_parquet(output_path, index=False, compression="snappy")
    sz = output_path.stat().st_size / 1024 / 1024
    print(f"\n✅ Saved to {output_path} ({sz:.1f} MB)")
    
    del df, vessel_lookup; gc.collect()


if __name__ == "__main__":
    run_step_2_2_to_2_6()
