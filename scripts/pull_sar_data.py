#!/usr/bin/env python3
"""
Pull GFW SAR presence data for Indonesia EEZ using the 4Wings API.

Canonical SAR data acquisition script — uses the GFWClient from src.data.

Usage:
    python scripts/pull_sar_data.py
    python scripts/pull_sar_data.py --start 2020-01-01 --end 2025-12-31
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path for `src.*` imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.data.gfw_client import GFWClient
from src.utils.config import app_config

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = app_config.data_root / "raw" / "gfw"
DATASETS = {
    "sar": "public-global-sar-presence:latest",
    "effort": "public-global-fishing-effort:latest",
}


def pull_report(
    client: GFWClient,
    dataset: str,
    date_range: str,
    output_suffix: str,
) -> int:
    """Pull a 4Wings report, falling back to bbox if EEZ fails.

    Args:
        client: Authenticated GFWClient.
        dataset: GFW dataset identifier.
        date_range: Comma-separated date range (e.g. "2020-01-01,2025-04-30").
        output_suffix: Filename suffix for the output file.

    Returns:
        Number of entries saved, or 0 on failure.
    """
    logger.info("Pulling %s for %s...", dataset, date_range)

    data = client.get_4wings_report(dataset, date_range)
    if data is None:
        logger.warning("EEZ-based pull failed, trying bbox fallback...")
        data = client.get_4wings_bbox(dataset, date_range)

    if data is None:
        logger.error("Both pull methods failed for %s", dataset)
        return 0

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"4wings_{output_suffix}_{date_range.replace(',', '-')}.json.gz"

    with gzip.open(out_file, "wt", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    entries = data.get("entries", data) if isinstance(data, dict) else data
    count = len(entries) if isinstance(entries, list) else 0
    size_mb = os.path.getsize(out_file) / (1024 * 1024)
    logger.info("Saved %d entries to %s (%.2f MB)", count, out_file, size_mb)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull GFW 4Wings SAR data for Indonesia")
    parser.add_argument("--start", default="2020-01-01", help="Start date")
    parser.add_argument("--end", default="2025-04-30", help="End date")
    parser.add_argument("--dataset", choices=list(DATASETS.keys()) + ["all"], default="all")
    args = parser.parse_args()

    date_range = f"{args.start},{args.end}"
    client = GFWClient()

    datasets = list(DATASETS.items()) if args.dataset == "all" else [(args.dataset, DATASETS[args.dataset])]

    total = 0
    for name, ds_id in datasets:
        total += pull_report(client, ds_id, date_range, name)

    logger.info("Done — %d total entries retrieved", total)


if __name__ == "__main__":
    main()
