#!/usr/bin/env python3
"""
Pull GFW SAR presence data for Indonesia EEZ using 4Wings API.
Pulling data year by year to stay within 366-day limit.
"""

import json
import gzip
import requests
from datetime import datetime, timedelta
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

def pull_data_for_date_range(start_date, end_date, year_str):
    """Pull data for a specific date range."""
    log_message(f"Pulling data for {year_str}: {start_date} to {end_date}...")

    base_url = "https://gateway.api.globalfishingwatch.org/v3/4wings/report"
    query_params = {
        "datasets[0]": "public-global-sar-presence:latest",
        "date-range": f"{start_date},{end_date}",
        "format": "JSON",
        "spatial-resolution": "LOW",
        "temporal-resolution": "MONTHLY"
    }

    body = {
        "region": {
            "dataset": "public-eez-areas",
            "id": 8371
        }
    }

    try:
        response = requests.post(base_url, headers=headers, params=query_params, json=body, timeout=300)
        response.raise_for_status()

        data = response.json()
        log_message(f"  Success for {year_str}. Status: {response.status_code}")

        if 'entries' in data:
            log_message(f"  Received {len(data['entries'])} entries for {year_str}")
            return data['entries']
        else:
            log_message(f"  Data keys: {list(data.keys())}")
            return []

    except requests.exceptions.RequestException as e:
        log_message(f"  Failed for {year_str}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            log_message(f"  Response status: {e.response.status_code}")
            log_message(f"  Response body: {e.response.text[:500]}")
        return None

def pull_all_data():
    """Pull data year by year from 2020 to 2025."""
    all_entries = []

    # Define year ranges
    years = [
        ("2020", "2020-01-01", "2020-12-31"),
        ("2021", "2021-01-01", "2021-12-31"),
        ("2022", "2022-01-01", "2022-12-31"),
        ("2023", "2023-01-01", "2023-12-31"),
        ("2024", "2024-01-01", "2024-12-31"),
        ("2025", "2025-01-01", "2025-04-30")  # Partial year as specified
    ]

    for year_str, start, end in years:
        entries = pull_data_for_date_range(start, end, year_str)

        if entries is not None:
            all_entries.extend(entries)
        else:
            log_message(f"WARNING: Failed to get data for {year_str}, continuing...")

    return all_entries

def save_data(entries):
    """Save data to gzipped JSON file."""
    try:
        # Create the data structure
        data = {
            "metadata": {
                "dataset": "public-global-sar-presence:latest",
                "region": {
                    "dataset": "public-eez-areas",
                    "id": 8371,
                    "name": "Indonesia EEZ"
                },
                "date_range": "2020-01-01,2025-04-30",
                "spatial_resolution": "LOW",
                "temporal_resolution": "MONTHLY",
                "total_entries": len(entries),
                "download_date": datetime.now().isoformat()
            },
            "entries": entries
        }

        with gzip.open(OUTPUT_FILE, 'wt', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        # Get file size
        size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
        log_message(f"Data saved to {OUTPUT_FILE} ({size_mb:.2f} MB)")
        log_message(f"Total entries: {len(entries)}")

        return len(entries)

    except Exception as e:
        log_message(f"Error saving data: {e}")
        return 0

def main():
    """Main execution."""
    log_message("=" * 60)
    log_message("Starting GFW SAR presence data pull for Indonesia EEZ")
    log_message("Date range: 2020-01-01 to 2025-04-30")
    log_message("=" * 60)

    # Pull all data
    all_entries = pull_all_data()

    if all_entries:
        num_entries = save_data(all_entries)
        log_message("=" * 60)
        log_message(f"SUCCESS: Retrieved and saved {num_entries} entries")
        log_message("=" * 60)
    else:
        log_message("=" * 60)
        log_message("ERROR: Failed to retrieve any data")
        log_message("=" * 60)

if __name__ == "__main__":
    main()
