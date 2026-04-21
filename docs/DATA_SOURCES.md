# Data Sources Guide — Gemastik IUU Fishing Detection (ST-GAT)

> **Last Updated:** 2026-04-21 | **Coverage:** Indonesia EEZ & Southeast Asian Waters
> **GFW API Token:** `~/gemastik/.gfw_token` | **Python:** `/tmp/datathon-env/bin/python`

---

## Quick Summary

| # | Source | Status | Priority | Data Type |
|---|--------|--------|----------|-----------|
| 1 | GFW Encounters Events | ✅ Working | P0 | Vessel encounter events |
| 2 | GFW Loitering Events | ✅ Working | P0 | Carrier vessel loitering |
| 3 | GFW Fishing Events | ✅ Working | P0 | Fishing activity events |
| 4 | GFW Port Visits | ✅ Working | P1 | Port entry/exit events |
| 5 | GFW 4Wings Fishing Effort | ✅ Working | P0 | Fishing hours by gear/spatial |
| 6 | GFW SAR Presence | ✅ Working | P1 | Satellite vessel detections |
| 7 | GFW Static Fishing Effort (Zenodo) | ✅ Download | P1 | 2012-2024 fishing hours CSV |
| 8 | GFW BigQuery Public Tables | ✅ Free | P2 | SQL-queryable fishing data |
| 9 | EEZ Shapefiles | ✅ Working | P0 | Maritime boundaries |
| 10 | Indonesia Ports | ✅ Working | P1 | 30 port locations |
| 11 | BMKG Maritime Weather | ⚠️ PDF only | P2 | Wave height, wind, weather |
| 12 | BPS Fisheries Statistics | ⚠️ Manual | P2 | Catch volume by province |
| 13 | KKP Portal Data | ⚠️ Web only | P2 | Production statistics |
| 14 | VIIRS Boat Detection | ❌ Auth required | P2 | Nighttime vessel detection |
| 15 | MarineCadastre AIS | ❌ US only | — | US waters only |
| 16 | GFW AIS Off/Gap Events | ❌ 404 | — | Not in v3 API |

---

## 1. GFW API — Events (Encounters, Loitering, Fishing, Port Visits)

**Base URL:** `https://gateway.api.globalfishingwatch.org/v3`

**Auth:** `Authorization: Bearer <token>` (token from `~/gemastik/.gfw_token`)

### Working Endpoints

#### Encounters Events
```bash
TOKEN=$(cat ~/gemastik/.gfw_token)
curl -s "https://gateway.api.globalfishingwatch.org/v3/events?\
datasets%5B0%5D=public-global-encounters-events%3Alatest&\
limit=100&offset=0&\
start-date=2024-01-01&end-date=2024-12-31" \
  -H "Authorization: Bearer $TOKEN"
```
- **Dataset:** `public-global-encounters-events:latest`
- **Total available:** ~105,000+ events globally
- **Data:** Vessel encounters (two vessels meeting at sea), position, duration, vessel info, distances from shore/port

#### Loitering Events
```bash
curl -s "https://gateway.api.globalfishingwatch.org/v3/events?\
datasets%5B0%5D=public-global-loitering-events%3Alatest&\
limit=100&offset=0&\
start-date=2024-01-01&end-date=2024-12-31" \
  -H "Authorization: Bearer $TOKEN"
```
- **Dataset:** `public-global-loitering-events:latest`
- **Total available:** 14,500+ events globally
- **Data:** Carrier vessels loitering (potential transshipment), position, duration, speed

#### Fishing Events
```bash
curl -s "https://gateway.api.globalfishingwatch.org/v3/events?\
datasets%5B0%5D=public-global-fishing-events%3Alatest&\
limit=100&offset=0&\
start-date=2024-01-01&end-date=2024-12-31" \
  -H "Authorization: Bearer $TOKEN"
```
- **Dataset:** `public-global-fishing-events:latest`
- **Total available:** 1,098,935 events globally
- **Data:** Individual fishing events with start/end time, position, vessel info, gear type

