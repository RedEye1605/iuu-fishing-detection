#!/usr/bin/env python3
"""
GFW API Setup and Test Script
==============================
Global Fishing Watch API integration for IUU Fishing Detection.

REGISTRATION REQUIRED:
1. Visit https://globalfishingwatch.org/our-apis/
2. Create a free account
3. Request API access
4. Set your API token: export GFW_API_TOKEN="your_token_here"

Available endpoints:
- Vessel search: /vessels/search
- Vessel track: /vessels/track
- Fishing events: /events?fishing
- Encounters: /events?encounter
- Loitering: /events?loitering
- AIS presence: /4wings/report
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta

API_BASE = "https://api.globalfishingwatch.org/v3"
API_TOKEN = os.environ.get("GFW_API_TOKEN", "")

def get_headers():
    if not API_TOKEN:
        print("ERROR: GFW_API_TOKEN not set. Run: export GFW_API_TOKEN='your_token'")
        sys.exit(1)
    return {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"}

def test_connection():
    """Test API connection."""
    try:
        r = requests.get(f"{API_BASE}/vessels/search", 
                        headers=get_headers(), 
                        params={"query": "fishing", "limit": 1})
        if r.status_code == 200:
            print("✅ GFW API connected successfully!")
            return True
        elif r.status_code == 401:
            print("❌ Unauthorized - check your API token")
        else:
            print(f"❌ Error: {r.status_code} - {r.text[:200]}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
    return False

def get_indonesia_fishing_events(start_date, end_date, limit=100):
    """
    Get fishing events in Indonesian EEZ.
    Bounding box roughly: 95-141°E, -11°S to 6°N
    """
    params = {
        "datasets[]": "public-fishing-event",
        "startDate": start_date,
        "endDate": end_date,
        "geometry": json.dumps({
            "type": "Polygon",
            "coordinates": [[
                [95, -11], [141, -11], [141, 6], [95, 6], [95, -11]
            ]]
        }),
        "limit": limit
    }
    r = requests.get(f"{API_BASE}/events", headers=get_headers(), params=params)
    return r.json() if r.status_code == 200 else None

def get_vessel_track(vessel_id, start_date, end_date):
    """Get vessel track data."""
    params = {
        "datasets[]": "public-global-ais",
        "startDate": start_date,
        "endDate": end_date,
        "binary": "false"
    }
    r = requests.get(f"{API_BASE}/vessels/{vessel_id}/track", 
                     headers=get_headers(), params=params)
    return r.json() if r.status_code == 200 else None

def get_encounter_events(start_date, end_date, limit=100):
    """Get encounter events (potential transshipment)."""
    params = {
        "datasets[]": "public-encounter-event",
        "startDate": start_date,
        "endDate": end_date,
        "limit": limit
    }
    r = requests.get(f"{API_BASE}/events", headers=get_headers(), params=params)
    return r.json() if r.status_code == 200 else None

def bulk_download_indonesia_data(year=2023):
    """
    Download bulk fishing data for Indonesian waters.
    Processes quarterly to stay within rate limits.
    """
    quarters = [
        (f"{year}-01-01", f"{year}-03-31", "Q1"),
        (f"{year}-04-01", f"{year}-06-30", "Q2"),
        (f"{year}-07-01", f"{year}-09-30", "Q3"),
        (f"{year}-10-01", f"{year}-12-31", "Q4"),
    ]
    
    all_events = []
    for start, end, q in quarters:
        print(f"Fetching {q}: {start} to {end}...")
        events = get_indonesia_fishing_events(start, end)
        if events:
            count = len(events.get("entries", []))
            print(f"  Found {count} events")
            all_events.extend(events.get("entries", []))
        else:
            print(f"  Failed to fetch {q}")
    
    # Save to processed data
    output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "gfw")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"gfw_indonesia_fishing_{year}.json")
    with open(output_file, "w") as f:
        json.dump(all_events, f, indent=2)
    print(f"\nSaved {len(all_events)} events to {output_file}")
    return all_events

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "test":
            test_connection()
        elif cmd == "download":
            year = int(sys.argv[2]) if len(sys.argv) > 2 else 2023
            bulk_download_indonesia_data(year)
        else:
            print(f"Unknown command: {cmd}")
    else:
        print("Usage: python gfw_api_setup.py [test|download] [year]")
        print("\nSet GFW_API_TOKEN environment variable first!")
