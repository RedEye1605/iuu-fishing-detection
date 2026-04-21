#!/usr/bin/env python3
"""
Synthetic AIS Data Generator for IUU Fishing Detection
========================================================
Generates realistic synthetic AIS vessel tracking data for development
and testing of the ST-GAT model before real data is available.

Generates:
- Normal fishing trajectories in Indonesian waters
- Suspicious/IUU patterns (AIS gaps, zone violations, etc.)
- Multi-vessel interactions (encounters, transshipment)
"""

import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import json
import random

np.random.seed(42)
random.seed(42)

# Indonesia bounding box
INDO_BOUNDS = {
    "min_lon": 95.0, "max_lon": 141.0,
    "min_lat": -11.0, "max_lat": 6.0
}

# Key fishing zones
FISHING_ZONES = [
    {"name": "Malacca Strait", "bounds": [98, 2, 104, 6], "fishing_density": 0.8},
    {"name": "South China Sea", "bounds": [105, -3, 117, 5], "fishing_density": 0.9},
    {"name": "Java Sea", "bounds": [105, -8, 117, -3], "fishing_density": 0.95},
    {"name": "Celebes Sea", "bounds": [117, -3, 125, 5], "fishing_density": 0.7},
    {"name": "Banda Sea", "bounds": [119, -8, 133, -3], "fishing_density": 0.65},
    {"name": "Arafura Sea", "bounds": [131, -11, 141, -5], "fishing_density": 0.85},
    {"name": "Indian Ocean (West)", "bounds": [95, -11, 105, -5], "fishing_density": 0.6},
]

VESSEL_TYPES = {
    "fishing": {"speed_max": 12, "speed_fishing": 2.5, "turn_rate": 0.3, "count": 500},
    "cargo": {"speed_max": 18, "speed_fishing": 14, "turn_rate": 0.05, "count": 200},
    "tanker": {"speed_max": 15, "speed_fishing": 12, "turn_rate": 0.05, "count": 100},
    "passenger": {"speed_max": 22, "speed_fishing": 18, "turn_rate": 0.08, "count": 50},
}

def generate_mmsi():
    """Generate a fake Indonesian MMSI (starts with 525)."""
    return f"525{random.randint(100000, 999999)}"

def generate_vessel(vessel_type, config):
    """Generate vessel metadata."""
    return {
        "mmsi": generate_mmsi(),
        "vessel_type": vessel_type,
        "length": random.randint(10, 60) if vessel_type == "fishing" else random.randint(50, 300),
        "tonnage": random.randint(5, 500) if vessel_type == "fishing" else random.randint(500, 50000),
        "flag": "IDN" if random.random() > 0.15 else random.choice(["CHN", "VNM", "PHL", "MYS", "THA", "PNG"]),
    }

