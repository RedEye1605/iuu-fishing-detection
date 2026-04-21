"""
Phase 3 Step 3.1+3.3: Vessel Profile & Temporal Features

Step 3.1: Join events with vessel registry → add vessel features
Step 3.3: Duration categories (temporal features already added in Phase 2)
Output: data/processed/gfw_events_enriched.parquet
"""

from __future__ import annotations
import gc, logging
from pathlib import Path
import pandas as pd
import numpy as np

INPUT = Path("data/processed")
OUTPUT = Path("data/processed")


def run_step_3_1():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    
    print("=" * 60)
    print("STEP 3.1: VESSEL PROFILE FEATURES")
    print("=" * 60)
    
    # Load events
    df = pd.read_parquet(INPUT / "gfw_events_clean.parquet")
    print(f"Events: {len(df):,} rows × {len(df.columns)} cols")
    
    # Load vessel registry
    vessels = pd.read_parquet(INPUT / "vessel_registry_dedup.parquet")
    print(f"Vessel registry: {len(vessels):,} rows")
    
    # Build lookup: mmsi → vessel features (convert registry MMSI to string)
    v_lookup = vessels.drop_duplicates(subset=["mmsi"]).copy()
    v_lookup.index = v_lookup["mmsi"].astype(str)
    v_lookup = v_lookup.drop(columns=["mmsi"])
    
    # Map vessel features to events
    print("\nMapping vessel features...")
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
            print(f"  {dst}: {filled:,} filled ({filled/len(df)*100:.1f}%)")
    
    # Derived features
    print("Computing derived features...")
    
    # is_fishing_vessel
    df["is_fishing_vessel"] = (
        (df.get("reg_self_reported_fishing", pd.Series(dtype=bool)) == True) |
        (df.get("reg_vessel_class", pd.Series(dtype=str)).str.contains(
            "fishing|trawl|seine|longline|gillnet|dredge|squid", case=False, na=False)) |
        (df["vessel_type"].str.contains("fishing|trawl|seine|longline|gillnet", case=False, na=False))
    )
    
    # size_category
    def size_cat(length):
        if pd.isna(length): return "unknown"
        if length < 12: return "small"
        if length < 24: return "medium"
        return "large"
    df["size_category"] = df["reg_length_m"].map(size_cat)
    
    # tonnage_per_length (density proxy)
    df["tonnage_per_length"] = np.where(
        df["reg_length_m"] > 0,
        df["reg_tonnage_gt"] / df["reg_length_m"],
        np.nan
    )
    
    # Duration category
    df["duration_category"] = pd.cut(
        df["duration_hours"],
        bins=[-0.01, 2, 8, float("inf")],
        labels=["short", "medium", "long"]
    )
    
    # Grid cell (0.1° ≈ 11km)
    df["grid_lat"] = (df["lat"] * 10).round(0) / 10
    df["grid_lon"] = (df["lon"] * 10).round(0) / 10
    
    # Nearest port (from ports table)
    import json
    with open(INPUT.parent / "raw" / "gfw" / "osm_indonesia_ports_manual.json") as f:
        ports = json.load(f)
    
    print(f"Computing nearest port from {len(ports)} ports...")
    port_lats = np.array([p["lat"] for p in ports])
    port_lons = np.array([p["lon"] for p in ports])
    port_names = [p["name"] for p in ports]
    
    # Vectorized nearest port (haversine approximation)
    event_lats = df["lat"].values
    event_lons = df["lon"].values
    
    # Simple euclidean for nearest (good enough for nearest-port lookup)
    min_idx = np.zeros(len(df), dtype=int)
    min_dist = np.full(len(df), np.inf)
    
    for i, (plat, plon) in enumerate(zip(port_lats, port_lons)):
        d = np.sqrt((event_lats - plat)**2 + (event_lons - plon)**2)
        mask = d < min_dist
        min_idx[mask] = i
        min_dist[mask] = d[mask]
    
    # Convert degree distance to km (approximate)
    df["nearest_port_name"] = [port_names[i] for i in min_idx]
    df["nearest_port_dist_km"] = min_dist * 111  # 1° ≈ 111km
    
    # Sea zone classification (rough bounding boxes)
    def classify_sea(lat, lon):
        if pd.isna(lat) or pd.isna(lon): return "unknown"
        if -8 <= lat <= -5 and 105 <= lon <= 115: return "Java Sea"
        if -8 <= lat <= -2 and 115 <= lon <= 120: return "Bali Sea"
        if -5 <= lat <= 2 and 108 <= lon <= 120: return "Karimata Strait"
        if 0 <= lat <= 5 and 120 <= lon <= 128: return "Celebes Sea"
        if -4 <= lat <= 2 and 128 <= lon <= 141: return "Banda Sea"
        if -8 <= lat <= -3 and 110 <= lon <= 116: return "Indian Ocean (S)"
        if 2 <= lat <= 6 and 95 <= lon <= 105: return "Malacca Strait"
        if -2 <= lat <= 4 and 130 <= lon <= 141: return "Arafura Sea"
        if -8 <= lat <= -2 and 120 <= lon <= 130: return "Timor Sea"
        return "Other"
    
    df["sea_zone"] = df.apply(lambda r: classify_sea(r["lat"], r["lon"]), axis=1)
    
    del v_lookup, vessels; gc.collect()
    
    # ===== VALIDATION =====
    print(f"\n--- Validation ---")
    print(f"Shape: {len(df):,} rows × {len(df.columns)} cols")
    print(f"\nSize category:")
    print(df["size_category"].value_counts().to_string())
    print(f"\nSea zone (top 10):")
    print(df["sea_zone"].value_counts().head(10).to_string())
    print(f"\nDuration category:")
    print(df["duration_category"].value_counts().to_string())
    print(f"\nis_fishing_vessel: {df['is_fishing_vessel'].sum():,} / {len(df):,}")
    print(f"vessel_class fill rate: {df['reg_vessel_class'].notna().mean()*100:.1f}%")
    print(f"length_m fill rate: {df['reg_length_m'].notna().mean()*100:.1f}%")
    
    # Save
    out = OUTPUT / "gfw_events_enriched.parquet"
    df.to_parquet(out, index=False, compression="snappy")
    sz = out.stat().st_size / 1024 / 1024
    print(f"\n✅ Saved to {out} ({sz:.1f} MB)")
    del df; gc.collect()


if __name__ == "__main__":
    run_step_3_1()
