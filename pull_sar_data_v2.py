#!/usr/bin/env python3
"""
Pull GFW SAR presence data for Indonesia EEZ using 4Wings API.
Trying GET request with query parameters.
"""

import json
import gzip
import requests
from datetime import datetime
import os
import urllib.parse

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

def try_eez_based_get():
    """Try EEZ-based pull using GET request."""
    log_message("Attempting EEZ-based pull with GET request and region ID 8371...")

    params = {
        "datasets": "public-global-sar-presence:latest",
        "date-range": "2020-01-01,2025-04-30",
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
        response = requests.get(API_URL, headers=headers, params=params, json=body, timeout=300)
        log_message(f"URL: {response.url[:200]}...")
        response.raise_for_status()

        data = response.json()
        log_message(f"EEZ-based GET request succeeded. Status: {response.status_code}")

        if 'entries' in data:
            log_message(f"Received {len(data['entries'])} entries")
        else:
            log_message(f"Data keys: {list(data.keys())}")

        return data

    except requests.exceptions.RequestException as e:
        log_message(f"EEZ-based GET request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            log_message(f"Response status: {e.response.status_code}")
            log_message(f"Response body: {e.response.text[:500]}")
        return None

def try_eez_based_post():
    """Try EEZ-based pull using POST with datasets in body."""
    log_message("Attempting EEZ-based pull with POST and datasets in body...")

    payload = {
        "datasets": ["public-global-sar-presence:latest"],
        "date-range": "2020-01-01,2025-04-30",
        "format": "JSON",
        "spatial-resolution": "LOW",
        "temporal-resolution": "MONTHLY",
        "region": {
            "dataset": "public-eez-areas",
            "id": 8371
        }
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=300)
        response.raise_for_status()

        data = response.json()
        log_message(f"EEZ-based POST request succeeded. Status: {response.status_code}")

        if 'entries' in data:
            log_message(f"Received {len(data['entries'])} entries")
        else:
            log_message(f"Data keys: {list(data.keys())}")

        return data

    except requests.exceptions.RequestException as e:
        log_message(f"EEZ-based POST request failed: {e}")
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

    # Try different approaches
    data = try_eez_based_post()

    if data is None:
        data = try_eez_based_get()

    # Save data if we got something
    if data is not None:
        num_entries = save_data(data)
        log_message(f"Successfully retrieved and saved {num_entries} entries")
    else:
        log_message("ERROR: All approaches failed. No data retrieved.")

    log_message("=" * 60)
    log_message("Script completed")
    log_message("=" * 60)

if __name__ == "__main__":
    main()
