"""
Phase 1 Steps 1.3-1.5: Vessel Registry, Zenodo Effort, Auxiliary Data

Step 1.3: Zenodo vessel registry → vessel_registry.parquet
Step 1.4: Zenodo monthly effort → zenodo_effort_flat.parquet  
Step 1.5: Weather, VIIRS, Ports, GIS → individual parquets
"""

from __future__ import annotations

import json
import logging
import zipfile
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

DATA_DIR = Path("data/raw")
OUTPUT_DIR = Path("data/processed")


def run_step_1_3():
    """Load Zenodo vessel registry, filter to relevant vessels."""
    logger.info("Loading vessel registry...")
    df = pd.read_csv(DATA_DIR / "zenodo" / "fishing-vessels-v3.csv", low_memory=False)
    print(f"  Total vessels: {len(df):,}")
    print(f"  Columns: {df.columns.tolist()}")

    # Find IDN-related vessels OR vessels appearing in our events
    is_idn = (
        df["flag_ais"].str.upper().str.contains("IDN", na=False) |
        df["flag_registry"].str.upper().str.contains("IDN", na=False) |
        df["flag_gfw"].str.upper().str.contains("IDN", na=False)
    )
    
    # Also keep vessels from flags we see in events (MYS, CHN, PAN, SGP, etc.)
    event_flags = ["IDN", "MYS", "CHN", "PAN", "SGP", "SWE", "TWN", "LBR", "BES", "HKG",
                   "KOR", "VNM", "THA", "PHL", "PNG", "AUS", "IND", "JPN", "MMR", "KHM"]
    flag_cols = ["flag_ais", "flag_registry", "flag_gfw"]
    
    is_relevant = pd.Series(False, index=df.index)
    for col in flag_cols:
        for flag in event_flags:
            is_relevant = is_relevant | df[col].str.upper().str.contains(flag, na=False)
    
    df_relevant = df[is_relevant].copy()
    print(f"  Relevant vessels (matching event flags): {len(df_relevant):,}")
    print(f"  Of which IDN: {is_idn.sum():,}")
    
    # Resolve best vessel class
    def best_class(row):
        for col in ["vessel_class_inferred", "vessel_class_gfw", "vessel_class_registry"]:
            val = row.get(col, "")
            if pd.notna(val) and val != "":
                return val
        return "UNKNOWN"
    
    def best_value(row, suffix):
        for prefix in [f"{suffix}_inferred", f"{suffix}_gfw", f"{suffix}_registry"]:
            val = row.get(prefix, "")
            if pd.notna(val) and val != "":
                return float(val)
        return None
    
    df_relevant = df_relevant.copy()
    df_relevant["vessel_class"] = df_relevant.apply(best_class, axis=1)
    df_relevant["length_m"] = df_relevant.apply(lambda r: best_value(r, "length_m"), axis=1)
    df_relevant["engine_power_kw"] = df_relevant.apply(lambda r: best_value(r, "engine_power_kw"), axis=1)
    df_relevant["tonnage_gt"] = df_relevant.apply(lambda r: best_value(r, "tonnage_gt"), axis=1)
    
    # Keep latest year per MMSI
    df_latest = df_relevant.sort_values("year", ascending=False).drop_duplicates(subset=["mmsi"], keep="first")
    print(f"  After dedup (latest per MMSI): {len(df_latest):,}")
    
    # Select output columns
    out_cols = ["mmsi", "year", "flag_ais", "flag_registry", "flag_gfw",
                "vessel_class", "length_m", "engine_power_kw", "tonnage_gt",
                "self_reported_fishing_vessel", "active_hours", "fishing_hours"]
    df_out = df_latest[out_cols].copy()
    
    output_path = OUTPUT_DIR / "vessel_registry.parquet"
    df_out.to_parquet(output_path, index=False)
    print(f"  ✅ Saved to {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")
    
    print(f"\n  Vessel class distribution:")
    print(df_out["vessel_class"].value_counts().head(10).to_string())
    print(f"\n  Flag (best) distribution:")
    flags = df_out["flag_gfw"].value_counts().head(10)
    print(flags.to_string())


