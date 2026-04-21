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

logger = logging.getLogger(__name__)
INPUT = Path("data/processed")
OUTPUT = Path("data/processed")

FLAG_MAP = {
    "IDN":"IDN","INA":"IDN","CHN":"CHN","CHINA":"CHN","TWN":"TWN","ROC":"TWN",
    "VNM":"VNM","MYS":"MYS","PHL":"PHL","PNG":"PNG","THA":"THA","KOR":"KOR",
    "SGP":"SGP","LBR":"LBR","PAN":"PAN","AUS":"AUS","JPN":"JPN","IND":"IND",
    "SWE":"SWE","BES":"BES","HKG":"HKG",
}


def clean_sar_effort():
    """Clean SAR and Fishing Effort."""
    for name, filename in [("SAR", "sar_presence_dedup"), ("Effort", "fishing_effort_dedup")]:
        print(f"\n--- Cleaning {name} ---")
        df = pd.read_parquet(INPUT / f"{filename}.parquet")
        print(f"  Loaded: {len(df):,}")
        
        # Flag standardize
        df["flag"] = df["flag"].str.upper().map(lambda x: FLAG_MAP.get(x, x))
        df["is_domestic"] = df["flag"] == "IDN"
        
        # Date → parse monthly strings
        df["date_parsed"] = pd.to_datetime(df["date"], format="mixed", errors="coerce")
        df["year"] = df["date_parsed"].dt.year
        df["month"] = df["date_parsed"].dt.month
        df["season"] = df["month"].map(lambda m: "wet" if m in [11,12,1,2,3] else "dry")
        
        # Coordinate validation
        df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
        df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
        bad = df["lat"].isna() | df["lon"].isna()
        if bad.any():
            print(f"  ⚠️ Dropping {bad.sum():,} rows with invalid coords")
            df = df[~bad]
        
        out_name = filename.replace("_dedup", "_clean")
        df.to_parquet(OUTPUT / f"{out_name}.parquet", index=False)
        sz = (OUTPUT / f"{out_name}.parquet").stat().st_size / 1024 / 1024
        print(f"  ✅ {out_name}.parquet ({sz:.1f} MB, {len(df):,} rows)")
        del df; gc.collect()


def clean_zenodo():
    """Clean Zenodo effort - memory efficient chunked processing."""
    print(f"\n--- Cleaning Zenodo Effort ---")
    import pyarrow.parquet as pq
    
    pf = pq.ParquetFile(INPUT / "zenodo_effort_dedup.parquet")
    
    # Process in chunks and write via ParquetWriter
    out_path = OUTPUT / "zenodo_effort_clean.parquet"
    writer = None
    total = 0
    
    for batch in pf.iter_batches(batch_size=1_500_000):
        df = batch.to_pandas()
        total += len(df)
        
        # Flag standardize
        df["flag"] = df["flag"].str.upper().map(lambda x: FLAG_MAP.get(x, x))
        df["is_domestic"] = df["flag"] == "IDN"
        
        # Date normalization (already has year/month columns)
        df["season"] = df["month"].map(lambda m: "wet" if m in [11,12,1,2,3] else "dry")
        
        # Coordinate validation
        df["cell_ll_lat"] = pd.to_numeric(df["cell_ll_lat"], errors="coerce")
        df["cell_ll_lon"] = pd.to_numeric(df["cell_ll_lon"], errors="coerce")
        
        # Convert to arrow table for writing
        import pyarrow as pa
        table = pa.Table.from_pandas(df)
        
        if writer is None:
            writer = pq.ParquetWriter(out_path, table.schema)
        writer.write_table(table)
        
        del df, table; gc.collect()
    
    if writer:
        writer.close()
    
    sz = out_path.stat().st_size / 1024 / 1024
    print(f"  ✅ zenodo_effort_clean.parquet ({sz:.1f} MB, {total:,} rows)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    print("=" * 60)
    print("STEP 2.7: CLEAN REMAINING DATASETS")
    print("=" * 60)
    clean_sar_effort()
    clean_zenodo()
    print("\n✅ All Phase 2 cleaning complete!")
