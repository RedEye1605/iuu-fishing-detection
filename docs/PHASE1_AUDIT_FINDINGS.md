# Phase 1 Data Audit Findings

**Date:** 2026-04-21 (updated 2026-04-22) | **Phase:** Load & Flatten
**Status:** All issues resolved. See post-fix validation below.

---

## Key Findings

### 1. MMSI Field Mapping ✅ FIXED
- `vessel.ssvid` is the MMSI field in GFW data, **not** `vessel.mmsi`
- All loaders use `vessel.ssvid` → renamed to `mmsi` in output
- MMSI is `large_string` type across all files (explicitly cast in pipeline/extract.py)

### 2. Encounter Events (Dual Vessel) ✅ DOCUMENTED
- Encounter events contain **2 vessels**: primary in `vessel` key, secondary in `encounter.vessel` key
- Output includes both `mmsi` (primary) and `mmsi_2` (secondary) columns
- ~46K encounter events in the dataset

### 3. SAR vs GFW Effort Granularity ✅ HANDLED
- **SAR Presence:** Area-level data (~40% rows have no MMSI) — detects presence in grid cells
- **GFW Fishing Effort:** Per-vessel data (100% MMSI coverage) — AIS-based effort estimation
- SAR grid-only rows dropped in Phase 2 (cannot track without MMSI)

### 4. Zenodo Data ✅ FIXED
- Zenodo data is **spatially filtered** to Indonesia bbox during load (not flag-only)
- Original global data was ~30M rows; spatial filter → 707K rows (all within Indonesian waters)
- Zenodo data is grid-level (no per-vessel MMSI, only `mmsi_present` count)
- 2021 zip was corrupted on first download; successfully redownloaded

### 5. Coverage Comparison (Indonesia)
- Zenodo (spatially filtered): 707K rows (grid-level, broader spatial coverage)
- GFW 4Wings Effort: 886K rows (vessel-level, AIS-dependent)
- These are complementary: Zenodo provides broader spatial coverage, GFW tracks individual vessels

### 6. IUU Signal Fields
- `publicAuthorizations` — whether vessel claims public authorization
- `potentialRisk` — GFW risk assessment flag (0.4% True — very imbalanced)
- `vesselPublicAuthorizationStatus` — authorization status indicator
- These fields are sparse but high-value for IUU labeling

### 7. Data Quality Notes
- Event durations range from minutes to weeks; outliers capped in Phase 2
- Vessel gear types use GFW taxonomy
- Flag codes use ISO 3166 alpha-3 (standardized via FLAG_MAP in constants.py)

---

## Output Files (data/processed/)

| File | Rows | Cols | Description |
|------|------|------|-------------|
| `gfw_events_flat.parquet` | 512,272 | 54 | All GFW events (fishing, encounters, loitering, port visits) |
| `sar_presence_flat.parquet` | 1,242,915 | 13 | SAR-derived vessel presence (includes grid-only) |
| `fishing_effort_flat.parquet` | 890,411 | 13 | AIS-based fishing effort estimates |
| `vessel_registry.parquet` | 147,924 | 12 | Zenodo vessel registry (MMSI as string) |
| `zenodo_effort_flat.parquet` | 707,118 | 10 | Grid-level fishing effort (spatially filtered to IDN bbox) |
| `weather.parquet` | 2,920 | 9 | BMKG marine weather (8 zones) |
| `viirs_detections.parquet` | 5,000 | 8 | VIIRS boat detection samples |
| `ports.parquet` | 30 | 3 | Indonesia port locations (OSM) |

---

## Post-Fix Validation (2026-04-22)

All Phase 1 issues from the original audit have been resolved:

| Issue | Status | Fix |
|-------|--------|-----|
| MMSI int64 in vessel_registry | ✅ Fixed | Cast to string in pipeline/extract.py |
| Zenodo 30M rows (global, unfiltered) | ✅ Fixed | Spatial bbox filter applied during load |
| VIIRS date_gmt int64 | ✅ Fixed | Parsed with `pd.to_datetime(str, format="%Y%m%d")` |
| Weather only 4 zones mapped | ✅ Fixed | All 8 zones mapped in enrichment |
| __index_level_0__ leak in zenodo | ✅ Fixed | `index=False` safeguard in ParquetWriter |