def run_step_1_4():
    """Load Zenodo monthly effort from zip files."""
    logger.info("Loading Zenodo monthly effort...")
    zenodo_dir = DATA_DIR / "zenodo"
    
    all_dfs = []
    for year in [2020, 2021, 2022, 2023, 2024]:
        zip_path = zenodo_dir / f"fleet-monthly-csvs-10-v3-{year}.zip"
        if not zip_path.exists():
            print(f"  ⚠️ Missing: {zip_path}")
            continue
        
        with zipfile.ZipFile(zip_path) as zf:
            csv_files = [n for n in zf.namelist() if n.endswith(".csv")]
            print(f"  {year}: {len(csv_files)} monthly files")
            
            for csv_name in csv_files:
                try:
                    with zf.open(csv_name) as f:
                        df_month = pd.read_csv(f)
                        all_dfs.append(df_month)
                except Exception as e:
                    print(f"    ⚠️ Skipping {csv_name}: {e}")
    
    if not all_dfs:
        print("  ❌ No data loaded!")
        return
    
    df = pd.concat(all_dfs, ignore_index=True)
    print(f"  Total Zenodo effort records: {len(df):,}")
    print(f"  Columns: {df.columns.tolist()}")
    
    # Filter to relevant flags
    event_flags = ["IDN", "MYS", "CHN", "PAN", "SGP", "TWN", "LBR", "KOR", "VNM", "THA"]
    df_relevant = df[df["flag"].str.upper().isin(event_flags)]
    print(f"  After flag filter: {len(df_relevant):,}")
    
    output_path = OUTPUT_DIR / "zenodo_effort_flat.parquet"
    df_relevant.to_parquet(output_path, index=False)
    print(f"  ✅ Saved to {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")
    
    print(f"\n  Flag distribution:")
    print(df_relevant["flag"].value_counts().to_string())
    print(f"\n  Geartype distribution:")
    print(df_relevant["geartype"].value_counts().head(10).to_string())


def run_step_1_5():
    """Load auxiliary data: weather, VIIRS, ports."""
    # Weather
    logger.info("Loading weather data...")
    df_weather = pd.read_csv(DATA_DIR / "bmkg" / "marine_weather_2024.csv")
    print(f"  Weather: {len(df_weather):,} rows")
    print(f"  Columns: {df_weather.columns.tolist()}")
    print(f"  Zones: {df_weather['zone'].unique().tolist()}")
    
    weather_path = OUTPUT_DIR / "weather.parquet"
    df_weather.to_parquet(weather_path, index=False)
    print(f"  ✅ Saved to {weather_path}")
    
    # VIIRS
    logger.info("Loading VIIRS data...")
    df_viirs = pd.read_csv(DATA_DIR / "viirs" / "sample_vbd_detections_2024.csv")
    print(f"  VIIRS: {len(df_viirs):,} rows")
    
    viirs_path = OUTPUT_DIR / "viirs_detections.parquet"
    df_viirs.to_parquet(viirs_path, index=False)
    print(f"  ✅ Saved to {viirs_path}")
    
    # Ports
    logger.info("Loading port data...")
    with open(DATA_DIR / "gfw" / "osm_indonesia_ports_manual.json") as f:
        ports = json.load(f)
    df_ports = pd.DataFrame(ports)
    print(f"  Ports: {len(df_ports):,}")
    print(f"  Sample: {df_ports.head(3).to_string()}")
    
    ports_path = OUTPUT_DIR / "ports.parquet"
    df_ports.to_parquet(ports_path, index=False)
    print(f"  ✅ Saved to {ports_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("STEP 1.3 — VESSEL REGISTRY")
    print("=" * 60)
    run_step_1_3()
    
    print(f"\n{'='*60}")
    print("STEP 1.4 — ZENODO MONTHLY EFFORT")
    print("=" * 60)
    run_step_1_4()
    
    print(f"\n{'='*60}")
    print("STEP 1.5 — AUXILIARY DATA")
    print("=" * 60)
    run_step_1_5()
    
    # Final inventory
    print(f"\n{'='*60}")
    print("PHASE 1 COMPLETE — OUTPUT INVENTORY")
    print("=" * 60)
    for f in sorted(OUTPUT_DIR.glob("*.parquet")):
        size_mb = f.stat().st_size / 1024 / 1024
        df = pd.read_parquet(f)
        print(f"  {f.name:40s} {size_mb:8.1f} MB  {len(df):>10,} rows × {len(df.columns)} cols")
