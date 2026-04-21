"""
Global Fishing Watch API client for IUU Fishing Detection.

Provides typed access to GFW v3 API endpoints:
- Fishing events, encounters, loitering, port visits
- Vessel track data
- 4Wings SAR presence and fishing effort reports

Requires GFW_API_TOKEN environment variable or ~/.openclaw/.gfw_token file.
Register at: https://globalfishingwatch.org/our-apis/
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

import requests

RequestException = requests.RequestException

logger = logging.getLogger(__name__)

API_BASE = "https://api.globalfishingwatch.org/v3"
GATEWAY_BASE = "https://gateway.api.globalfishingwatch.org/v3"

# Indonesia EEZ configuration
TOKEN_FILE = Path.home() / ".openclaw" / ".gfw_token"
EEZ_BOUNDS = {"min_lat": -11.5, "max_lat": 6.5, "min_lon": 95.0, "max_lon": 141.5}
EEZ_REGION_ID = "8492"
DEFAULT_OUTPUT = Path("data/raw/gfw")


def _load_token() -> str:
    """Load GFW API token from env or file."""
    token = os.environ.get("GFW_API_TOKEN", "")
    if token:
        return token
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()
    logger.error("GFW_API_TOKEN not set and no token file found at %s", TOKEN_FILE)
    sys.exit(1)


def _headers(token: str) -> dict[str, str]:
    """Build authorization headers."""
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


class GFWClient:
    """High-level client for the Global Fishing Watch API."""

    def __init__(self, token: Optional[str] = None) -> None:
        self.token = token or _load_token()
        self.headers = _headers(self.token)

    def test_connection(self) -> bool:
        """Verify API connectivity and token validity."""
        try:
            r = requests.get(
                f"{API_BASE}/vessels/search",
                headers=self.headers,
                params={"query": "fishing", "limit": 1},
                timeout=30,
            )
            if r.status_code == 200:
                logger.info("GFW API connected successfully")
                return True
            if r.status_code == 401:
                logger.error("Unauthorized — check your API token")
            else:
                logger.error("API error %s: %s", r.status_code, r.text[:200])
        except requests.RequestException as exc:
            logger.error("Connection failed: %s", exc)
        return False

    def get_indonesia_fishing_events(
        self,
        start_date: str,
        end_date: str,
        limit: int = 100,
    ) -> Optional[dict[str, Any]]:
        """Fetch fishing events within the Indonesian EEZ bounding box."""
        params: dict[str, Any] = {
            "datasets[]": "public-fishing-event",
            "startDate": start_date,
            "endDate": end_date,
            "geometry": json.dumps({
                "type": "Polygon",
                "coordinates": [[
                    [EEZ_BOUNDS["min_lon"], EEZ_BOUNDS["min_lat"]],
                    [EEZ_BOUNDS["max_lon"], EEZ_BOUNDS["min_lat"]],
                    [EEZ_BOUNDS["max_lon"], EEZ_BOUNDS["max_lat"]],
                    [EEZ_BOUNDS["min_lon"], EEZ_BOUNDS["max_lat"]],
                    [EEZ_BOUNDS["min_lon"], EEZ_BOUNDS["min_lat"]],
                ]],
            }),
            "limit": limit,
        }
        return self._get(f"{API_BASE}/events", params)

    def get_encounter_events(
        self,
        start_date: str,
        end_date: str,
        limit: int = 100,
    ) -> Optional[dict[str, Any]]:
        """Fetch encounter events (potential transshipment)."""
        params = {
            "datasets[]": "public-encounter-event",
            "startDate": start_date,
            "endDate": end_date,
            "limit": limit,
        }
        return self._get(f"{API_BASE}/events", params)

    def get_vessel_track(
        self,
        vessel_id: str,
        start_date: str,
        end_date: str,
    ) -> Optional[dict[str, Any]]:
        """Fetch vessel track data."""
        params = {
            "datasets[]": "public-global-ais",
            "startDate": start_date,
            "endDate": end_date,
            "binary": "false",
        }
        return self._get(f"{API_BASE}/vessels/{vessel_id}/track", params)

    def get_4wings_report(
        self,
        dataset: str,
        date_range: str,
        spatial_resolution: str = "LOW",
        temporal_resolution: str = "MONTHLY",
    ) -> Optional[dict[str, Any]]:
        """Fetch a 4Wings report using EEZ region-based spatial filter."""
        body: dict[str, Any] = {
            "region": {
                "dataset": "public-eez-areas",
                "id": EEZ_REGION_ID,
            }
        }
        params = {
            "datasets[0]": dataset,
            "date-range": date_range,
            "format": "JSON",
            "spatial-resolution": spatial_resolution,
            "temporal-resolution": temporal_resolution,
        }
        return self._post(f"{GATEWAY_BASE}/4wings/report", params, body)

    def get_4wings_bbox(
        self,
        dataset: str,
        date_range: str,
        spatial_resolution: str = "LOW",
        temporal_resolution: str = "MONTHLY",
    ) -> Optional[dict[str, Any]]:
        """Fetch a 4Wings report using bounding-box spatial filter (fallback)."""
        body: dict[str, Any] = {
            "spatial-aggregation": {
                "type": "bbox",
                "geojson": {
                    "type": "Polygon",
                    "coordinates": [[
                        [EEZ_BOUNDS["min_lon"], EEZ_BOUNDS["min_lat"]],
                        [EEZ_BOUNDS["max_lon"], EEZ_BOUNDS["min_lat"]],
                        [EEZ_BOUNDS["max_lon"], EEZ_BOUNDS["max_lat"]],
                        [EEZ_BOUNDS["min_lon"], EEZ_BOUNDS["max_lat"]],
                        [EEZ_BOUNDS["min_lon"], EEZ_BOUNDS["min_lat"]],
                    ]],
                },
            }
        }
        params = {
            "datasets[0]": dataset,
            "date-range": date_range,
            "format": "JSON",
            "spatial-resolution": spatial_resolution,
            "temporal-resolution": temporal_resolution,
        }
        return self._post(f"{GATEWAY_BASE}/4wings/report", params, body)

    def bulk_download_indonesia_data(self, year: int = 2023) -> list[dict[str, Any]]:
        """Download fishing data for Indonesian waters, processed quarterly."""
        quarters = [
            (f"{year}-01-01", f"{year}-03-31", "Q1"),
            (f"{year}-04-01", f"{year}-06-30", "Q2"),
            (f"{year}-07-01", f"{year}-09-30", "Q3"),
            (f"{year}-10-01", f"{year}-12-31", "Q4"),
        ]
        all_events: list[dict[str, Any]] = []
        for start, end, q in quarters:
            logger.info("Fetching %s %s: %s → %s", year, q, start, end)
            events = self.get_indonesia_fishing_events(start, end)
            if events:
                entries = events.get("entries", [])
                logger.info("  Found %d events", len(entries))
                all_events.extend(entries)
            else:
                logger.warning("  Failed to fetch %s %s", year, q)

        DEFAULT_OUTPUT.mkdir(parents=True, exist_ok=True)
        output_file = DEFAULT_OUTPUT / f"gfw_indonesia_fishing_{year}.json"
        output_file.write_text(json.dumps(all_events, indent=2))
        logger.info("Saved %d events to %s", len(all_events), output_file)
        return all_events

    def _get(self, url: str, params: dict) -> Optional[dict[str, Any]]:
        """GET request with error handling."""
        try:
            r = requests.get(url, headers=self.headers, params=params, timeout=120)
            if r.status_code == 200:
                return r.json()
            logger.error("GET %s → %s: %s", url, r.status_code, r.text[:200])
        except (requests.RequestException, Exception) as exc:
            logger.error("GET %s failed: %s", url, exc)
        return None

    def _post(
        self, url: str, params: dict, body: dict
    ) -> Optional[dict[str, Any]]:
        """POST request with error handling."""
        try:
            r = requests.post(
                url, headers=self.headers, params=params, json=body, timeout=300
            )
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            logger.error("POST %s failed: %s", url, exc)
            if hasattr(exc, "response") and exc.response is not None:
                logger.error(
                    "Response %s: %s", exc.response.status_code, exc.response.text[:500]
                )
        return None


def main() -> None:
    """Simple CLI for testing and bulk downloads."""
    import argparse

    parser = argparse.ArgumentParser(description="GFW API client")
    parser.add_argument("command", choices=["test", "download"])
    parser.add_argument("--year", type=int, default=2023)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    client = GFWClient()

    if args.command == "test":
        ok = client.test_connection()
        print("✅ Connected" if ok else "❌ Failed")
    elif args.command == "download":
        client.bulk_download_indonesia_data(args.year)


if __name__ == "__main__":
    main()
