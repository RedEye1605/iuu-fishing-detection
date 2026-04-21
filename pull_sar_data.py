#!/usr/bin/env python3
"""
Pull GFW SAR presence data for Indonesia EEZ using 4Wings API.
"""

import json
import gzip
import requests
from datetime import datetime
import os

# Configuration
API_URL = "https://gateway.api.globalfishingwatch.org/v3/4wings/report"
TOKEN_FILE = "/home/rclaw/gemastik/.gfw_token"
OUTPUT_FILE = "/home/rclaw/gemastik/data/raw/gfw/4wings_sar_presence_indonesia_2020-2025.json.gz"
LOG_FILE = "/home/rclaw/gemastik/data/raw/gfw/download_log_v4.txt"

# Read token
with open(TOKEN_FILE, 'r') as f:
    token = f.read().strip()

headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

def log_message(message):
    """Append message to log file."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] {message}\n")
    print(message)

def try_eez_based():
    """Try EEZ-based pull using region ID."""
    log_message("Attempting EEZ-based pull with region ID 8371...")

    params = {
        "dataset": "public-global-sar-presence:latest"
    }

    payload = {
        "date-range": "2020-01-01,2025-04-30",
        "format": "JSON",
        "spatial-resolution": "LOW",
        "temporal-resolution": "MONTHLY",
        "region": {
            "dataset": "public-eez-areas",
            "id": 8371  # Indonesia EEZ
        }
    }

    try:
        response = requests.post(API_URL, headers=headers, params=params, json=payload, timeout=300)
        response.raise_for_status()

        data = response.json()
        log_message(f"EEZ-based request succeeded. Status: {response.status_code}")

        # Check if data contains actual results
        if 'entries' in data:
            log_message(f"Received {len(data['entries'])} entries")
        else:
            log_message(f"Data keys: {list(data.keys())}")

        return data

    except requests.exceptions.RequestException as e:
        log_message(f"EEZ-based request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            log_message(f"Response status: {e.response.status_code}")
            log_message(f"Response body: {e.response.text[:500]}")
        return None

def try_bbox_based():
    """Try bbox-based pull."""
    log_message("Attempting bbox-based pull...")

    params = {
        "dataset": "public-global-sar-presence:latest"
    }

    payload = {
        "date-range": "2020-01-01,2025-04-30",
        "format": "JSON",
        "spatial-resolution": "LOW",
        "temporal-resolution": "MONTHLY",
        "spatial-aggregation": {
            "type": "bbox",
            "geojson": {
                "type": "Polygon",
                "coordinates": [[
                    [95, -11],
                    [141, -11],
                    [141, 6],
                    [95, 6],
                    [95, -11]
                ]]
            }
        }
    }

    try:
        response = requests.post(API_URL, headers=headers, params=params, json=payload, timeout=300)
        response.raise_for_status()

        data = response.json()
        log_message(f"Bbox-based request succeeded. Status: {response.status_code}")

        if 'entries' in data:
            log_message(f"Received {len(data['entries'])} entries")
        else:
            log_message(f"Data keys: {list(data.keys())}")

        return data

    except requests.exceptions.RequestException as e:
        log_message(f"Bbox-based request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            log_message(f"Response status: {e.response.status_code}")
            log_message(f"Response body: {e.response.text[:500]}")
        return None

def save_data(data):
    """Save data to gzipped JSON file."""
    try:
        with gzip.open(OUTPUT_FILE, 'wt', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        # Get file size
        size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
        log_message(f"Data saved to {OUTPUT_FILE} ({size_mb:.2f} MB)")

        # Count entries
        if isinstance(data, dict) and 'entries' in data:
            num_entries = len(data['entries'])
            log_message(f"Total entries: {num_entries}")
            return num_entries
        elif isinstance(data, list):
            num_entries = len(data)
            log_message(f"Total entries (list): {num_entries}")
            return num_entries
        else:
            log_message(f"Data type: {type(data)}")
            return 0

    except Exception as e:
        log_message(f"Error saving data: {e}")
        return 0

def main():
    """Main execution."""
    log_message("=" * 60)
    log_message("Starting GFW SAR presence data pull for Indonesia EEZ")
    log_message("=" * 60)

    # Try EEZ-based first
    data = try_eez_based()

    # Fall back to bbox-based if EEZ fails
    if data is None:
        data = try_bbox_based()

    # Save data if we got something
    if data is not None:
        num_entries = save_data(data)
        log_message(f"Successfully retrieved and saved {num_entries} entries")
    else:
        log_message("ERROR: Both approaches failed. No data retrieved.")

    log_message("=" * 60)
    log_message("Script completed")
    log_message("=" * 60)

if __name__ == "__main__":
    main()
