#!/usr/bin/env python3
"""
MPA (Marine Protected Area) Data Setup
========================================
Downloads and processes marine protected area boundaries for Indonesia.

Sources:
1. Protected Planet / WDPA - https://www.protectedplanet.net/country/IDN
2. MPAtlas - https://mpatlas.org/
3. Indonesia Ministry of Marine Affairs and Fisheries (KKP)

WDPA data requires registration but is free for non-commercial use.
This script provides instructions and creates sample data for development.
"""

import os
import json
import csv
import random
import numpy as np

def generate_sample_mpa_data(output_dir):
    """Generate sample MPA boundaries for Indonesia (for development)."""
    random.seed(42)
    
    # Known Indonesian MPAs (approximate coordinates)
    mpas = [
        {"name": "Taman Nasional Komodo", "type": "National Park", "lon": 119.5, "lat": -8.55, "area_km2": 1733},
        {"name": "Taman Nasional Bunaken", "type": "National Park", "lon": 124.75, "lat": 1.62, "area_km2": 890},
        {"name": "Taman Nasional Wakatobi", "type": "National Park", "lon": 123.6, "lat": -5.3, "area_km2": 1390},
        {"name": "Taman Nasional Karimunjawa", "type": "National Park", "lon": 110.4, "lat": -5.85, "area_km2": 1116},
        {"name": "Taman Nasional Teluk Cenderawasih", "type": "National Park", "lon": 134.9, "lat": -2.7, "area_km2": 14535},
        {"name": "Taman Nasional Kepulauan Seribu", "type": "National Park", "lon": 106.5, "lat": -5.6, "area_km2": 1079},
        {"name": "Taman Nasional Ujung Kulon", "type": "National Park", "lon": 105.33, "lat": -6.75, "area_km2": 1206},
        {"name": "Cenderawasih Bay MPA", "type": "Marine Sanctuary", "lon": 135.5, "lat": -3.0, "area_km2": 5000},
        {"name": "Raja Ampat MPA Network", "type": "Marine Sanctuary", "lon": 130.5, "lat": -0.5, "area_km2": 46000},
        {"name": "Savu Sea MPA", "type": "Marine Sanctuary", "lon": 122.0, "lat": -9.0, "area_km2": 33597},
        {"name": "Banda Sea MPA", "type": "Marine Sanctuary", "lon": 129.0, "lat": -5.0, "area_km2": 50000},
        {"name": "Bird's Head Seascape", "type": "Marine Sanctuary", "lon": 131.0, "lat": -1.5, "area_km2": 36000},
    ]
    
    # Generate bounding boxes for each MPA (approximate)
    for mpa in mpas:
        size = np.sqrt(mpa["area_km2"]) / 111  # rough degree conversion
        mpa["bbox"] = [
            round(mpa["lon"] - size/2, 4),
            round(mpa["lat"] - size/2, 4),
            round(mpa["lon"] + size/2, 4),
            round(mpa["lat"] + size/2, 4)
        ]
        mpa["is_no_take"] = random.random() < 0.3  # 30% chance of no-take zone
    
    # Save as JSON
    output_path = os.path.join(output_dir, "indonesia_mpa_sample.json")
    with open(output_path, "w") as f:
        json.dump(mpas, f, indent=2)
    print(f"Sample MPA data saved: {output_path} ({len(mpas)} MPAs)")
    
    # Also save as GeoJSON
    features = []
    for mpa in mpas:
        bbox = mpa["bbox"]
        features.append({
            "type": "Feature",
            "properties": {
                "name": mpa["name"],
                "type": mpa["type"],
                "area_km2": mpa["area_km2"],
                "is_no_take": mpa["is_no_take"]
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [bbox[0], bbox[1]], [bbox[2], bbox[1]],
                    [bbox[2], bbox[3]], [bbox[0], bbox[3]], [bbox[0], bbox[1]]
                ]]
            }
        })
    
    geojson = {"type": "FeatureCollection", "features": features}
    geojson_path = os.path.join(output_dir, "indonesia_mpa_sample.geojson")
    with open(geojson_path, "w") as f:
        json.dump(geojson, f, indent=2)
    print(f"GeoJSON saved: {geojson_path}")
    
    return mpas

if __name__ == "__main__":
    output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "gis")
    os.makedirs(output_dir, exist_ok=True)
    generate_sample_mpa_data(output_dir)
    
    # Download instructions
    instructions = """
    MPA / WDPA DATA DOWNLOAD INSTRUCTIONS
    =======================================
    
    Option 1: Protected Planet (WDPA)
    1. Visit https://www.protectedplanet.net/country/IDN
    2. Click "Download" to get WDPA data for Indonesia
    3. Requires free registration
    4. Select "Marine" protected areas only
    5. Place shapefile in data/raw/gis/
    
    Option 2: MPAtlas
    1. Visit https://old.mpatlas.org/data/download/
    2. Download global MPA shapefile
    3. Filter for Indonesia (ISO = IDN)
    
    Option 3: KKP Indonesia (government)
    1. Visit https://kkp.go.id/
    2. Look for "Kawasan Konservasi Perairan" (KKP) data
    3. May require Bahasa Indonesia navigation
    """
    with open(os.path.join(output_dir, "MPA_DOWNLOAD_INSTRUCTIONS.txt"), "w") as f:
        f.write(instructions)
    print("Download instructions saved.")
