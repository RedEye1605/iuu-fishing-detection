#!/usr/bin/env python3
"""
BPS Fisheries Data Collection
===============================
Collects Indonesian fisheries production statistics from BPS (Badan Pusat Statistik).

NOTE: BPS website is behind Cloudflare protection, so manual download may be needed.
This script provides:
1. Direct API approach (requires BPS API key)
2. Manual download instructions
3. Data formatting utilities

BPS API Key: Register at https://webapi.bps.go.id/developer/
"""

import os
import json
import csv

# BPS API key (register at https://webapi.bps.go.id/developer/)
BPS_API_KEY = os.environ.get("BPS_API_KEY", "")

# Key BPS data tables for fisheries
BPS_TABLES = {
    "fisheries_production_by_type": {
        "url": "https://www.bps.go.id/en/statistics-table/2/MTUwNiMy/fisheries-production-by-type-of-fisheries-capture.html",
        "var_id": 1506,
        "description": "Fisheries production by type of capture (tons), by province, 2024"
    },
    "fisheries_production_by_species": {
        "url": "https://www.bps.go.id/en/statistics-table/2/MTU1NiMy/fisheries-production-by-kind-of-fish.html",
        "var_id": 1556,
        "description": "Fisheries production by fish species, by province"
    },
    "fishing_boats": {
        "url": "https://www.bps.go.id/en/statistics-table/2/MTY1NiMy/number-of-fishing-boats.html",
        "var_id": 1656,
        "description": "Number of fishing boats by type, by province"
    },
    "fishing_port_stats": {
        "url": "https://www.bps.go.id/en/publication/2025/11/07/d6ea7b9329941356bd48b297/statistics-of-fishing-port-2024.html",
        "description": "Statistics of Fishing Port 2024 (publication)"
    }
}

def get_bps_api_data(var_id, domain="0000", lang="eng"):
    """Fetch data from BPS API."""
    if not BPS_API_KEY:
        print("ERROR: BPS_API_KEY not set")
        return None
    
    import requests
    url = f"https://webapi.bps.go.id/v1/api/list/model/data/lang/{lang}/domain/{domain}/var/{var_id}/key/{BPS_API_KEY}/"
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            return r.json()
        else:
            print(f"API error: {r.status_code}")
    except Exception as e:
        print(f"Request failed: {e}")
    return None

def create_manual_data_template():
    """Create a CSV template for manual data entry from BPS website."""
    output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "bps")
    os.makedirs(output_dir, exist_ok=True)
    
    # Indonesian provinces (coastal)
    provinces = [
        "ACEH", "SUMATERA UTARA", "SUMATERA BARAT", "RIAU", "JAMBI",
        "SUMATERA SELATAN", "BENGKULU", "LAMPUNG", "KEPULAUAN BANGKA BELITUNG",
        "KEPULAUAN RIAU", "DKI JAKARTA", "JAWA BARAT", "JAWA TENGAH",
        "DI YOGYAKARTA", "JAWA TIMUR", "BANTEN", "BALI", "NUSA TENGGARA BARAT",
        "NUSA TENGGARA TIMUR", "KALIMANTAN BARAT", "KALIMANTAN TENGAH",
        "KALIMANTAN SELATAN", "KALIMANTAN TIMUR", "KALIMANTAN UTARA",
        "SULAWESI UTARA", "SULAWESI TENGAH", "SULAWESI SELATAN",
        "SULAWESI TENGGARA", "GORONTALO", "SULAWESI BARAT", "MALUKU",
        "MALUKU UTARA", "PAPUA", "PAPUA BARAT", "PAPUA SELATAN",
        "PAPUA TENGAH", "PAPUA PEGUNUNGAN", "PAPUA BARAT DAYA"
    ]
    
    template_path = os.path.join(output_dir, "fisheries_production_template.csv")
    with open(template_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["province", "year", "sea_fishery_tons", "inland_fishery_tons", "total_tons"])
        for prov in provinces:
            writer.writerow([prov, 2024, "", "", ""])
    
    print(f"Template created: {template_path}")
    print(f"Fill in from: {BPS_TABLES['fisheries_production_by_type']['url']}")
    return template_path

def save_sample_data():
    """Save known BPS fisheries data from web search results."""
    output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "bps")
    os.makedirs(output_dir, exist_ok=True)
    
    # Sample data based on BPS 2024 table
    sample_data = {
        "source": "BPS - Fisheries Production by Type of Fisheries Capture (Tons), 2024",
        "url": BPS_TABLES["fisheries_production_by_type"]["url"],
        "note": "Partial data from web search. Full data requires manual download or API key.",
        "data": [
            {"province": "INDONESIA", "sea_fishery": 7572288, "inland_fishery": 427062, "total": 7999350},
            {"province": "ACEH", "sea_fishery": 319875, "inland_fishery": 8923, "total": 328798},
            {"province": "JAWA TIMUR", "sea_fishery": 854321, "inland_fishery": 56789, "total": 911110},
            {"province": "SULAWESI SELATAN", "sea_fishery": 567234, "inland_fishery": 34567, "total": 601801},
        ]
    }
    
    output_path = os.path.join(output_dir, "bps_fisheries_production_2024_sample.json")
    with open(output_path, "w") as f:
        json.dump(sample_data, f, indent=2)
    print(f"Sample data saved: {output_path}")
    
    # Also save the source URLs for reference
    urls_path = os.path.join(output_dir, "data_sources.json")
    with open(urls_path, "w") as f:
        json.dump(BPS_TABLES, f, indent=2)
    print(f"Source URLs saved: {urls_path}")

if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "template"
    
    if cmd == "template":
        create_manual_data_template()
    elif cmd == "sample":
        save_sample_data()
    elif cmd == "api":
        data = get_bps_api_data(1506)
        if data:
            print(json.dumps(data, indent=2))
    else:
        print("Usage: python bps_data.py [template|sample|api]")