#### Port Visits
```bash
curl -s "https://gateway.api.globalfishingwatch.org/v3/events?\
datasets%5B0%5D=public-global-port-visits-events%3Alatest&\
limit=100&offset=0&\
start-date=2024-01-01&end-date=2024-12-31" \
  -H "Authorization: Bearer $TOKEN"
```
- **Dataset:** `public-global-port-visits-events:latest`
- **Total available:** 2,349,756 events globally
- **⚠️ Must include `offset=0`** — requests without offset return 422
- **Data:** Port entry/exit, anchorage details, visit duration, confidence, distances

### Key Parameters
- `limit`: Max results per request (up to 1000)
- `offset`: Pagination offset (required for port visits!)
- `start-date` / `end-date`: ISO date format (YYYY-MM-DD)
- `vessels`: Filter by vessel ID
- `geometry`: GeoJSON polygon filter (POST body)

### Response Structure (Events)
```json
{
  "total": 105480,
  "entries": [
    {
      "id": "...",
      "type": "encounter|loitering|fishing|port_visit",
      "start": "2024-01-01T00:00:00.000Z",
      "end": "2024-01-01T12:00:00.000Z",
      "position": {"lat": 14.7, "lon": -17.4},
      "boundingBox": {...},
      "distances": {"fromShore": 12345, "fromPort": 23456},
      "vessel": {"name": "...", "mmsi": "...", "flag": "...", "geartype": "..."},
      "regions": ["8371"]
    }
  ]
}
```

---

## 2. GFW API — 4Wings Report (Fishing Effort, SAR Presence)

**Endpoint:** `POST /v3/4wings/report`

### Fishing Effort by EEZ
```bash
curl -s -X POST "https://gateway.api.globalfishingwatch.org/v3/4wings/report?\
spatial-resolution=LOW&temporal-resolution=MONTHLY&\
datasets%5B0%5D=public-global-fishing-effort%3Alatest&\
date-range=2024-01-01,2024-12-31&format=JSON" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"region": {"dataset": "public-eez-areas", "id": 8371}}'
```
- **Dataset:** `public-global-fishing-effort:latest`
- **Indonesia EEZ IDs:** 8371 (main), 8370, 8372
- **Spatial resolutions:** LOW (0.1°), MEDIUM, HIGH
- **Temporal resolutions:** HOURLY, DAILY, MONTHLY, YEARLY
- **Returns:** Fishing hours per vessel per spatial bin per time period

### SAR Vessel Presence
```bash
curl -s -X POST "https://gateway.api.globalfishingwatch.org/v3/4wings/report?\
spatial-resolution=LOW&temporal-resolution=MONTHLY&\
datasets%5B0%5D=public-global-sar-presence%3Alatest&\
date-range=2024-01-01,2024-12-31&format=JSON" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"region": {"dataset": "public-eez-areas", "id": 8371}}'
```
- **Dataset:** `public-global-sar-presence:latest`
- **Returns:** Vessel detection counts from satellite SAR imagery

### Response Structure (4Wings)
```json
{
  "entries": [
    {
      "lat": 14.7,
      "lon": -17.4,
      "date": "2024-01",
      "hours": 12.5,
      "mmsi": "663102000",
      "shipName": "ANTA SARR",
      "flag": "SEN",
      "geartype": "TRAWLERS",
      "vesselType": "FISHING"
    }
  ]
}
```

---

## 3. GFW Vessel Identity & Search

