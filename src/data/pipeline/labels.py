"""
Phase 4: IUU Label Generation

Generate IUU risk scores using multi-signal approach with verified data.
Labels are based on indicators we can actually derive from available data.

Tier 1 — Hard IUU (weight 1.0):
  - fishing_in_mpa: Fishing inside no-take MPA
  - unauthorized_foreign: Foreign vessel fishing without authorization in EEZ
  - high_seas_fishing: Fishing outside any EEZ

Tier 2 — Suspicious Activity (weight 0.6):
  - encounter_at_sea: Vessel-to-vessel encounter (transshipment risk)
  - loitering_anomaly: Excessive loitering relative to vessel's own patterns
  - unregistered_vessel: No registry match for fishing vessel
  - nighttime_foreign: Foreign vessel fishing at night

Tier 3 — Behavioral Anomaly (weight 0.3):
  - high_encounter_rate: Vessel encounter rate > 75th percentile
  - high_loitering_rate: Vessel loitering rate > 75th percentile
  - far_offshore: Operating far from shore (> 90th percentile)
  - rapid_port_cycle: Very short port visits (smuggling indicator)

Output:
  - iuu_score: Continuous [0, 1] weighted sum
  - iuu_label: categorical (normal, suspicious, probable_iuu, hard_iuu)

Functions:
- compute_tier1_indicators: Hard IUU signals
- compute_tier2_indicators: Suspicious activity signals
- compute_tier3_indicators: Behavioral anomalies
- compute_iuu_score: Aggregate weighted score
- assign_iuu_labels: Threshold-based label assignment
- run_label_all: Full pipeline, save labeled dataset
"""

from __future__ import annotations

import gc
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from ..constants import PROCESSED_DIR, GFW_EVENTS_FULL, GFW_EVENTS_LABELED

logger = logging.getLogger(__name__)
INPUT = PROCESSED_DIR
OUTPUT = PROCESSED_DIR

# ===== WEIGHTS =====
TIER1_WEIGHT = 1.0
TIER2_WEIGHT = 0.6
TIER3_WEIGHT = 0.3

# ===== LABEL THRESHOLDS =====
HARD_IUU_THRESHOLD = 0.5
PROBABLE_IUU_THRESHOLD = 0.3
SUSPICIOUS_THRESHOLD = 0.15


