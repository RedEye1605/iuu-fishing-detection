"""
Phase 2 Step 2.7: Clean Remaining Datasets (SAR, Effort, Zenodo)

- Date normalization
- Flag standardization
- Coordinate validation
- Add temporal features
"""

from __future__ import annotations
import gc, logging
from pathlib import Path
import pandas as pd
import numpy as np

from .constants import (
    PROCESSED_DIR, FLAG_MAP,
    SAR_PRESENCE_DEDUP, FISHING_EFFORT_DEDUP, ZENODO_EFFORT_DEDUP,
    SAR_PRESENCE_CLEAN, FISHING_EFFORT_CLEAN, ZENODO_EFFORT_CLEAN,
)

logger = logging.getLogger(__name__)
INPUT = PROCESSED_DIR
OUTPUT = PROCESSED_DIR


def clean_sar_effort():
    """Clean SAR and Fishing Effort."""
    for name, in_name, out_name in [
        ("SAR", SAR_PRESENCE_DEDUP, SAR_PRESENCE_CLEAN),
        ("Effort", FISHING_EFFORT_DEDUP, FISHING_EFFORT_CLEAN),
    ]:
        logger.info(f"\n--- Cleaning {name} ---")
        df = pd.read_parquet(INPUT / in_name)
        logger.info(f"  Loaded: {len(df):,}")

        df["flag"] = df["flag"].str.upper().map(lambda x: FLAG_MAP.get(x, x))
        df["is_domestic"] = df["flag"] == "IDN"

        df["date_parsed"] = pd.to_datetime(df["date"], format="mixed", errors="coerce")
        df["year"] = df["date_parsed"].dt.year
        df["month"] = df["date_parsed"].dt.month
        df["season"] = df["month"].map(lambda m: "wet" if m in [11,12,1,2,3] else "dry")

        df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
        df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
        bad = df["lat"].isna() | df["lon"].isna()
        if bad.any():
            logger.warning(f"  Dropping {bad.sum():,} rows with invalid coords")
            df = df[~bad]

        df.to_parquet(OUTPUT / out_name, index=False)
        sz = (OUTPUT / out_name).stat().st_size / 1024 / 1024
        logger.info(f"  ✅ {out_name} ({sz:.1f} MB, {len(df):,} rows)")
        del df; gc.collect()


def clean_zenodo():
    """Clean Zenodo effort - memory efficient chunked processing."""
    logger.info(f"\n--- Cleaning Zenodo Effort ---")
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(INPUT / ZENODO_EFFORT_DEDUP)

    out_path = OUTPUT / ZENODO_EFFORT_CLEAN
    writer = None
    total = 0

    for batch in pf.iter_batches(batch_size=1_500_000):
        df = batch.to_pandas()
        total += len(df)

        df["flag"] = df["flag"].str.upper().map(lambda x: FLAG_MAP.get(x, x))
        df["is_domestic"] = df["flag"] == "IDN"
        df["season"] = df["month"].map(lambda m: "wet" if m in [11,12,1,2,3] else "dry")
        df["cell_ll_lat"] = pd.to_numeric(df["cell_ll_lat"], errors="coerce")
        df["cell_ll_lon"] = pd.to_numeric(df["cell_ll_lon"], errors="coerce")

        import pyarrow as pa
        table = pa.Table.from_pandas(df)

        if writer is None:
            writer = pq.ParquetWriter(out_path, table.schema)
        writer.write_table(table)

        del df, table; gc.collect()

    if writer:
        writer.close()

    sz = out_path.stat().st_size / 1024 / 1024
    logger.info(f"  ✅ {ZENODO_EFFORT_CLEAN} ({sz:.1f} MB, {total:,} rows)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    logger.info("=" * 60 + "\nSTEP 2.7: CLEAN REMAINING DATASETS\n" + "=" * 60)
    clean_sar_effort()
    clean_zenodo()
    logger.info("\n✅ All Phase 2 cleaning complete!")