```bash
# Search vessels
curl -s "https://gateway.api.globalfishingwatch.org/v3/vessels/search?\
datasets%5B0%5D=public-global-vessel-identity%3Alatest&\
query=<search_term>&limit=10&offset=0" \
  -H "Authorization: Bearer $TOKEN"

# Get vessel by ID
curl -s "https://gateway.api.globalfishingwatch.org/v3/vessels/<vessel_id>?\
datasets%5B0%5D=public-global-vessel-identity%3Alatest" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 4. GFW Static Fishing Effort (Download)

### Zenodo v3 Dataset (2012-2024)
- **URL:** https://zenodo.org/records/14982712
- **DOI:** 10.5281/zenodo.14982712
- **Format:** CSV files per year (zipped)
- **Coverage:** Global, 370M+ hours of fishing activity, 141K+ unique MMSI
- **License:** CC-BY
- **Contents:**
  - Fishing hours by MMSI (daily, 0.01° resolution)
  - Fishing hours by fleet
  - Vessel information file
- **BigQuery:** `global-fishing-watch.fishing_effort_v3`

### GFW Data Download Portal
- **URL:** https://globalfishingwatch.org/data-download/datasets/public-fishing-effort
- **Requires:** Free GFW account login
- **Formats:** CSV, GeoTIFF

---

## 5. GFW BigQuery Public Tables (FREE)

Accessible via Google BigQuery free tier:
```sql
-- Fishing effort v3
SELECT * FROM `global-fishing-watch.fishing_effort_v3.fishing_effort`
WHERE date >= '2024-01-01'
LIMIT 100;
```
- **Free tier:** 1 TB query/month
- **Datasets:** fishing_effort_v3, vessel_identity, events
- **Setup:** https://globalfishingwatch.org/our-apis/

---

## 6. EEZ Shapefiles

- **Source:** MarineRegions (Flanders Marine Institute)
- **URL:** https://www.marineregions.org/eez.php
- **Download:** GeoJSON / Shapefile
- **Indonesia EEZ IDs in GFW:**
  - 8371 = Indonesia (main EEZ)
  - 8370 = Indonesia (section)
  - 8372 = Indonesia (section)
- **Status:** ✅ Already downloaded

---

## 7. Indonesia Ports Data

- **Source:** GFW / World Port Index
- **Count:** 30 Indonesian ports with coordinates
- **Status:** ✅ Already collected
- **Usage:** Port visit event filtering, proximity analysis

---

## 8. BMKG Maritime Weather ⚠️

- **Maritime Portal:** https://maritim.bmkg.go.id/
- **Weather PDFs:** `https://maritim.bmkg.go.id/marine2026-data/doc/cuaca/perairan/<CODE>.pdf`
  - Codes: M.01 through M.20 (perairan/perairan areas)
  - E.g., M.20 = Laut Jawa bagian tengah
  - M.08 = Samudra Hindia
  - P.W.04 = Perairan western areas
- **API:** No public API for marine weather; data only as PDF
- **Data includes:** Wave height, wind speed/direction, air temperature, humidity, visibility
- **Access:** ✅ PDFs downloadable (200 status, ~900KB each)
- **Extraction:** Use `pdfplumber` or `tabula-py` to extract tables from PDFs
- **Alternative:** BMKG general API at `api.bmkg.go.id` (limited, land weather only)

### PDF Extraction Example
```python
import pdfplumber
with pdfplumber.open("bmkg_maritime.pdf") as pdf:
    for page in pdf.pages:
        tables = page.extract_tables()
        for table in tables:
            for row in table:
                print(row)
```

---

## 9. BPS Fisheries Statistics ⚠️

- **Publications:**
  - Statistik Sumber Daya Laut dan Pesisir 2024: https://www.bps.go.id/id/publication/2024/11/29/d622648a533da3bc907e8b3a
  - Statistik Pelabuhan Perikanan 2024: https://www.bps.go.id/id/publication/2025/11/07/d6ea7b9329941356bd48b297
- **Statistics Table (catch by province):** https://www.bps.go.id/id/statistics-table/3/.../volume-produksi-dan-nilai-produksi-perikanan-tangkap-menurut-provinsi-dan-jenis-penangkapan--2024.html
- **⚠️ Cloudflare Protection:** Automated downloads blocked (403)
- **Workaround:** Manual download via browser, or use BPS API (if available)
- **Data includes:** Catch volume by province, fishing gear type, fish species

---

## 10. KKP Portal Data ⚠️

- **Portal:** https://portaldata.kkp.go.id/portals/data-statistik/prod-ikan/summary
- **Data:** Produksi Perikanan Tangkap by species (2024)
  - Top species: TONGKOL (681K ton), LAYANG (550K ton), CAKALANG (412K ton)
- **⚠️ SPA site:** No public API; data rendered client-side
- **Workaround:** Manual data entry or browser scraping with Selenium

---

## 11. VIIRS Boat Detection ❌

- **Provider:** Earth Observation Group (EOG), Colorado School of Mines
- **URL:** https://eogdata.mines.edu/products/vbd/
- **Data Format:** CSV (nightly), GeoTIFF (monthly summaries)
- **Coverage:** Global, per-country EEZ data available
- **Indonesia:** `/v23/IDN/` folder exists
- **❌ Requires Authentication:** 302 redirect to OpenID Connect login
- **Free tier:** 'Final' nightly data + monthly/annual summaries under CC-BY-4.0
- **To access:** Register at https://eogdata.mines.edu/ (free account)
- **Alternative:** Sentinel-2 vessel detections via GFW API (`public-global-sar-presence:latest`)

