#!/usr/bin/env python3
"""
BMKG Marine Weather Data Setup
================================
Indonesian meteorological data for maritime conditions.

Sources:
1. BMKG API (free, no registration): https://data.bmkg.go.id/
2. BMKG Marine: https://maritim.bmkg.go.id/
3. NOAA GFS: Global weather model (free)
"""

import os
import json
import csv
import random
import numpy as np
import requests
from datetime import datetime, timedelta

BMKG_API_BASE = "https://data.bmkg.go.id/DataMKG/MEWS/DigitalForecast/"

def get_bmkg_weather():
    """Fetch weather data from BMKG open API."""
    try:
        # BMKG provides XML weather data by region
        # Region codes: Indonesia divided into forecast areas
        url = f"{BMKG_API_BASE}DigitalForecast-HoChiMinh.xml"  # Closest public endpoint
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.text
    except Exception as e:
        print(f"BMKG fetch failed: {e}")
    return None

def generate_sample_marine_weather(output_dir, n_days=365):
    """Generate synthetic marine weather data for Indonesian waters."""
    random.seed(42)
    np.random.seed(42)
    
    zones = [
        {"name": "Malacca Strait", "lon": 101, "lat": 3},
        {"name": "South China Sea", "lon": 110, "lat": 2},
        {"name": "Java Sea West", "lon": 108, "lat": -6},
        {"name": "Java Sea East", "lon": 115, "lat": -5},
        {"name": "Celebes Sea", "lon": 121, "lat": 2},
        {"name": "Banda Sea", "lon": 128, "lat": -5},
        {"name": "Arafura Sea", "lon": 136, "lat": -7},
        {"name": "Indian Ocean South", "lon": 100, "lat": -7},
    ]
    
    records = []
    start_date = datetime(2024, 1, 1)
    
    for day in range(n_days):
        date = start_date + timedelta(days=day)
        for zone in zones:
            # Seasonal variation (monsoon patterns)
            month = date.month
            if month in [12, 1, 2]:  # NW Monsoon
                wind_speed_base = 15 + zone["lat"] * (-1)  # Stronger in south
                wave_height_base = 1.5 + random.uniform(0, 1.5)
            elif month in [6, 7, 8]:  # SE Monsoon
                wind_speed_base = 12 + random.uniform(0, 5)
                wave_height_base = 1.2 + random.uniform(0, 1.0)
            else:  # Transition
                wind_speed_base = 8 + random.uniform(0, 4)
                wave_height_base = 0.8 + random.uniform(0, 0.8)
            
            wind_speed = max(0, wind_speed_base + random.gauss(0, 3))
            wave_height = max(0.1, wave_height_base + random.gauss(0, 0.3))
            
            records.append({
                "date": date.strftime("%Y-%m-%d"),
                "zone": zone["name"],
                "lon": zone["lon"],
                "lat": zone["lat"],
                "wind_speed_knots": round(wind_speed, 1),
                "wave_height_m": round(wave_height, 2),
                "sea_surface_temp_c": round(28 + random.uniform(-2, 2), 1),
                "visibility_km": round(max(1, 10 + random.gauss(0, 3)), 1),
                "precipitation_mm": round(max(0, random.gauss(5, 8)), 1),
            })
    
    output_path = os.path.join(output_dir, "marine_weather_2024.csv")
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)
    
    print(f"Marine weather data saved: {output_path} ({len(records)} records)")
    return output_path

if __name__ == "__main__":
    output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "bmkg")
    os.makedirs(output_dir, exist_ok=True)
    generate_sample_marine_weather(output_dir)
