# Phase 1 Data Audit Findings

**Date:** 2026-04-21 | **Phase:** Load & Flatten

---

## Key Findings

### 1. MMSI Field Mapping
- `vessel.ssvid` is the MMSI field in GFW data, **not** `vessel.mmsi`
- All loaders updated to use `vessel.ssvid` → renamed to `mmsi` in output

### 2. Encounter Events (Dual Vessel)
- Encounter events contain **2 vessels**: primary in `vessel` key, secondary in `encounter.vessel` key
- Output includes both `mmsi` (primary) and `mmsi_2` (secondary) columns
- ~46K encounter events in the dataset

### 3. SAR vs GFW Effort Granularity
- **SAR Presence:** Area-level data (~40% rows have no MMSI) — detects presence in grid cells
- **GFW Fishing Effort:** Per-vessel data (100% MMSI coverage) — AIS-based effort estimation
- These are complementary: SAR catches dark fleet, GFW tracks known vessels

### 4. Zenodo Data Issues
- **2021 zip was corrupted** on first download; successfully redownloaded and processed
- Zenodo data is **grid-level** (no per-vessel MMSI, only `mmsi_present` boolean flag)
- ~30M rows total across 2020-2024; IDN subset: 893K rows
- Contains `fishing_hours` and `mmsi_present` as key signals

### 5. Coverage Comparison (Indonesia)
- Zenodo IDN: 893K rows (grid-level, broader spatial coverage)
- GFW 4Wings Effort: 586K rows (vessel-level, AIS-dependent)
- Zenodo provides better spatial coverage but less vessel-specific information

### 6. New IUU Signal Fields
- `publicAuthorizations` — whether vessel claims public authorization
- `potentialRisk` — GFW risk assessment flag
- `vesselPublicAuthorizationStatus` — authorization status indicator
- These fields are sparse but high-value for IUU labeling

### 7. Data Quality Notes
- Some events have null coordinates (AIS gaps by definition)
- Event durations range from minutes to weeks; outliers may need filtering
- Vessel gear types use GFW taxonomy (not standardized to ISSCFG yet)
- Flag codes use ISO 3166-1 alpha-2

---

## Output Files (data/processed/)

| File | Size | Rows | Cols | Description |
|------|------|------|------|-------------|
| `gfw_events_flat.parquet` | 64MB | 512K | 54 | All GFW events (fishing, encounters, loitering, port visits) |
| `sar_presence_flat.parquet` | 41MB | 1.2M | 13 | SAR-derived vessel presence detections |
| `fishing_effort_flat.parquet` | 17MB | 890K | 13 | AIS-based fishing effort estimates |
| `vessel_registry.parquet` | 6MB | 148K | 12 | Zenodo vessel registry (filtered IDN region) |
| `zenodo_effort_flat.parquet` | 237MB | 30M | 10 | Grid-level fishing effort (all flags, IDN region) |
| `weather.parquet` | — | 3K | — | BMKG marine weather observations |
| `viirs_detections.parquet` | — | 5K | — | VIIRS boat detection samples |
| `ports.parquet` | — | 30 | — | Indonesia port locations (OSM) |