---

## 12. MarineCadastre AIS ❌ (US Waters Only)

- **URL:** https://marinecadastre.gov/accessais/
- **Data:** US EEZ AIS vessel tracks
- **Coverage:** ❌ US waters only — not useful for Indonesia
- **Skip this source for Gemastik**

---

## 13. GFW AIS Off/Gap Events ❌

- **Status:** Not available via GFW v3 Events API
- **Dataset names tried (all 404):**
  - `public-global-ais-off-events:latest`
  - `public-global-ais-off-events-v2:latest`
  - `public-global-ais-gaps:latest`
  - `public-global-gap-events:latest`
  - `public-ais-off-events:latest`
- **Insights API:** `/v3/insights` returns 404
- **GFW docs confirm** AIS off events exist as a product but the dataset name for v3 API is not publicly documented
- **Alternative:** Derive gap events manually from vessel track data (look for temporal gaps in AIS positions)
- **Workaround:** Use GFW map interface at https://globalfishingwatch.org/map to visually identify gap events

---

## Priority Data Pull Plan for ST-GAT Model

### Phase 1: Core Dataset (Immediate)
1. **GFW Fishing Events** — Pull all fishing events for Indonesia bounding box (95°E-141°E, 12°S-6°N)
   - ~1M global events; filter for Indonesia region
   - Use pagination (offset/limit) to pull all pages
2. **GFW 4Wings Fishing Effort** — Monthly fishing effort for Indonesia EEZ (ID 8371, 8370, 8372)
   - LOW spatial resolution (0.1° bins), MONTHLY temporal
3. **GFW Encounters** — Encounter events in Indonesia waters
4. **GFW Loitering** — Loitering events in Indonesia waters

### Phase 2: Enrichment (Next)
5. **GFW Port Visits** — Port visits at Indonesian ports
6. **GFW SAR Presence** — Satellite detections in Indonesia EEZ
7. **GFW Static Effort** — Download 2022-2024 CSVs from Zenodo

### Phase 3: Supplementary (If Time Allows)
8. **BMKG Weather** — Extract maritime weather from PDFs
9. **BPS Statistics** — Manual download catch statistics
10. **VIIRS VBD** — Register EOG account, download Indonesia nightly data

---

## API Quota & Rate Limits

- GFW API: Free tier, rate limited (be gentle with requests)
- BigQuery: 1 TB free query/month
- Use pagination (`offset`/`limit`) for large pulls
- Batch date ranges to minimize API calls

---

## Python Helper: Batch Pull Events

```python
import requests, json, time

TOKEN = open('/home/rclaw/gemastik/.gfw_token').read().strip()
BASE = 'https://gateway.api.globalfishingwatch.org/v3'
HEADERS = {'Authorization': f'Bearer {TOKEN}'}

def pull_events(dataset, start_date, end_date, batch_size=1000):
    """Pull all events with pagination."""
    all_events = []
    offset = 0
    while True:
        url = f'{BASE}/events?datasets%5B0%5D={dataset}&limit={batch_size}&offset={offset}&start-date={start_date}&end-date={end_date}'
        r = requests.get(url, headers=HEADERS)
        data = r.json()
        entries = data.get('entries', [])
        if not entries:
            break
        all_events.extend(entries)
        total = data.get('total', 0)
        offset += batch_size
        if offset >= total:
            break
        time.sleep(0.5)  # Rate limit
    return all_events

# Example: Pull encounters
# events = pull_events('public-global-encounters-events:latest', '2024-01-01', '2024-12-31')
```

---

## File Locations

```
~/gemastik/
├── .gfw_token              # API token
├── docs/
│   └── DATA_SOURCES.md     # This file
├── data/
│   ├── encounters/         # Pulled encounter events
│   ├── loitering/          # Pulled loitering events
│   ├── fishing-events/     # Pulled fishing events
│   ├── port-visits/        # Pulled port visit events
│   ├── fishing-effort/     # 4Wings effort data
│   ├── sar-presence/       # SAR detections
│   ├── eez/                # EEZ shapefiles
│   └── ports/              # Indonesia port data
└── scripts/
    └── pull_gfw_data.py    # Data pulling script
```
