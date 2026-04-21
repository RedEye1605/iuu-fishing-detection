# Changelog

## [0.2.0] - 2026-04-21

### Phase 1: Load & Flatten — COMPLETE
- Generated 8 processed Parquet files from raw data sources
- **loaders.py:** GFW events (fishing, encounters, loitering, port visits) → unified `gfw_events_flat.parquet`
- **loaders_sar_effort.py:** SAR presence & fishing effort → `sar_presence_flat.parquet`, `fishing_effort_flat.parquet`
- **loaders_aux.py:** Auxiliary data (weather, VIIRS, ports, vessel registry, Zenodo effort) → 5 parquet files
- Fixed Zenodo 2021 corrupted zip (redownloaded successfully)
- Data audit completed — see `docs/PHASE1_AUDIT_FINDINGS.md`
- Updated `.gitignore` to exclude `*.parquet`, `data/raw/`, `*.bak`, `.pytest_cache/`
- Cleaned up stray files (`.bak`, `test.html`, `__pycache__/`, `.pytest_cache/`)

## [0.1.0] - 2026-04-20

### Initial Setup
- Project structure with `src/`, `scripts/`, `docs/`, `tests/`, `notebooks/`
- GFW API client for events, SAR, effort data
- Data download scripts for all sources
- ST-GAT model skeleton
- Graph builder skeleton