def generate_fishing_trajectory(vessel, zone, hours=24, iuu=False):
    """Generate a realistic fishing vessel trajectory."""
    bounds = zone["bounds"]
    start_lon = random.uniform(bounds[0], bounds[2])
    start_lat = random.uniform(bounds[1], bounds[3])
    config = VESSEL_TYPES.get(vessel["vessel_type"], VESSEL_TYPES["fishing"])
    
    points = []
    t = datetime(2024, random.randint(1, 12), random.randint(1, 28), 0, 0, 0)
    lon, lat = start_lon, start_lat
    speed = config["speed_max"] * random.uniform(0.3, 0.7)
    heading = random.uniform(0, 360)
    
    interval_minutes = 5  # AIS reporting interval
    
    for i in range(int(hours * 60 / interval_minutes)):
        # Decide behavior: transiting, fishing, or drifting
        behavior = "fishing" if random.random() < 0.6 else "transiting"
        
        if behavior == "fishing":
            speed = config["speed_fishing"] * random.uniform(0.5, 1.5)
            heading += random.gauss(0, config["turn_rate"] * 30)
        else:
            speed = config["speed_max"] * random.uniform(0.4, 0.8)
            heading += random.gauss(0, config["turn_rate"] * 5)
        
        # IUU patterns
        if iuu:
            # Pattern 1: AIS gap (transponder off)
            if random.random() < 0.02:
                gap_hours = random.randint(2, 12)
                t += timedelta(hours=gap_hours)
                # Jump position during gap
                lon += random.uniform(-0.5, 0.5)
                lat += random.uniform(-0.3, 0.3)
            
            # Pattern 2: Entering restricted area
            if random.random() < 0.005:
                # Move toward restricted coordinates
                lon += random.uniform(-0.1, 0.1)
                lat += random.uniform(-0.1, 0.1)
            
            # Pattern 3: Unusual speed changes (rendezvous)
            if random.random() < 0.01:
                speed = 0.1  # Near-stationary
        
        # Update position
        rad_heading = np.radians(heading)
        lon += speed * np.sin(rad_heading) * interval_minutes / 3600 * 0.01
        lat += speed * np.cos(rad_heading) * interval_minutes / 3600 * 0.01
        
        # Keep in bounds
        lon = np.clip(lon, bounds[0], bounds[2])
        lat = np.clip(lat, bounds[1], bounds[3])
        
        point = {
            "mmsi": vessel["mmsi"],
            "timestamp": t.isoformat(),
            "lon": round(lon, 6),
            "lat": round(lat, 6),
            "speed": round(speed, 2),
            "heading": round(heading % 360, 2),
            "behavior": behavior,
            "zone": zone["name"],
            "is_iuu": iuu
        }
        points.append(point)
        t += timedelta(minutes=interval_minutes)
    
    return points

def generate_dataset(n_normal=300, n_iuu=50):
    """Generate full dataset with normal and IUU trajectories."""
    all_points = []
    vessels = []
    
    for vtype, config in VESSEL_TYPES.items():
        count = int(config["count"] * n_normal / 500)
        for i in range(count):
            vessel = generate_vessel(vtype, config)
            vessels.append(vessel)
            zone = random.choice(FISHING_ZONES)
            hours = random.randint(8, 48)
            is_iuu = False
            points = generate_fishing_trajectory(vessel, zone, hours, iuu=is_iuu)
            all_points.extend(points)
    
    # Generate IUU vessels
    for i in range(n_iuu):
        vessel = generate_vessel("fishing", VESSEL_TYPES["fishing"])
        vessel["flag"] = random.choice(["CHN", "VNM", "PHL", "MYS"])  # Foreign flag
        vessel["is_iuu"] = True
        vessels.append(vessel)
        zone = random.choice(FISHING_ZONES)
        hours = random.randint(12, 72)
        points = generate_fishing_trajectory(vessel, zone, hours, iuu=True)
        all_points.extend(points)
    
    return pd.DataFrame(all_points), vessels

if __name__ == "__main__":
    print("Generating synthetic AIS dataset...")
    df, vessels = generate_dataset(n_normal=300, n_iuu=50)
    
    output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
    
    # Save trajectory data
    traj_path = os.path.join(output_dir, "omtad", "synthetic_ais_trajectories.csv")
    df.to_csv(traj_path, index=False)
    print(f"Trajectories saved: {traj_path} ({len(df)} points)")
    
    # Save vessel metadata
    vessels_path = os.path.join(output_dir, "omtad", "synthetic_vessels.json")
    with open(vessels_path, "w") as f:
        json.dump(vessels, f, indent=2)
    print(f"Vessels saved: {vessels_path} ({len(vessels)} vessels)")
    
    # Stats
    print(f"\nDataset Statistics:")
    print(f"  Total points: {len(df)}")
    print(f"  Total vessels: {len(vessels)}")
    print(f"  IUU vessels: {sum(1 for v in vessels if v.get('is_iuu'))}")
    print(f"  Normal vessels: {sum(1 for v in vessels if not v.get('is_iuu'))}")
    print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"  Zones: {df['zone'].unique().tolist()}")
