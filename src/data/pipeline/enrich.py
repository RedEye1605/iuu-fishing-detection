"""
Phase 3b: Cross-Source Enrichment

Enrich GFW events with SAR density, effort density,
and per-vessel behavioral features.

Weather and VIIRS enrichments were removed:
- Weather: 20% coverage (2024 only), not representative
- VIIRS: 0.01% signal (5K sample rows), statistical noise

Functions:
- enrich_sar_density: Merge SAR detection density
- enrich_effort_density: Merge fishing effort density
- enrich_behavioral: Merge per-vessel behavioral features
- run_enrich_all: Run all enrichment, save gfw_events_full.parquet
"""

from __future__ import annotations

import gc
import logging
from pathlib import Path

import pandas as pd

from ..constants import (
    PROCESSED_DIR,
    GFW_EVENTS_ENRICHED, VESSEL_BEHAVIORAL, GFW_EVENTS_FULL,
    SAR_PRESENCE_CLEAN, FISHING_EFFORT_CLEAN,
)

logger = logging.getLogger(__name__)
INPUT = PROCESSED_DIR
OUTPUT = PROCESSED_DIR


def enrich_sar_density(df: pd.DataFrame) -> pd.DataFrame:
    """Merge SAR detection density per grid cell/month.

    Args:
        df: Events DataFrame with grid_lat, grid_lon, ev_year, ev_month columns.

    Returns:
        DataFrame with sar_total_detections and sar_unique_vessels columns.
    """
    logger.info("--- SAR Density Enrichment ---")
    sar = pd.read_parquet(INPUT / SAR_PRESENCE_CLEAN,
                          columns=["lat", "lon", "year", "month", "detections", "mmsi"])
    sar["grid_lat"] = (sar["lat"] * 10).round(0) / 10
    sar["grid_lon"] = (sar["lon"] * 10).round(0) / 10
    sar_density = sar.groupby(["grid_lat", "grid_lon", "year", "month"]).agg(
        sar_total_detections=("detections", "sum"),
        sar_unique_vessels=("mmsi", "nunique"),
    ).reset_index()

    df = df.merge(sar_density, left_on=["grid_lat", "grid_lon", "ev_year", "ev_month"],
                  right_on=["grid_lat", "grid_lon", "year", "month"], how="left", suffixes=("", "_sar"))
    df["sar_total_detections"] = df["sar_total_detections"].fillna(0)
    df["sar_unique_vessels"] = df["sar_unique_vessels"].fillna(0).astype(int)
    for c in ["year", "month"]:
        if c in df.columns:
            df.drop(columns=c, inplace=True)
    logger.info(f"  SAR enriched: {(df['sar_total_detections'] > 0).sum():,} events")
    del sar, sar_density
    gc.collect()
    return df


def enrich_effort_density(df: pd.DataFrame) -> pd.DataFrame:
    """Merge fishing effort density per grid cell/month.

    Args:
        df: Events DataFrame with grid_lat, grid_lon, ev_year, ev_month columns.

    Returns:
        DataFrame with effort_hours_in_cell and effort_vessels_in_cell columns.
    """
    logger.info("--- Effort Density Enrichment ---")
    effort = pd.read_parquet(INPUT / FISHING_EFFORT_CLEAN,
                              columns=["lat", "lon", "fishing_hours", "year", "month"])
    effort["grid_lat"] = (effort["lat"] * 10).round(0) / 10
    effort["grid_lon"] = (effort["lon"] * 10).round(0) / 10
    eff_density = effort.groupby(["grid_lat", "grid_lon", "year", "month"]).agg(
        effort_hours_in_cell=("fishing_hours", "sum"),
        effort_vessels_in_cell=("fishing_hours", "count"),
    ).reset_index()

    df = df.merge(eff_density, left_on=["grid_lat", "grid_lon", "ev_year", "ev_month"],
                  right_on=["grid_lat", "grid_lon", "year", "month"], how="left", suffixes=("", "_eff"))
    df["effort_hours_in_cell"] = df["effort_hours_in_cell"].fillna(0)
    df["effort_vessels_in_cell"] = df["effort_vessels_in_cell"].fillna(0).astype(int)
    for c in ["year", "month"]:
        if c in df.columns:
            df.drop(columns=c, inplace=True)
    logger.info(f"  Effort enriched: {(df['effort_hours_in_cell'] > 0).sum():,} events")
    del effort, eff_density
    gc.collect()
    return df


def enrich_behavioral(df: pd.DataFrame) -> pd.DataFrame:
    """Merge per-vessel behavioral features.

    Args:
        df: Events DataFrame with mmsi column.

    Returns:
        DataFrame with behavioral feature columns added.
    """
    logger.info("--- Behavioral Features ---")
    behavior = pd.read_parquet(INPUT / VESSEL_BEHAVIORAL)

    # Drop columns that would collide with existing event columns
    collision_cols = [c for c in behavior.columns if c in df.columns and c != "mmsi"]
    behavior_clean = behavior.drop(columns=[c for c in collision_cols
                                             if c in ["vessel_flag", "is_domestic", "avg_speed_knots"]])

    df = df.merge(behavior_clean, on="mmsi", how="left")
    logger.info(f"  After merge: {len(df):,} × {len(df.columns)} cols")
    return df


def run_enrich_all() -> Path:
    """Run all enrichment steps and save final enriched events.

    Returns:
        Path to gfw_events_full.parquet
    """
    logger.info("Loading enriched events...")
    df = pd.read_parquet(INPUT / GFW_EVENTS_ENRICHED)
    logger.info(f"Events: {len(df):,} rows × {len(df.columns)} cols")

    df["ev_year"] = df["start_time"].dt.year
    df["ev_month"] = df["start_time"].dt.month

    df = enrich_sar_density(df)
    df = enrich_effort_density(df)
    df = enrich_behavioral(df)

    # Cleanup temp columns
    for c in ["ev_year", "ev_month"]:
        if c in df.columns:
            df.drop(columns=c, inplace=True)

    # Fix column collision artifacts (_x/_y suffixes)
    for c in list(df.columns):
        if c.endswith("_x"):
            base = c[:-2]
            if f"{base}_y" in df.columns:
                df.drop(columns=f"{base}_y", inplace=True)
            df.rename(columns={c: base}, inplace=True)
        elif c.endswith("_y") and c[:-2] in df.columns:
            df.drop(columns=c, inplace=True)

    # Drop SAR/effort suffixed collision columns
    dup_cols = [c for c in df.columns if c.endswith("_sar") or c.endswith("_eff")]
    for c in dup_cols:
        df.drop(columns=c, inplace=True)

    logger.info(f"FINAL: {len(df):,} rows × {len(df.columns)} cols")
    logger.info(f"Columns: {sorted(df.columns.tolist())}")

    out = OUTPUT / GFW_EVENTS_FULL
    df.to_parquet(out, index=False, compression="snappy")
    logger.info(f"✅ Saved to {out} ({out.stat().st_size / 1024 / 1024:.1f} MB)")
    del df
    gc.collect()
    return out
