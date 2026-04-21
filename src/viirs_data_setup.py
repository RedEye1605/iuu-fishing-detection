#!/usr/bin/env python3
"""
VIIRS Boat Detection Data Setup
=================================
VIIRS VBD data from EOG (Earth Observation Group) requires login.

This script:
1. Documents the data access process
2. Creates download templates for when credentials are available
3. Generates sample VBD-like data for development

REGISTRATION:
1. Visit https://eogdata.mines.edu/ (register for free account)
2. Navigate to VIIRS Products > VBD
3. Download Indonesia (idn) nightly CSV or monthly GeoTIFF

DIRECT DOWNLOAD URLS (after login):
- Nightly CSV: https://eogdata.mines.edu/wwwdata/viirs_products/vbd-pub/v23/idn/final/
- Monthly GeoTIFF: https://eogdata.mines.edu/wwwdata/viirs_products/vbd-pub/v23/idn/monthly/
- Global: https://eogdata.mines.edu/wwwdata/viirs_products/vbd-pub/v23/global-saa/

FILE NAMING:
- VBD_npp_dYYYYMMDD_idn_noaa_ops_v23.csv (nightly)
- VBD_npp_YYYYMM01-YYYYMM31_idn_qf1-2-3-8-10-pc_v23_c*.avg_rade9.tif (monthly)

QUALITY FLAGS:
1 = Boat, 2 = Weak Detection, 3 = Blurry Detection, 4 = Gas Flare
7 = Glow, 8 = Recurring Light, 10 = Weak and Blurry, 11 = Platform
"""

import os
import json
import csv
import numpy as np
import random

def generate_sample_vbd_data(output_dir, n_detections=5000):
    """Generate synthetic VBD detections for development."""
    random.seed(42)
    np.random.seed(42)
    
    # Indonesia fishing hotspots
    hotspots = [
        {"name": "Java Sea", "lon_range": (108, 115), "lat_range": (-7, -4), "weight": 0.3},
        {"name": "Malacca Strait", "lon_range": (100, 104), "lat_range": (1, 4), "weight": 0.2},
        {"name": "Celebes Sea", "lon_range": (119, 124), "lat_range": (-2, 4), "weight": 0.15},
        {"name": "Arafura Sea", "lon_range": (133, 140), "lat_range": (-9, -5), "weight": 0.15},
        {"name": "South China Sea", "lon_range": (108, 117), "lat_range": (-3, 3), "weight": 0.1},
        {"name": "Indian Ocean", "lon_range": (97, 105), "lat_range": (-9, -4), "weight": 0.1},
    ]
    
    detections = []
    for i in range(n_detections):
        # Weighted random zone selection
        zone = random.choices(hotspots, weights=[h["weight"] for h in hotspots])[0]
        
        lon = random.uniform(*zone["lon_range"])
        lat = random.uniform(*zone["lat_range"])
        
        # Date within 2024
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        hour = random.randint(0, 23)
        
        qf = random.choices(
            [1, 2, 3, 8, 10],
            weights=[0.5, 0.2, 0.1, 0.15, 0.05]
        )[0]
        
        detections.append({
            "id": i + 1,
            "date_gmt": f"2024{month:02d}{day:02d}",
            "time_gmt": f"{hour:02d}{random.randint(0,59):02d}",
            "lon": round(lon, 4),
            "lat": round(lat, 4),
            "quality_flag": qf,
            "radiance": round(random.uniform(0.5, 50.0), 3),
            "zone": zone["name"]
        })
    
    # Save as CSV
    output_path = os.path.join(output_dir, "sample_vbd_detections_2024.csv")
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=detections[0].keys())
        writer.writeheader()
        writer.writerows(detections)
    
    print(f"Generated {n_detections} VBD detections → {output_path}")
    
    # Save hotspot reference
    ref_path = os.path.join(output_dir, "fishing_hotspots.json")
    with open(ref_path, "w") as f:
        json.dump(hotspots, f, indent=2)
    
    return output_path

if __name__ == "__main__":
    output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "viirs")
    os.makedirs(output_dir, exist_ok=True)
    generate_sample_vbd_data(output_dir)
    
    # Create download instructions
    instructions = """
    VIIRS VBD DATA DOWNLOAD INSTRUCTIONS
    ======================================
    1. Register at https://eogdata.mines.edu/ (free account)
    2. After login, navigate to: https://eogdata.mines.edu/wwwdata/viirs_products/vbd-pub/v23/
    3. For Indonesia data, go to: /idn/final/ (nightly CSV) or /idn/monthly/ (GeoTIFF)
    4. Download files matching: VBD_npp_d2024*_idn_noaa_ops_v23.csv
    5. Place downloaded files in this directory (data/raw/viirs/)
    """
    with open(os.path.join(output_dir, "DOWNLOAD_INSTRUCTIONS.txt"), "w") as f:
        f.write(instructions)
    print("Download instructions saved.")