def compute_tier1_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute hard IUU indicators — high confidence signals.

    Indicators:
        fishing_in_mpa: Fishing event inside no-take Marine Protected Area.
        unauthorized_foreign: Foreign vessel fishing in EEZ without authorization.
        high_seas_fishing: Fishing event in international waters (no EEZ).

    Args:
        df: Events DataFrame with event_type, in_mpa_notake, is_foreign,
            authorization_status, in_highseas columns.

    Returns:
        DataFrame with tier1_* indicator columns added.
    """
    logger.info("--- Tier 1: Hard IUU Indicators ---")

    # Fishing in no-take MPA
    df["ind_fishing_in_mpa"] = (
        (df["event_type"] == "fishing") & (df["in_mpa_notake"] == True)
    ).astype(int)
    n = df["ind_fishing_in_mpa"].sum()
    logger.info(f"  fishing_in_mpa: {n:,} events ({n/len(df)*100:.2f}%)")

    # Unauthorized foreign vessel fishing in EEZ
    # Foreign + not_authorized + fishing + NOT in high seas (i.e., inside EEZ)
    df["ind_unauthorized_foreign"] = (
        (df["event_type"] == "fishing")
        & (df["is_foreign"] == True)
        & (df["authorization_status"] == "not_authorized")
        & (df["in_highseas"] == False)
    ).astype(int)
    n = df["ind_unauthorized_foreign"].sum()
    logger.info(f"  unauthorized_foreign: {n:,} events ({n/len(df)*100:.2f}%)")

    # High seas fishing (outside EEZ jurisdiction)
    df["ind_high_seas_fishing"] = (
        (df["event_type"] == "fishing") & (df["in_highseas"] == True)
    ).astype(int)
    n = df["ind_high_seas_fishing"].sum()
    logger.info(f"  high_seas_fishing: {n:,} events ({n/len(df)*100:.2f}%)")

    # Aggregate tier 1: any indicator fires
    df["tier1_any"] = (
        df["ind_fishing_in_mpa"]
        | df["ind_unauthorized_foreign"]
        | df["ind_high_seas_fishing"]
    )
    n = df["tier1_any"].sum()
    logger.info(f"  Tier 1 total (union): {n:,} events ({n/len(df)*100:.2f}%)")

    return df


def compute_tier2_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute suspicious activity indicators — medium confidence signals.

    Indicators:
        encounter_at_sea: Vessel-to-vessel encounter (potential transshipment).
        loitering_anomaly: Excessive loitering hours for the vessel.
        unregistered_vessel: Fishing vessel with no registry match.
        nighttime_foreign: Foreign vessel fishing at night.

    Args:
        df: Events DataFrame with event_type, encounter_type, mmsi,
            reg_vessel_class, is_nighttime, is_foreign columns.

    Returns:
        DataFrame with tier2_* indicator columns added.
    """
    logger.info("--- Tier 2: Suspicious Activity Indicators ---")

    # Encounter at sea (any encounter = transshipment risk)
    df["ind_encounter_at_sea"] = (df["event_type"] == "encounter").astype(int)
    n = df["ind_encounter_at_sea"].sum()
    logger.info(f"  encounter_at_sea: {n:,} events ({n/len(df)*100:.2f}%)")

    # Loitering anomaly: loitering with very low speed (drifting/waiting)
    df["ind_loitering_anomaly"] = (
        (df["event_type"] == "loitering")
        & (df["loitering_avg_speed_knots"] < 1.0)
    ).astype(int)
    n = df["ind_loitering_anomaly"].sum()
    logger.info(f"  loitering_anomaly: {n:,} events ({n/len(df)*100:.2f}%)")

    # Unregistered vessel: fishing vessel with no registry data
    df["ind_unregistered_vessel"] = (
        (df["event_type"] == "fishing")
        & (df["reg_vessel_class"].isna())
    ).astype(int)
    n = df["ind_unregistered_vessel"].sum()
    logger.info(f"  unregistered_vessel: {n:,} events ({n/len(df)*100:.2f}%)")

    # Nighttime + foreign: foreign vessels fishing at night (avoid detection)
    df["ind_nighttime_foreign"] = (
        (df["event_type"] == "fishing")
        & (df["is_nighttime"] == True)
        & (df["is_foreign"] == True)
    ).astype(int)
    n = df["ind_nighttime_foreign"].sum()
    logger.info(f"  nighttime_foreign: {n:,} events ({n/len(df)*100:.2f}%)")

    # Aggregate tier 2: count of indicators
    df["tier2_count"] = (
        df["ind_encounter_at_sea"]
        + df["ind_loitering_anomaly"]
        + df["ind_unregistered_vessel"]
        + df["ind_nighttime_foreign"]
    )
    n = (df["tier2_count"] >= 1).sum()
    n2 = (df["tier2_count"] >= 2).sum()
    logger.info(f"  Tier 2 ≥1 indicator: {n:,} events ({n/len(df)*100:.2f}%)")
    logger.info(f"  Tier 2 ≥2 indicators: {n2:,} events ({n2/len(df)*100:.2f}%)")

    return df


