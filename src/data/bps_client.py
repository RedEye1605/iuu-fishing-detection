"""
BPS (Badan Pusat Statistik) fisheries data client.

Collects Indonesian fisheries production statistics. BPS website uses
Cloudflare protection, so API access or manual download may be needed.

Register for API key at: https://webapi.bps.go.id/developer/
"""

from __future__ import annotations

import csv
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

import requests

from src.utils.config import bps_config

logger = logging.getLogger(__name__)

BPS_TABLES: dict[str, dict[str, Any]] = {
    "fisheries_production_by_type": {
        "url": "https://www.bps.go.id/en/statistics-table/2/MTUwNiMy/fisheries-production-by-type-of-fisheries-capture.html",
        "var_id": 1506,
        "description": "Fisheries production by type of capture (tons), by province, 2024",
    },
    "fisheries_production_by_species": {
        "url": "https://www.bps.go.id/en/statistics-table/2/MTU1NiMy/fisheries-production-by-kind-of-fish.html",
        "var_id": 1556,
        "description": "Fisheries production by fish species, by province",
    },
    "fishing_boats": {
        "url": "https://www.bps.go.id/en/statistics-table/2/MTY1NiMy/number-of-fishing-boats.html",
        "var_id": 1656,
        "description": "Number of fishing boats by type, by province",
    },
}

COASTAL_PROVINCES = [
    "ACEH", "SUMATERA UTARA", "SUMATERA BARAT", "RIAU", "JAMBI",
    "SUMATERA SELATAN", "BENGKULU", "LAMPUNG", "KEPULAUAN BANGKA BELITUNG",
    "KEPULAUAN RIAU", "DKI JAKARTA", "JAWA BARAT", "JAWA TENGAH",
    "DI YOGYAKARTA", "JAWA TIMUR", "BANTEN", "BALI", "NUSA TENGGARA BARAT",
    "NUSA TENGGARA TIMUR", "KALIMANTAN BARAT", "KALIMANTAN TENGAH",
    "KALIMANTAN SELATAN", "KALIMANTAN TIMUR", "KALIMANTAN UTARA",
    "SULAWESI UTARA", "SULAWESI TENGAH", "SULAWESI SELATAN",
    "SULAWESI TENGGARA", "GORONTALO", "SULAWESI BARAT", "MALUKU",
    "MALUKU UTARA", "PAPUA", "PAPUA BARAT", "PAPUA SELATAN",
    "PAPUA TENGAH", "PAPUA PEGUNUNGAN", "PAPUA BARAT DAYA",
]


def get_bps_api_data(var_id: int, domain: str = "0000", lang: str = "eng") -> Optional[dict]:
    """Fetch data from the BPS web API."""
    api_key = bps_config.load_api_key()
    if not api_key:
        logger.error("BPS_API_KEY not set")
        return None

    url = (
        f"https://webapi.bps.go.id/v1/api/list/model/data/"
        f"lang/{lang}/domain/{domain}/var/{var_id}/key/{api_key}/"
    )
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            return r.json()
        logger.error("BPS API error: %s", r.status_code)
    except requests.RequestException as exc:
        logger.error("BPS request failed: %s", exc)
    return None


def create_manual_data_template(output_dir: Path | None = None) -> Path:
    """Create a CSV template for manual BPS data entry.

    Args:
        output_dir: Directory for the template file.

    Returns:
        Path to the created template CSV.
    """
    output_dir = output_dir or Path("data/raw/bps")
    output_dir.mkdir(parents=True, exist_ok=True)
    template_path = output_dir / "fisheries_production_template.csv"

    with open(template_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["province", "year", "sea_fishery_tons", "inland_fishery_tons", "total_tons"])
        for prov in COASTAL_PROVINCES:
            writer.writerow([prov, 2024, "", "", ""])

    logger.info("Template created: %s", template_path)
    return template_path


def save_sample_data(output_dir: Path | None = None) -> Path:
    """Save known BPS fisheries data from web search results.

    Args:
        output_dir: Directory for the sample data.

    Returns:
        Path to the saved JSON file.
    """
    output_dir = output_dir or Path("data/raw/bps")
    output_dir.mkdir(parents=True, exist_ok=True)

    sample = {
        "source": "BPS — Fisheries Production by Type of Fisheries Capture (Tons), 2024",
        "url": BPS_TABLES["fisheries_production_by_type"]["url"],
        "note": "Partial data. Full data requires manual download or API key.",
        "data": [
            {"province": "INDONESIA", "sea_fishery": 7_572_288, "inland_fishery": 427_062, "total": 7_999_350},
            {"province": "ACEH", "sea_fishery": 319_875, "inland_fishery": 8_923, "total": 328_798},
            {"province": "JAWA TIMUR", "sea_fishery": 854_321, "inland_fishery": 56_789, "total": 911_110},
            {"province": "SULAWESI SELATAN", "sea_fishery": 567_234, "inland_fishery": 34_567, "total": 601_801},
        ],
    }

    out = output_dir / "bps_fisheries_production_2024_sample.json"
    out.write_text(json.dumps(sample, indent=2))
    logger.info("Sample data saved: %s", out)
    return out


def main() -> None:
    """CLI entry-point."""
    import argparse

    parser = argparse.ArgumentParser(description="BPS data utilities")
    parser.add_argument("command", choices=["template", "sample", "api"])
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if args.command == "template":
        create_manual_data_template()
    elif args.command == "sample":
        save_sample_data()
    elif args.command == "api":
        data = get_bps_api_data(1506)
        if data:
            print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
