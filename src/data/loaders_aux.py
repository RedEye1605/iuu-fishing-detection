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

from .constants import (
    RAW_DIR, PROCESSED_DIR, ZENODO_RAW_DIR, GFW_RAW_DIR, BMKG_RAW_DIR, VIIRS_RAW_DIR,
    EVENT_FLAGS, INDONESIA_BBOX,
    ZENODO_VESSELS_FILE, PORTS_FILE, WEATHER_FILE, VIIRS_FILE,
    VESSEL_REGISTRY, ZENODO_EFFORT_FLAT, WEATHER_PARQUET, VIIRS_PARQUET, PORTS_PARQUET,
)

logger = logging.getLogger(__name__)


def run_step_1_3():
    """Load Zenodo vessel registry, filter to relevant vessels."""
    logger.info("Loading vessel registry...")
    df = pd.read_csv(ZENODO_RAW_DIR / ZENODO_VESSELS_FILE, low_memory=False)
    logger.info(f"  Total vessels: {len(df):,}")
    logger.info(f"  Columns: {df.columns.tolist()}")

    is_idn = (
        df["flag_ais"].str.upper().str.contains("IDN", na=False) |
        df["flag_registry"].str.upper().str.contains("IDN", na=False) |
        df["flag_gfw"].str.upper().str.contains("IDN", na=False)
    )

    flag_cols = ["flag_ais", "flag_registry", "flag_gfw"]
    is_relevant = pd.Series(False, index=df.index)
    for col in flag_cols:
        for flag in EVENT_FLAGS:
            is_relevant = is_relevant | df[col].str.upper().str.contains(flag, na=False)

    df_relevant = df[is_relevant].copy()
    logger.info(f"  Relevant vessels (matching event flags): {len(df_relevant):,}")
    logger.info(f"  Of which IDN: {is_idn.sum():,}")

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
    logger.info(f"  After dedup (latest per MMSI): {len(df_latest):,}")

    out_cols = ["mmsi", "year", "flag_ais", "flag_registry", "flag_gfw",
                "vessel_class", "length_m", "engine_power_kw", "tonnage_gt",
                "self_reported_fishing_vessel", "active_hours", "fishing_hours"]
    df_out = df_latest[out_cols].copy()

    # CRITICAL: Convert MMSI to string before saving for join consistency
    df_out["mmsi"] = df_out["mmsi"].astype(str)

    output_path = PROCESSED_DIR / VESSEL_REGISTRY
    df_out.to_parquet(output_path, index=False)
    logger.info(f"  ✅ Saved to {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")
    logger.info(f"  Vessel class distribution:\n{df_out['vessel_class'].value_counts().head(10).to_string()}")
    logger.info(f"  Flag (gfw) distribution:\n{df_out['flag_gfw'].value_counts().head(10).to_string()}")


def run_step_1_4():
    """Load Zenodo monthly effort from zip files — with spatial filter."""
    logger.info("Loading Zenodo monthly effort...")
    zenodo_dir = ZENODO_RAW_DIR

    bbox = INDONESIA_BBOX
    all_dfs = []
    for year in [2020, 2021, 2022, 2023, 2024]:
        zip_path = zenodo_dir / f"fleet-monthly-csvs-10-v3-{year}.zip"
        if not zip_path.exists():
            logger.warning(f"  Missing: {zip_path}")
            continue

        with zipfile.ZipFile(zip_path) as zf:
            csv_files = [n for n in zf.namelist() if n.endswith(".csv")]
            logger.info(f"  {year}: {len(csv_files)} monthly files")

            for csv_name in csv_files:
                try:
                    with zf.open(csv_name) as f:
                        df_month = pd.read_csv(f)

                        # Apply spatial filter (Indonesia bbox) during loading
                        if "cell_ll_lat" in df_month.columns and "cell_ll_lon" in df_month.columns:
                            df_month = df_month[
                                (df_month["cell_ll_lat"] >= bbox["lat_min"]) &
                                (df_month["cell_ll_lat"] <= bbox["lat_max"]) &
                                (df_month["cell_ll_lon"] >= bbox["lon_min"]) &
                                (df_month["cell_ll_lon"] <= bbox["lon_max"])
                            ]

                        all_dfs.append(df_month)
                except Exception as e:
                    logger.warning(f"    Skipping {csv_name}: {e}")

    if not all_dfs:
        logger.error("  No data loaded!")
        return

    df = pd.concat(all_dfs, ignore_index=True)
    logger.info(f"  Total Zenodo effort records (after spatial filter): {len(df):,}")
    logger.info(f"  Columns: {df.columns.tolist()}")

    output_path = PROCESSED_DIR / ZENODO_EFFORT_FLAT
    df.to_parquet(output_path, index=False)
    logger.info(f"  ✅ Saved to {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")
    logger.info(f"  Flag distribution:\n{df['flag'].value_counts().to_string()}")
    logger.info(f"  Geartype distribution:\n{df['geartype'].value_counts().head(10).to_string()}")


def run_step_1_5():
    """Load auxiliary data: weather, VIIRS, ports."""
    # Weather
    logger.info("Loading weather data...")
    df_weather = pd.read_csv(BMKG_RAW_DIR / WEATHER_FILE)
    logger.info(f"  Weather: {len(df_weather):,} rows, columns: {df_weather.columns.tolist()}")
    logger.info(f"  Zones: {df_weather['zone'].unique().tolist()}")

    weather_path = PROCESSED_DIR / WEATHER_PARQUET
    df_weather.to_parquet(weather_path, index=False)
    logger.info(f"  ✅ Saved to {weather_path}")

    # VIIRS
    logger.info("Loading VIIRS data...")
    df_viirs = pd.read_csv(VIIRS_RAW_DIR / VIIRS_FILE)
    logger.info(f"  VIIRS: {len(df_viirs):,} rows")

    viirs_path = PROCESSED_DIR / VIIRS_PARQUET
    df_viirs.to_parquet(viirs_path, index=False)
    logger.info(f"  ✅ Saved to {viirs_path}")

    # Ports
    logger.info("Loading port data...")
    with open(GFW_RAW_DIR / PORTS_FILE) as f:
        ports = json.load(f)
    df_ports = pd.DataFrame(ports)
    logger.info(f"  Ports: {len(df_ports):,}")

    ports_path = PROCESSED_DIR / PORTS_PARQUET
    df_ports.to_parquet(ports_path, index=False)
    logger.info(f"  ✅ Saved to {ports_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60 + "\nSTEP 1.3 — VESSEL REGISTRY\n" + "=" * 60)
    run_step_1_3()

    logger.info("=" * 60 + "\nSTEP 1.4 — ZENODO MONTHLY EFFORT\n" + "=" * 60)
    run_step_1_4()

    logger.info("=" * 60 + "\nSTEP 1.5 — AUXILIARY DATA\n" + "=" * 60)
    run_step_1_5()

    # Final inventory
    logger.info("=" * 60 + "\nPHASE 1 COMPLETE — OUTPUT INVENTORY\n" + "=" * 60)
    for f in sorted(PROCESSED_DIR.glob("*.parquet")):
        size_mb = f.stat().st_size / 1024 / 1024
        df_tmp = pd.read_parquet(f, columns=[])  # just for row count
        logger.info(f"  {f.name:40s} {size_mb:8.1f} MB")