def compute_tier3_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute behavioral anomaly indicators — lower confidence signals.

    Uses per-vessel behavioral features to flag anomalous patterns.

    Indicators:
        high_encounter_rate: Vessel encounter rate > 75th percentile.
        high_loitering_rate: Vessel loitering rate > 75th percentile.
        far_offshore: Operating > 90th percentile distance from shore.
        rapid_port_cycle: Port visit < 2 hours (smuggling indicator).

    Args:
        df: Events DataFrame with encounter_rate, loitering_rate,
            avg_distance_shore, port_visit_duration_hours columns.

    Returns:
        DataFrame with tier3_* indicator columns added.
    """
    logger.info("--- Tier 3: Behavioral Anomaly Indicators ---")

    # High encounter rate: > p75 of encounter_rate
    enc_p75 = df["encounter_rate"].quantile(0.75)
    df["ind_high_encounter_rate"] = (df["encounter_rate"] > enc_p75).astype(int)
    logger.info(f"  high_encounter_rate (> {enc_p75:.3f}): {df['ind_high_encounter_rate'].sum():,}")

    # High loitering rate: > p75 of loitering_rate
    loit_p75 = df["loitering_rate"].quantile(0.75)
    df["ind_high_loitering_rate"] = (df["loitering_rate"] > loit_p75).astype(int)
    logger.info(f"  high_loitering_rate (> {loit_p75:.3f}): {df['ind_high_loitering_rate'].sum():,}")

    # Far offshore: > p90 of avg_distance_shore
    shore_p90 = df["avg_distance_shore"].quantile(0.90)
    df["ind_far_offshore"] = (df["avg_distance_shore"] > shore_p90).astype(int)
    logger.info(f"  far_offshore (> {shore_p90:.1f} km): {df['ind_far_offshore'].sum():,}")

    # Rapid port cycle: port visit < 2 hours
    df["ind_rapid_port_cycle"] = (
        (df["event_type"] == "port_visit")
        & (df["port_visit_duration_hours"] < 2)
    ).astype(int)
    n = df["ind_rapid_port_cycle"].sum()
    logger.info(f"  rapid_port_cycle (<2h): {n:,}")

    # Aggregate tier 3: count of indicators
    df["tier3_count"] = (
        df["ind_high_encounter_rate"]
        + df["ind_high_loitering_rate"]
        + df["ind_far_offshore"]
        + df["ind_rapid_port_cycle"]
    )
    n = (df["tier3_count"] >= 1).sum()
    logger.info(f"  Tier 3 ≥1 indicator: {n:,} events ({n/len(df)*100:.2f}%)")

    return df


def compute_iuu_score(df: pd.DataFrame) -> pd.DataFrame:
    """Compute weighted IUU risk score from tier indicators.

    Score = (tier1_any * w1 + tier2_count/max2 * w2 + tier3_count/max3 * w3) / (w1 + w2 + w3)

    Normalized to [0, 1].

    Args:
        df: Events DataFrame with tier indicators computed.

    Returns:
        DataFrame with iuu_score column added.
    """
    logger.info("--- IUU Score Computation ---")

    # Tier 1: binary (any hard IUU indicator)
    t1 = df["tier1_any"].astype(float) * TIER1_WEIGHT

    # Tier 2: normalized count (0 to 1, capped at 2 indicators = full weight)
    t2 = (df["tier2_count"].clip(upper=2) / 2.0) * TIER2_WEIGHT

    # Tier 3: normalized count (0 to 1, capped at 2 indicators = full weight)
    t3 = (df["tier3_count"].clip(upper=2) / 2.0) * TIER3_WEIGHT

    # Normalize by max possible score
    max_score = TIER1_WEIGHT + TIER2_WEIGHT + TIER3_WEIGHT
    df["iuu_score"] = (t1 + t2 + t3) / max_score

    # Round to 4 decimal places
    df["iuu_score"] = df["iuu_score"].round(4)

    logger.info(f"  Score distribution:")
    for threshold in [0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0]:
        above = (df["iuu_score"] >= threshold).sum()
        logger.info(f"    ≥ {threshold:.1f}: {above:,} ({above/len(df)*100:.1f}%)")

    return df


def assign_iuu_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Assign categorical IUU labels based on score thresholds.

    Labels:
        normal: score < 0.15
        suspicious: 0.15 ≤ score < 0.3
        probable_iuu: 0.3 ≤ score < 0.5
        hard_iuu: score ≥ 0.5

    Args:
        df: Events DataFrame with iuu_score column.

    Returns:
        DataFrame with iuu_label column added.
    """
    logger.info("--- Label Assignment ---")

    conditions = [
        df["iuu_score"] >= HARD_IUU_THRESHOLD,
        df["iuu_score"] >= PROBABLE_IUU_THRESHOLD,
        df["iuu_score"] >= SUSPICIOUS_THRESHOLD,
    ]
    labels = ["hard_iuu", "probable_iuu", "suspicious"]
    df["iuu_label"] = np.select(conditions, labels, default="normal")

    logger.info(f"  Label distribution:")
    for label in ["normal", "suspicious", "probable_iuu", "hard_iuu"]:
        n = (df["iuu_label"] == label).sum()
        logger.info(f"    {label:15s}: {n:>8,} ({n/len(df)*100:.1f}%)")

    # Defense: top reasons per label
    logger.info(f"  Label defense (top indicators per label):")
    for label in ["hard_iuu", "probable_iuu", "suspicious"]:
        subset = df[df["iuu_label"] == label]
        if len(subset) == 0:
            continue
        logger.info(f"    {label} (n={len(subset):,}):")
        ind_cols = [c for c in df.columns if c.startswith("ind_")]
        for col in sorted(ind_cols):
            active = subset[col].sum()
            if active > 0:
                pct = active / len(subset) * 100
                logger.info(f"      {col}: {active:,} ({pct:.1f}%)")

    return df


def run_label_all() -> Path:
    """Run full label generation pipeline.

    Returns:
        Path to gfw_events_labeled.parquet
    """
    logger.info("Loading enriched events...")
    df = pd.read_parquet(INPUT / GFW_EVENTS_FULL)
    logger.info(f"Events: {len(df):,} rows × {len(df.columns)} cols")

    df = compute_tier1_indicators(df)
    df = compute_tier2_indicators(df)
    df = compute_tier3_indicators(df)
    df = compute_iuu_score(df)
    df = assign_iuu_labels(df)

    # Clean up intermediate columns
    for c in ["tier1_any", "tier2_count", "tier3_count"]:
        if c in df.columns:
            df.drop(columns=c, inplace=True)

    logger.info(f"FINAL: {len(df):,} rows × {len(df.columns)} cols")

    out = OUTPUT / GFW_EVENTS_LABELED
    df.to_parquet(out, index=False, compression="snappy")
    logger.info(f"✅ Saved to {out} ({out.stat().st_size / 1024 / 1024:.1f} MB)")
    del df
    gc.collect()
    return out
