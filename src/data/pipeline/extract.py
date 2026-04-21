"""
Phase 1: Extract & Flatten ALL Raw Data

Loads raw data files (JSON, CSV, ZIP) and converts to normalized parquet files.
All functions import from src.data.constants for paths and shared config.

Functions:
- extract_gfw_events: Load 4 GFW event JSONs → gfw_events_flat.parquet
- extract_sar_presence: Load SAR JSON → sar_presence_flat.parquet
- extract_fishing_effort: Load effort JSON → fishing_effort_flat.parquet
- extract_vessel_registry: Load Zenodo CSV → vessel_registry.parquet
- extract_zenodo_effort: Load Zenodo zips → zenodo_effort_flat.parquet
- extract_auxiliary: Load weather, VIIRS, ports → individual parquets
- run_extract_all: Run all extract functions, return mapping
"""

from __future__ import annotations

import gc
import gzip
import json
import logging
import zipfile
from pathlib import Path
from typing import Optional

import pandas as pd

from ..constants import (
    GFW_RAW_DIR, PROCESSED_DIR, ZENODO_RAW_DIR, BMKG_RAW_DIR, VIIRS_RAW_DIR,
    RAW_DIR,
    GFW_FISHING_FILE, GFW_ENCOUNTERS_FILE, GFW_LOITERING_FILE, GFW_PORT_VISITS_FILE,
    GFW_SAR_FILE, GFW_EFFORT_FILE,
    ZENODO_VESSELS_FILE, PORTS_FILE, WEATHER_FILE, VIIRS_FILE,
    GFW_EVENTS_FLAT, SAR_PRESENCE_FLAT, FISHING_EFFORT_FLAT,
    VESSEL_REGISTRY, ZENODO_EFFORT_FLAT,
    WEATHER_PARQUET, VIIRS_PARQUET, PORTS_PARQUET,
    EVENT_FLAGS, INDONESIA_BBOX,
)

logger = logging.getLogger(__name__)


# =========================================================================
# Internal helpers for GFW event flattening
# =========================================================================

def _extract_vessel_info(vessel: dict) -> dict:
    """Extract standardized vessel fields from GFW vessel object."""
    if not vessel:
        return {}
    return {
        "mmsi": vessel.get("ssvid", ""),
        "vessel_name": vessel.get("name", ""),
        "vessel_id": vessel.get("id", ""),
        "vessel_flag": vessel.get("flag", ""),
        "vessel_type": vessel.get("type", ""),
    }


def _extract_regions(regions: dict) -> dict:
    """Flatten regions dict."""
    if not regions:
        return {}
    return {
        "eez_ids": regions.get("eez", []),
        "mpa_ids": regions.get("mpa", []),
        "rfmo": regions.get("rfmo", []),
        "fao_zones": regions.get("fao", []),
        "in_highseas": len(regions.get("highSeas", [])) > 0,
        "in_mpa_notake": len(regions.get("mpaNoTake", [])) > 0,
    }


def _extract_distances(distances: dict) -> dict:
    """Flatten distances dict."""
    if not distances:
        return {}
    return {
        "distance_shore_start_km": distances.get("startDistanceFromShoreKm"),
        "distance_shore_end_km": distances.get("endDistanceFromShoreKm"),
        "distance_port_start_km": distances.get("startDistanceFromPortKm"),
        "distance_port_end_km": distances.get("endDistanceFromPortKm"),
    }


def _extract_authorizations(vessel: dict) -> dict:
    """Extract RFMO authorization status."""
    auths = vessel.get("publicAuthorizations", [])
    auth_status = "unknown"
    rfmo_list = []
    if auths:
        for auth in auths:
            rfmo_list.append(auth.get("rfmo", ""))
            if auth.get("hasPubliclyListedAuthorization") == "false":
                auth_status = "not_authorized"
            elif auth.get("hasPubliclyListedAuthorization") == "true":
                auth_status = "authorized"
    return {
        "authorization_status": auth_status,
        "authorized_rfmos": rfmo_list,
    }


