"""
Phase 3 Step 3.5: Cross-Source Enrichment

Enrich GFW events with: weather, VIIRS proximity, SAR density, effort density, behavioral features.
Output: data/processed/gfw_events_full.parquet
"""

from __future__ import annotations
import gc, logging
from pathlib import Path
import pandas as pd
import numpy as np

INPUT = Path("data/processed")
OUTPUT = Path("data/processed")


def get_weather_zone(lat, lon):
    if pd.isna(lat) or pd.isna(lon): return "unknown"
    if lat > -3 and lon > 120: return "Celebes Sea"
    if lat > -6 and lon > 110: return "Banda Sea"
    if lon > 115: return "Java Sea West"
    return "Malacca Strait"


def run_step_3_5():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    
    print("=" * 60)
    print("STEP 3.5: CROSS-SOURCE ENRICHMENT")
    print("=" * 60)
    
    df = pd.read_parquet(INPUT / "gfw_events_enriched.parquet")
    print(f"Events: {len(df):,} rows × {len(df.columns)} cols")
    
    # Ensure temporal columns
    df["ev_year"] = df["start_time"].dt.year
    df["ev_month"] = df["start_time"].dt.month
    df["ev_date"] = df["start_time"].dt.date
    
    # ===== 3.5a: WEATHER =====
    print("\n--- 3.5a: Weather ---")
    weather = pd.read_parquet(INPUT / "weather.parquet")
    weather["date"] = pd.to_datetime(weather["date"])
    weather["w_month"] = weather["date"].dt.month
    weather["w_year"] = weather["date"].dt.year
    w_monthly = weather.groupby(["zone", "w_year", "w_month"]).mean(numeric_only=True).reset_index()
    w_monthly.columns = [f"weather_{c}" if c not in ["zone","w_year","w_month"] else c for c in w_monthly.columns]
    
    df["weather_zone"] = df.apply(lambda r: get_weather_zone(r["lat"], r["lon"]), axis=1)
    df = df.merge(w_monthly, left_on=["weather_zone","ev_year","ev_month"], 
                  right_on=["zone","w_year","w_month"], how="left")
    for c in ["zone","w_year","w_month","weather_zone"]:
        if c in df.columns: df.drop(columns=c, inplace=True)
    wf = df.filter(like="weather_").notna().any(axis=1).sum()
    print(f"  Enriched: {wf:,} / {len(df):,} ({wf/len(df)*100:.1f}%)")
    
    # ===== 3.5b: VIIRS =====
    print("\n--- 3.5b: VIIRS ---")
    viirs = pd.read_parquet(INPUT / "viirs_detections.parquet")
    viirs["grid_lat"] = (viirs["lat"] * 10).round(0) / 10
    viirs["grid_lon"] = (viirs["lon"] * 10).round(0) / 10
    viirs["vdate"] = pd.to_datetime(viirs["date_gmt"]).dt.date
    
    viirs_counts = viirs.groupby(["grid_lat","grid_lon","vdate"]).agg(
        viirs_count=("id","count"), viirs_avg_radiance=("radiance","mean")
    ).reset_index()
    
    df = df.merge(viirs_counts, left_on=["grid_lat","grid_lon","ev_date"],
                  right_on=["grid_lat","grid_lon","vdate"], how="left")
    df["viirs_count"] = df["viirs_count"].fillna(0).astype(int)
    df["viirs_detection_nearby"] = df["viirs_count"] > 0
    df["viirs_avg_radiance"] = df["viirs_avg_radiance"].fillna(0)
    if "vdate" in df.columns: df.drop(columns="vdate", inplace=True)
    print(f"  VIIRS nearby: {df['viirs_detection_nearby'].sum():,} events")
    
    # ===== 3.5c: SAR DENSITY =====
    print("\n--- 3.5c: SAR Density ---")
    sar = pd.read_parquet(INPUT / "sar_presence_clean.parquet",
                          columns=["lat","lon","year","month","detections","mmsi"])
    sar["grid_lat"] = (sar["lat"] * 10).round(0) / 10
    sar["grid_lon"] = (sar["lon"] * 10).round(0) / 10
    sar_density = sar.groupby(["grid_lat","grid_lon","year","month"]).agg(
        sar_total_detections=("detections","sum"),
        sar_unique_vessels=("mmsi","nunique"),
    ).reset_index()
    
    df = df.merge(sar_density, left_on=["grid_lat","grid_lon","ev_year","ev_month"],
                  right_on=["grid_lat","grid_lon","year","month"], how="left", suffixes=("","_sar"))
    df["sar_total_detections"] = df["sar_total_detections"].fillna(0)
    df["sar_unique_vessels"] = df["sar_unique_vessels"].fillna(0).astype(int)
    for c in ["year","month"]:
        if c in df.columns: df.drop(columns=c, inplace=True)
    print(f"  SAR enriched: {(df['sar_total_detections']>0).sum():,} events")
    del sar, sar_density; gc.collect()
    
    # ===== 3.5d: EFFORT DENSITY =====
    print("\n--- 3.5d: Effort Density ---")
    effort = pd.read_parquet(INPUT / "fishing_effort_clean.parquet",
                              columns=["lat","lon","fishing_hours","year","month"])
    effort["grid_lat"] = (effort["lat"] * 10).round(0) / 10
    effort["grid_lon"] = (effort["lon"] * 10).round(0) / 10
    eff_density = effort.groupby(["grid_lat","grid_lon","year","month"]).agg(
        effort_hours_in_cell=("fishing_hours","sum"),
        effort_vessels_in_cell=("fishing_hours","count"),
    ).reset_index()
    
    df = df.merge(eff_density, left_on=["grid_lat","grid_lon","ev_year","ev_month"],
                  right_on=["grid_lat","grid_lon","year","month"], how="left", suffixes=("","_eff"))
    df["effort_hours_in_cell"] = df["effort_hours_in_cell"].fillna(0)
    df["effort_vessels_in_cell"] = df["effort_vessels_in_cell"].fillna(0).astype(int)
    for c in ["year","month"]:
        if c in df.columns: df.drop(columns=c, inplace=True)
    print(f"  Effort enriched: {(df['effort_hours_in_cell']>0).sum():,} events")
    del effort, eff_density; gc.collect()
    
    # ===== BEHAVIORAL FEATURES =====
    print("\n--- Behavioral Features ---")
    behavior = pd.read_parquet(INPUT / "vessel_behavioral_features.parquet")
    df = df.merge(behavior, on="mmsi", how="left")
    print(f"  After merge: {len(df):,} × {len(df.columns)} cols")
    
    # Cleanup temp columns
    for c in ["ev_year","ev_month","ev_date"]:
        if c in df.columns: df.drop(columns=c, inplace=True)
    
    # Drop duplicate columns from merges
    dup_cols = [c for c in df.columns if c.endswith("_sar") or c.endswith("_eff")]
    for c in dup_cols: df.drop(columns=c, inplace=True)
    
    # ===== FINAL =====
    print(f"\n{'='*60}")
    print("FINAL ENRICHED EVENTS")
    print(f"{'='*60}")
    print(f"Shape: {len(df):,} rows × {len(df.columns)} cols")
    print(f"Columns: {sorted(df.columns.tolist())}")
    
    out = OUTPUT / "gfw_events_full.parquet"
    df.to_parquet(out, index=False, compression="snappy")
    sz = out.stat().st_size / 1024 / 1024
    print(f"\n✅ Saved to {out} ({sz:.1f} MB)")


if __name__ == "__main__":
    run_step_3_5()
