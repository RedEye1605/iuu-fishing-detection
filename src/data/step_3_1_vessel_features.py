"""
Phase 3 Step 3.1+3.3: Vessel Profile & Temporal Features

Step 3.1: Join events with vessel registry → add vessel features
Step 3.3: Duration categories (temporal features already added in Phase 2)
Output: data/processed/gfw_events_enriched.parquet
"""

from __future__ import annotations
import gc, logging, json
from pathlib import Path
import pandas as pd
import numpy as np

from .constants import (
    PROCESSED_DIR, GFW_RAW_DIR, PORTS_FILE,
    GFW_EVENTS_CLEAN, VESSEL_REGISTRY_DEDUP, GFW_EVENTS_ENRICHED,
)

logger = logging.getLogger(__name__)
INPUT = PROCESSED_DIR
OUTPUT = PROCESSED_DIR


def run_step_3_1():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    logger.info("=" * 60 + "\nSTEP 3.1: VESSEL PROFILE FEATURES\n" + "=" * 60)

    # Load events
    df = pd.read_parquet(INPUT / GFW_EVENTS_CLEAN)
    logger.info(f"Events: {len(df):,} rows × {len(df.columns)} cols")

    # Load vessel registry — ensure MMSI is string for join
    vessels = pd.read_parquet(INPUT / VESSEL_REGISTRY_DEDUP)
    vessels["mmsi"] = vessels["mmsi"].astype(str)
    logger.info(f"Vessel registry: {len(vessels):,} rows")

    v_lookup = vessels.drop_duplicates(subset=["mmsi"]).copy()
    v_lookup.index = v_lookup["mmsi"]
    v_lookup = v_lookup.drop(columns=["mmsi"])

    # Map vessel features to events
    logger.info("Mapping vessel features...")
    registry_cols = {
        "vessel_class": "reg_vessel_class",
        "length_m": "reg_length_m",
        "engine_power_kw": "reg_engine_power_kw",
        "tonnage_gt": "reg_tonnage_gt",
        "self_reported_fishing_vessel": "reg_self_reported_fishing",
        "flag_ais": "reg_flag_ais",
    }
    for src, dst in registry_cols.items():
        if src in v_lookup.columns:
            df[dst] = df["mmsi"].map(v_lookup[src].to_dict())
            filled = df[dst].notna().sum()
            logger.info(f"  {dst}: {filled:,} filled ({filled/len(df)*100:.1f}%)")

    # Derived features
    logger.info("Computing derived features...")

    # is_fishing_vessel
    df["is_fishing_vessel"] = (
        (df.get("reg_self_reported_fishing", pd.Series(dtype=bool)) == True) |
        (df.get("reg_vessel_class", pd.Series(dtype=str)).str.contains(
            "fishing|trawl|seine|longline|gillnet|dredge|squid", case=False, na=False)) |
        (df["vessel_type"].str.contains("fishing|trawl|seine|longline|gillnet", case=False, na=False))
    )

    # size_category — handle edge cases
    def size_cat(length):
        if pd.isna(length) or length <= 0:
            return "unknown"
        if length < 12:
            return "small"
        if length < 24:
            return "medium"
        return "large"

    df["size_category"] = df["reg_length_m"].map(size_cat)

    # tonnage_per_length
    df["tonnage_per_length"] = np.where(
        df["reg_length_m"] > 0,
        df["reg_tonnage_gt"] / df["reg_length_m"],
        np.nan
    )

    # Duration category — use string labels (not Categorical) for ML compatibility
    df["duration_category"] = pd.cut(
        df["duration_hours"],
        bins=[-0.01, 2, 8, float("inf")],
        labels=["short", "medium", "long"]
    ).astype(str)  # Convert from Categorical to str

    # Grid cell (0.1° ≈ 11km)
    df["grid_lat"] = (df["lat"] * 10).round(0) / 10
    df["grid_lon"] = (df["lon"] * 10).round(0) / 10

    # Nearest port (vectorized)
    with open(GFW_RAW_DIR / PORTS_FILE) as f:
        ports = json.load(f)

    logger.info(f"Computing nearest port from {len(ports)} ports...")
    port_lats = np.array([p["lat"] for p in ports])
    port_lons = np.array([p["lon"] for p in ports])
    port_names = [p["name"] for p in ports]

    event_lats = df["lat"].values
    event_lons = df["lon"].values

    min_idx = np.zeros(len(df), dtype=int)
    min_dist = np.full(len(df), np.inf)

    for i, (plat, plon) in enumerate(zip(port_lats, port_lons)):
        d = np.sqrt((event_lats - plat)**2 + (event_lons - plon)**2)
        mask = d < min_dist
        min_idx[mask] = i
        min_dist[mask] = d[mask]

    df["nearest_port_name"] = [port_names[i] for i in min_idx]
    df["nearest_port_dist_km"] = min_dist * 111  # 1° ≈ 111km

    # Sea zone classification — VECTORIZED with np.select()
    lat = df["lat"].values
    lon = df["lon"].values

    conditions = [
        (lat >= -8) & (lat <= -5) & (lon >= 105) & (lon <= 115),   # Java Sea
        (lat >= -8) & (lat <= -2) & (lon >= 115) & (lon <= 120),   # Bali Sea
        (lat >= -5) & (lat <= 2) & (lon >= 108) & (lon <= 120),    # Karimata Strait
        (lat >= 0) & (lat <= 5) & (lon >= 120) & (lon <= 128),     # Celebes Sea
        (lat >= -4) & (lat <= 2) & (lon >= 128) & (lon <= 141),    # Banda Sea
        (lat >= -8) & (lat <= -3) & (lon >= 110) & (lon <= 116),   # Indian Ocean (S)
        (lat >= 2) & (lat <= 6) & (lon >= 95) & (lon <= 105),      # Malacca Strait
        (lat >= -2) & (lat <= 4) & (lon >= 130) & (lon <= 141),    # Arafura Sea
        (lat >= -8) & (lat <= -2) & (lon >= 120) & (lon <= 130),   # Timor Sea
    ]
    choices = [
        "Java Sea", "Bali Sea", "Karimata Strait", "Celebes Sea",
        "Banda Sea", "Indian Ocean (S)", "Malacca Strait", "Arafura Sea", "Timor Sea",
    ]

    df["sea_zone"] = np.select(conditions, choices, default="Other")

    # Handle NaN coords
    df.loc[df["lat"].isna() | df["lon"].isna(), "sea_zone"] = "unknown"

    del v_lookup, vessels; gc.collect()

    # ===== VALIDATION =====
    logger.info(f"--- Validation ---")
    logger.info(f"Shape: {len(df):,} rows × {len(df.columns)} cols")
    logger.info(f"Size category:\n{df['size_category'].value_counts().to_string()}")
    logger.info(f"Sea zone (top 10):\n{df['sea_zone'].value_counts().head(10).to_string()}")
    logger.info(f"Duration category:\n{df['duration_category'].value_counts().to_string()}")
    logger.info(f"is_fishing_vessel: {df['is_fishing_vessel'].sum():,} / {len(df):,}")
    logger.info(f"vessel_class fill rate: {df['reg_vessel_class'].notna().mean()*100:.1f}%")
    logger.info(f"length_m fill rate: {df['reg_length_m'].notna().mean()*100:.1f}%")

    out = OUTPUT / GFW_EVENTS_ENRICHED
    df.to_parquet(out, index=False, compression="snappy")
    sz = out.stat().st_size / 1024 / 1024
    logger.info(f"✅ Saved to {out} ({sz:.1f} MB)")
    del df; gc.collect()


if __name__ == "__main__":
    run_step_3_1()