def _flatten_fishing_events() -> pd.DataFrame:
    """Load and flatten fishing events."""
    logger.info("Loading fishing events...")
    with gzip.open(GFW_RAW_DIR / GFW_FISHING_FILE, "rt") as f:
        data = json.load(f)
    logger.info(f"  Loaded {len(data):,} fishing events")

    rows = []
    for ev in data:
        vessel = ev.get("vessel", {})
        v_info = _extract_vessel_info(vessel)
        regions = _extract_regions(ev.get("regions", {}))
        distances = _extract_distances(ev.get("distances", {}))
        auths = _extract_authorizations(vessel)
        fishing = ev.get("fishing", {})
        pos = ev.get("position", {})

        row = {
            "event_id": ev.get("id", ""),
            "event_type": "fishing",
            "start_time": ev.get("start", ""),
            "end_time": ev.get("end", ""),
            "lat": pos.get("lat"),
            "lon": pos.get("lon"),
            "bbox_minlon": ev.get("boundingBox", [None, None, None, None])[0],
            "bbox_minlat": ev.get("boundingBox", [None, None, None, None])[1],
            "bbox_maxlon": ev.get("boundingBox", [None, None, None, None])[2],
            "bbox_maxlat": ev.get("boundingBox", [None, None, None, None])[3],
            **v_info,
            **regions,
            **distances,
            **auths,
            "total_distance_km": fishing.get("totalDistanceKm"),
            "avg_speed_knots": fishing.get("averageSpeedKnots"),
            "potential_risk": fishing.get("potentialRisk", False),
            "auth_match_status": fishing.get("vesselPublicAuthorizationStatus", ""),
            "next_port": (vessel.get("nextPort") or {}).get("name", "") if vessel.get("nextPort") else "",
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    logger.info(f"  Flattened to {len(df):,} rows × {len(df.columns)} columns")
    return df


def _flatten_encounters() -> pd.DataFrame:
    """Load and flatten encounters (has 2 vessels)."""
    logger.info("Loading encounters...")
    with gzip.open(GFW_RAW_DIR / GFW_ENCOUNTERS_FILE, "rt") as f:
        data = json.load(f)
    logger.info(f"  Loaded {len(data):,} encounters")

    rows = []
    for ev in data:
        vessel = ev.get("vessel", {})
        v1 = _extract_vessel_info(vessel)
        auths1 = _extract_authorizations(vessel)

        enc_detail = ev.get("encounter", {})
        enc_vessel = enc_detail.get("vessel", {})
        v2 = _extract_vessel_info(enc_vessel)

        regions = _extract_regions(ev.get("regions", {}))
        distances = _extract_distances(ev.get("distances", {}))
        pos = ev.get("position", {})

        row = {
            "event_id": ev.get("id", ""),
            "event_type": "encounter",
            "start_time": ev.get("start", ""),
            "end_time": ev.get("end", ""),
            "lat": pos.get("lat"),
            "lon": pos.get("lon"),
            "bbox_minlon": ev.get("boundingBox", [None, None, None, None])[0],
            "bbox_minlat": ev.get("boundingBox", [None, None, None, None])[1],
            "bbox_maxlon": ev.get("boundingBox", [None, None, None, None])[2],
            "bbox_maxlat": ev.get("boundingBox", [None, None, None, None])[3],
            "mmsi": v1.get("mmsi", ""),
            "vessel_name": v1.get("vessel_name", ""),
            "vessel_id": v1.get("vessel_id", ""),
            "vessel_flag": v1.get("vessel_flag", ""),
            "vessel_type": v1.get("vessel_type", ""),
            "mmsi_2": v2.get("mmsi", ""),
            "vessel_name_2": v2.get("vessel_name", ""),
            "vessel_flag_2": v2.get("vessel_flag", ""),
            "vessel_type_2": v2.get("vessel_type", ""),
            **regions,
            **distances,
            **auths1,
            "encounter_type": enc_detail.get("type", ""),
            "encounter_median_distance_km": enc_detail.get("medianDistanceKilometers"),
            "encounter_median_speed_knots": enc_detail.get("medianSpeedKnots"),
            "encounter_potential_risk": enc_detail.get("potentialRisk", False),
            "encounter_v2_auth_status": enc_detail.get("encounteredVesselPublicAuthorizationStatus", ""),
            "next_port": "",
            "total_distance_km": None,
            "avg_speed_knots": None,
            "potential_risk": enc_detail.get("potentialRisk", False),
            "auth_match_status": enc_detail.get("mainVesselPublicAuthorizationStatus", ""),
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    logger.info(f"  Flattened to {len(df):,} rows × {len(df.columns)} columns")
    return df


def _flatten_loitering_events() -> pd.DataFrame:
    """Load and flatten loitering events."""
    logger.info("Loading loitering events...")
    with gzip.open(GFW_RAW_DIR / GFW_LOITERING_FILE, "rt") as f:
        data = json.load(f)
    logger.info(f"  Loaded {len(data):,} loitering events")

    rows = []
    for ev in data:
        vessel = ev.get("vessel", {})
        v_info = _extract_vessel_info(vessel)
        regions = _extract_regions(ev.get("regions", {}))
        distances = _extract_distances(ev.get("distances", {}))
        auths = _extract_authorizations(vessel)
        loit = ev.get("loitering", {})
        pos = ev.get("position", {})

        row = {
            "event_id": ev.get("id", ""),
            "event_type": "loitering",
            "start_time": ev.get("start", ""),
            "end_time": ev.get("end", ""),
            "lat": pos.get("lat"),
            "lon": pos.get("lon"),
            "bbox_minlon": ev.get("boundingBox", [None, None, None, None])[0],
            "bbox_minlat": ev.get("boundingBox", [None, None, None, None])[1],
            "bbox_maxlon": ev.get("boundingBox", [None, None, None, None])[2],
            "bbox_maxlat": ev.get("boundingBox", [None, None, None, None])[3],
            **v_info,
            **regions,
            **distances,
            **auths,
            "loitering_total_hours": loit.get("totalTimeHours"),
            "loitering_total_distance_km": loit.get("totalDistanceKm"),
            "loitering_avg_speed_knots": loit.get("averageSpeedKnots"),
            "loitering_avg_distance_shore_km": loit.get("averageDistanceFromShoreKm"),
            "next_port": "",
            "total_distance_km": loit.get("totalDistanceKm"),
            "avg_speed_knots": loit.get("averageSpeedKnots"),
            "potential_risk": False,
            "auth_match_status": "",
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    logger.info(f"  Flattened to {len(df):,} rows × {len(df.columns)} columns")
    return df


def _flatten_port_visits() -> pd.DataFrame:
    """Load and flatten port visit events."""
    logger.info("Loading port visits...")
    with gzip.open(GFW_RAW_DIR / GFW_PORT_VISITS_FILE, "rt") as f:
        data = json.load(f)
    logger.info(f"  Loaded {len(data):,} port visits")

    rows = []
    for ev in data:
        vessel = ev.get("vessel", {})
        v_info = _extract_vessel_info(vessel)
        regions = _extract_regions(ev.get("regions", {}))
        distances = _extract_distances(ev.get("distances", {}))
        auths = _extract_authorizations(vessel)
        pv = ev.get("port_visit", {})
        pos = ev.get("position", {})
        start_anch = pv.get("startAnchorage", {}) or {}

        row = {
            "event_id": ev.get("id", ""),
            "event_type": "port_visit",
            "start_time": ev.get("start", ""),
            "end_time": ev.get("end", ""),
            "lat": pos.get("lat"),
            "lon": pos.get("lon"),
            "bbox_minlon": ev.get("boundingBox", [None, None, None, None])[0],
            "bbox_minlat": ev.get("boundingBox", [None, None, None, None])[1],
            "bbox_maxlon": ev.get("boundingBox", [None, None, None, None])[2],
            "bbox_maxlat": ev.get("boundingBox", [None, None, None, None])[3],
            **v_info,
            **regions,
            **distances,
            **auths,
            "port_name": start_anch.get("topDestination", "") or start_anch.get("name", ""),
            "port_id": start_anch.get("id", ""),
            "port_lat": start_anch.get("lat"),
            "port_lon": start_anch.get("lon"),
            "port_visit_duration_hours": pv.get("durationHrs"),
            "port_visit_confidence": pv.get("confidence", ""),
            "at_dock": start_anch.get("atDock", False),
            "port_country_flag": start_anch.get("flag", ""),
            "next_port": "",
            "total_distance_km": None,
            "avg_speed_knots": None,
            "potential_risk": False,
            "auth_match_status": "",
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    logger.info(f"  Flattened to {len(df):,} rows × {len(df.columns)} columns")
    return df


# =========================================================================
# Public extract functions
# =========================================================================

def extract_gfw_events() -> Path:
    """Load 4 GFW event JSONs and flatten into unified parquet.

    Returns:
        Path to gfw_events_flat.parquet
    """
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    df_fishing = _flatten_fishing_events()
    df_encounters = _flatten_encounters()
    df_loitering = _flatten_loitering_events()
    df_port_visits = _flatten_port_visits()

    all_dfs = [df_fishing, df_encounters, df_loitering, df_port_visits]
    all_cols = sorted(set().union(*(df.columns for df in all_dfs)))

    for i, df in enumerate(all_dfs):
        missing = set(all_cols) - set(df.columns)
        for col in missing:
            all_dfs[i][col] = None

    logger.info("Concatenating all event types...")
    df_unified = pd.concat(all_dfs, ignore_index=True)
    logger.info(f"Unified table: {len(df_unified):,} rows × {len(df_unified.columns)} columns")

    logger.info("Parsing timestamps...")
    df_unified["start_time"] = pd.to_datetime(df_unified["start_time"], utc=True)
    df_unified["end_time"] = pd.to_datetime(df_unified["end_time"], utc=True)
    df_unified["duration_hours"] = (
        df_unified["end_time"] - df_unified["start_time"]
    ).dt.total_seconds() / 3600

    df_unified["lat"] = pd.to_numeric(df_unified["lat"], errors="coerce")
    df_unified["lon"] = pd.to_numeric(df_unified["lon"], errors="coerce")

    logger.info("Validating...")
    logger.info(f"Total rows: {len(df_unified):,}")
    logger.info(f"By event type:\n{df_unified['event_type'].value_counts().to_string()}")
    logger.info(f"Null MMSI: {df_unified['mmsi'].isna().sum():,} / {len(df_unified):,}")
    logger.info(f"Empty MMSI: {(df_unified['mmsi'] == '').sum():,}")
    logger.info(f"Null lat/lon: {df_unified['lat'].isna().sum():,}")
    logger.info(f"Date range: {df_unified['start_time'].min()} → {df_unified['start_time'].max()}")
    logger.info(f"Flag distribution (top 10):\n{df_unified['vessel_flag'].value_counts().head(10).to_string()}")
    logger.info(f"Duration stats (hours):\n{df_unified['duration_hours'].describe().to_string()}")

    output_path = PROCESSED_DIR / GFW_EVENTS_FLAT
    df_unified.to_parquet(output_path, index=False, compression="snappy")
    logger.info(f"✅ Saved to {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")
    del df_unified, all_dfs; gc.collect()
    return output_path


def extract_sar_presence() -> Path:
    """Load SAR presence JSON and flatten to parquet.

    Returns:
        Path to sar_presence_flat.parquet
    """
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
    logger.info(f"Non-empty MMSI: {(df['mmsi'] != '').sum():,} ({(df['mmsi'] != '').mean()*100:.1f}%)")
    logger.info(f"Detections stats:\n{df['detections'].describe().to_string()}")

    output_path = PROCESSED_DIR / SAR_PRESENCE_FLAT
    df.to_parquet(output_path, index=False)
    logger.info(f"✅ Saved to {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")
    del df; gc.collect()
    return output_path


def extract_fishing_effort() -> Path:
    """Load fishing effort JSON and flatten to parquet.

    Returns:
        Path to fishing_effort_flat.parquet
    """
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
    logger.info(f"Fishing hours stats:\n{df['fishing_hours'].describe().to_string()}")
    logger.info(f"Geartype distribution:\n{df['geartype'].value_counts().head(10).to_string()}")
    logger.info(f"Flag distribution:\n{df['flag'].value_counts().head(5).to_string()}")

    output_path = PROCESSED_DIR / FISHING_EFFORT_FLAT
    df.to_parquet(output_path, index=False)
    logger.info(f"✅ Saved to {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")
    del df; gc.collect()
    return output_path


def extract_vessel_registry() -> Path:
    """Load Zenodo vessel registry CSV, filter to relevant vessels, save as parquet.

    Returns:
        Path to vessel_registry.parquet
    """
    logger.info("Loading vessel registry...")
    df = pd.read_csv(ZENODO_RAW_DIR / ZENODO_VESSELS_FILE, low_memory=False)
    logger.info(f"  Total vessels: {len(df):,}")

    flag_cols = ["flag_ais", "flag_registry", "flag_gfw"]
    is_relevant = pd.Series(False, index=df.index)
    for col in flag_cols:
        for flag in EVENT_FLAGS:
            is_relevant = is_relevant | df[col].str.upper().str.contains(flag, na=False)

    df_relevant = df[is_relevant].copy()
    logger.info(f"  Relevant vessels (matching event flags): {len(df_relevant):,}")

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

    # Convert MMSI to string for join consistency
    df_out["mmsi"] = df_out["mmsi"].astype(str)

    output_path = PROCESSED_DIR / VESSEL_REGISTRY
    df_out.to_parquet(output_path, index=False)
    logger.info(f"  ✅ Saved to {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")
    logger.info(f"  Vessel class distribution:\n{df_out['vessel_class'].value_counts().head(10).to_string()}")
    del df, df_relevant, df_latest; gc.collect()
    return output_path


def extract_zenodo_effort() -> Path:
    """Load Zenodo monthly effort from zip files with spatial filter (Indonesia bbox).

    Returns:
        Path to zenodo_effort_flat.parquet
    """
    logger.info("Loading Zenodo monthly effort...")
    bbox = INDONESIA_BBOX

    all_dfs = []
    for year in [2020, 2021, 2022, 2023, 2024]:
        zip_path = ZENODO_RAW_DIR / f"fleet-monthly-csvs-10-v3-{year}.zip"
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
        return PROCESSED_DIR / ZENODO_EFFORT_FLAT

    df = pd.concat(all_dfs, ignore_index=True)
    logger.info(f"  Total Zenodo effort records (after spatial filter): {len(df):,}")

    output_path = PROCESSED_DIR / ZENODO_EFFORT_FLAT
    df.to_parquet(output_path, index=False)
    logger.info(f"  ✅ Saved to {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")
    del df, all_dfs; gc.collect()
    return output_path


def extract_auxiliary() -> list[Path]:
    """Load weather, VIIRS, and port data → individual parquets.

    Returns:
        List of output parquet paths.
    """
    paths = []

    # Weather
    logger.info("Loading weather data...")
    df_weather = pd.read_csv(BMKG_RAW_DIR / WEATHER_FILE)
    logger.info(f"  Weather: {len(df_weather):,} rows")
    weather_path = PROCESSED_DIR / WEATHER_PARQUET
    df_weather.to_parquet(weather_path, index=False)
    logger.info(f"  ✅ Saved to {weather_path}")
    paths.append(weather_path)

    # VIIRS
    logger.info("Loading VIIRS data...")
    df_viirs = pd.read_csv(VIIRS_RAW_DIR / VIIRS_FILE)
    logger.info(f"  VIIRS: {len(df_viirs):,} rows")
    viirs_path = PROCESSED_DIR / VIIRS_PARQUET
    df_viirs.to_parquet(viirs_path, index=False)
    logger.info(f"  ✅ Saved to {viirs_path}")
    paths.append(viirs_path)

    # Ports
    logger.info("Loading port data...")
    with open(GFW_RAW_DIR / PORTS_FILE) as f:
        ports = json.load(f)
    df_ports = pd.DataFrame(ports)
    logger.info(f"  Ports: {len(df_ports):,}")
    ports_path = PROCESSED_DIR / PORTS_PARQUET
    df_ports.to_parquet(ports_path, index=False)
    logger.info(f"  ✅ Saved to {ports_path}")
    paths.append(ports_path)

    return paths


def run_extract_all() -> dict[str, Path]:
    """Run all extract functions and return mapping of name → output path.

    Returns:
        Dict mapping dataset name to output parquet path.
    """
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    results = {}

    results["gfw_events"] = extract_gfw_events()
    results["sar_presence"] = extract_sar_presence()
    results["fishing_effort"] = extract_fishing_effort()
    results["vessel_registry"] = extract_vessel_registry()
    results["zenodo_effort"] = extract_zenodo_effort()

    for p in extract_auxiliary():
        results[p.stem] = p

    logger.info("✅ Extract phase complete")
    return results
