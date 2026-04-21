"""
Phase 1 Step 1.1: Flatten GFW Events into Unified Table

Input: 4 GFW event JSON.gz files (fishing, encounters, loitering, port visits)
Output: data/processed/gfw_events_flat.parquet

Key finding from audit:
- vessel.ssvid is the MMSI (not vessel.mmsi)
- Encounters: main vessel in 'vessel', other vessel in 'encounter.vessel'
- Each event type has a type-specific sub-object: fishing{}, encounter{}, loitering{}, port_visit{}
"""

from __future__ import annotations

import gzip
import json
import logging
import sys
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

DATA_DIR = Path("data/raw/gfw")
OUTPUT_DIR = Path("data/processed")


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


def flatten_fishing_events() -> pd.DataFrame:
    """Load and flatten fishing events."""
    logger.info("Loading fishing events...")
    with gzip.open(DATA_DIR / "fishing_events_indonesia_2020-2025.json.gz", "rt") as f:
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
            # Fishing-specific
            "total_distance_km": fishing.get("totalDistanceKm"),
            "avg_speed_knots": fishing.get("averageSpeedKnots"),
            "potential_risk": fishing.get("potentialRisk", False),
            "auth_match_status": fishing.get("vesselPublicAuthorizationStatus", ""),
            # Vessel next port
            "next_port": (vessel.get("nextPort") or {}).get("name", "") if vessel.get("nextPort") else "",
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    logger.info(f"  Flattened to {len(df):,} rows × {len(df.columns)} columns")
    return df


def flatten_encounters() -> pd.DataFrame:
    """Load and flatten encounters (has 2 vessels)."""
    logger.info("Loading encounters...")
    with gzip.open(DATA_DIR / "encounters_indonesia_2020-2024.json.gz", "rt") as f:
        data = json.load(f)
    logger.info(f"  Loaded {len(data):,} encounters")

    rows = []
    for ev in data:
        # Main vessel
        vessel = ev.get("vessel", {})
        v1 = _extract_vessel_info(vessel)
        auths1 = _extract_authorizations(vessel)

        # Encountered vessel
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
            # Primary vessel
            "mmsi": v1.get("mmsi", ""),
            "vessel_name": v1.get("vessel_name", ""),
            "vessel_id": v1.get("vessel_id", ""),
            "vessel_flag": v1.get("vessel_flag", ""),
            "vessel_type": v1.get("vessel_type", ""),
            # Secondary vessel
            "mmsi_2": v2.get("mmsi", ""),
            "vessel_name_2": v2.get("vessel_name", ""),
            "vessel_flag_2": v2.get("vessel_flag", ""),
            "vessel_type_2": v2.get("vessel_type", ""),
            **regions,
            **distances,
            **auths1,
            # Encounter-specific
            "encounter_type": enc_detail.get("type", ""),  # e.g. "fishing-fishing"
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


def flatten_loitering_events() -> pd.DataFrame:
    """Load and flatten loitering events."""
    logger.info("Loading loitering events...")
    with gzip.open(DATA_DIR / "loitering_indonesia_2020-2025_corrected.json.gz", "rt") as f:
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
            # Loitering-specific
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


def flatten_port_visits() -> pd.DataFrame:
    """Load and flatten port visit events."""
    logger.info("Loading port visits...")
    with gzip.open(DATA_DIR / "port_visits_indonesia_2020-2025.json.gz", "rt") as f:
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

        # Port info
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
            # Port-visit specific
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


def run_step_1_1():
    """Execute Phase 1 Step 1.1: Build unified GFW events table."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load each event type
    df_fishing = flatten_fishing_events()
    df_encounters = flatten_encounters()
    df_loitering = flatten_loitering_events()
    df_port_visits = flatten_port_visits()

    # Unify columns — add missing columns to each df
    all_dfs = [df_fishing, df_encounters, df_loitering, df_port_visits]
    all_cols = sorted(set().union(*(df.columns for df in all_dfs)))
    
    for i, df in enumerate(all_dfs):
        missing = set(all_cols) - set(df.columns)
        for col in missing:
            all_dfs[i][col] = None

    # Concatenate
    logger.info("Concatenating all event types...")
    df_unified = pd.concat(all_dfs, ignore_index=True)
    logger.info(f"Unified table: {len(df_unified):,} rows × {len(df_unified.columns)} columns")

    # Parse timestamps
    logger.info("Parsing timestamps...")
    df_unified["start_time"] = pd.to_datetime(df_unified["start_time"], utc=True)
    df_unified["end_time"] = pd.to_datetime(df_unified["end_time"], utc=True)
    
    # Compute duration
    df_unified["duration_hours"] = (
        df_unified["end_time"] - df_unified["start_time"]
    ).dt.total_seconds() / 3600

    # Type conversions
    df_unified["lat"] = pd.to_numeric(df_unified["lat"], errors="coerce")
    df_unified["lon"] = pd.to_numeric(df_unified["lon"], errors="coerce")

    # Validate
    logger.info("Validating...")
    print(f"\n{'='*60}")
    print("STEP 1.1 VALIDATION REPORT")
    print(f"{'='*60}")
    print(f"Total rows: {len(df_unified):,}")
    print(f"\nBy event type:")
    print(df_unified["event_type"].value_counts().to_string())
    print(f"\nNull MMSI: {df_unified['mmsi'].isna().sum():,} / {len(df_unified):,} ({df_unified['mmsi'].isna().mean()*100:.1f}%)")
    print(f"Empty MMSI: {(df_unified['mmsi'] == '').sum():,}")
    print(f"Null lat/lon: {df_unified['lat'].isna().sum():,}")
    print(f"\nDate range: {df_unified['start_time'].min()} → {df_unified['start_time'].max()}")
    print(f"\nFlag distribution (top 10):")
    print(df_unified["vessel_flag"].value_counts().head(10).to_string())
    print(f"\nDuration stats (hours):")
    print(df_unified["duration_hours"].describe().to_string())
    print(f"\nColumns ({len(df_unified.columns)}):")
    print(df_unified.columns.tolist())

    # Save
    output_path = OUTPUT_DIR / "gfw_events_flat.parquet"
    df_unified.to_parquet(output_path, index=False, compression="snappy")
    logger.info(f"\n✅ Saved to {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    run_step_1_1()
