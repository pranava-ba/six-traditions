# Six Traditions — Temple Circuit Planner

A conversational temple itinerary planner for the six traditions of Hinduism (Shanmata).  
Currently live with **Shaivam** temples. Enter your location, set a travel radius, and get an optimised temple circuit — with route, distances, and a live map.

---

## What is DIGIPIN?

**DIGIPIN** (Digital Postal Index Number) is India Post's new geocode system, launched in 2024. It assigns a unique **10-character alphanumeric code** to every 4m × 4m square of land across India — precise enough to pinpoint a doorstep.

```
Example:  4TJ6-3MK9-PL
          └─┘└─┘└─┘└─┘
          Each group narrows the location progressively
```

**Why DIGIPIN instead of GPS coordinates?**
- Easier to share verbally or in a message than `12.8397, 79.7172`
- Works offline — no internet needed to encode/decode
- Already printed on India Post mail in new format
- Covers the entire Indian subcontinent including border areas

**Valid characters:** `2 3 4 5 6 7 8 9 C J K L M P T F`  
(vowels and easily-confused characters like `0 O 1 I` are excluded to prevent errors)

**How it works:**  
India's geography (lat 2.5°–38.5°N, lon 63.5°–99.5°E) is divided into a 4×4 grid. Each cell gets a character. The process repeats 10 times, each iteration quartering the previous cell. After 10 iterations, the cell is ~4m × 4m.

---

## What is Pincode?

India's traditional 6-digit postal index. The first digit identifies the region, digits 2–3 identify the sub-region/district, and digits 4–6 identify the post office. This app resolves pincodes to lat/lon using the **India Post pincode database** (165,000+ post offices).

---

## How the App Works

```
User input (pincode / DIGIPIN / district name)
        ↓
   Location Resolver
   ├─ 6-digit pincode → India Post DB → lat/lon
   ├─ DIGIPIN (10-char) → decode → lat/lon
   └─ District/city name → alias map → DB centroid → lat/lon
        ↓
   Radius Filter (Haversine formula)
   All temples within N km of the resolved point
        ↓
   Route Optimiser (Nearest Neighbour + 2-opt TSP)
   Shortest practical visiting order
        ↓
   Output: Itinerary + Map
```

### Fuzzy Location Matching

The alias system handles colloquial names, colonial spellings, and transliteration variants:

| What you type | Resolves to |
|---|---|
| `trichy` | Thiruchirapalli |
| `tanjore` | Thanjavur |
| `kanchi` | Kancheepuram |
| `madras` | Chennai |
| `pondy` | Puducherry |
| `nellai` | Thirunelveli |
| `kumbakonam` | Thanjavur district |
| `conjeevaram` | Kancheepuram |

---

## The Six Traditions (Shanmata)

The **Shanmata** system, codified by Adi Shankaracharya, recognises six principal Hindu traditions:

| Abbr | Tradition | Deity |
|---|---|---|
| SH | **Shaivam** | Shiva |
| VA | **Vaishnavam** | Vishnu |
| GA | **Ganapathyam** | Ganesha |
| SA | **Saktham** | Devi / Shakti |
| KA | **Kaumaram** | Murugan / Kartikeya |
| SO | **Sowram** | Surya (Sun) |

The RefNo tagging system uses `[State abbr][Gnana abbr][0001–9999]` for Indian temples (e.g. `TNSH0001` = Tamil Nadu, Shaivam, serial 1) and `[Country code][F][Gnana abbr][001–1000]` for foreign temples.

---

## Naadu — Historical Regions of Tamil Country

Temples are also tagged by **Naadu** (historical region), reflecting the ancient geographic divisions of Tamil Nadu:

| Naadu | Area |
|---|---|
| Thondai Naadu | Northern Tamil Nadu (Kancheepuram, Vellore, Chennai belt) |
| Nadu Naadu | Central Tamil Nadu |
| Cauvery Vadakarai | North bank of the Cauvery (Thanjavur, Nagapattinam) |
| Cauvery Thenkarai | South bank of the Cauvery |
| Pandya Naadu | Deep south (Madurai, Ramanathapuram) |
| Kongu Naadu | Western Tamil Nadu (Coimbatore, Erode, Salem) |
| Malai Naadu | Hill country (Nilgiris) |
| Vada Naadu | Far north / Andhra border |
| Thuluva Naadu | Karnataka coast |
| Ezha Naadu | Sri Lanka (excluded from routing) |

---

## Running Locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Open `http://localhost:8501`

---

## Deploying to Streamlit Cloud (Free)

1. Push this folder to a GitHub repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click **New app** → select your repo → set main file to `streamlit_app.py`
4. Deploy — you get a public URL instantly

---

## File Structure

```
six-traditions-app/
├── streamlit_app.py        ← Main app (chat UI + map)
├── requirements.txt        ← Python dependencies
├── temples.db              ← SQLite: 271 Shaivam temples + flagged table
├── aliases.json            ← Fuzzy alias map (districts, cities, naadu, gnana)
├── pincode_data.csv        ← India Post pincode database (165k records, lat/lon)
└── chatbot/
    ├── db.py               ← SQLite read/write + session management
    ├── resolver.py         ← Pincode / DIGIPIN / name → lat/lon
    ├── router.py           ← Haversine filter + TSP route optimisation
    ├── formatter.py        ← Message formatting
    ├── conversation.py     ← 5-state conversation engine
    └── main.py             ← FastAPI webhook (for future WhatsApp integration)
```

---

## Data Sources

- **Temple data** — compiled from primary research across Tamil Nadu and beyond
- **Coordinates** — India Post pincode database; DIGIPIN-resolved centroids
- **Pincode DB** — India Post open data (165,627 post offices)
- **DIGIPIN** — India Post DIGIPIN specification (2024)

---

## Status

| Tradition | Temples | Status |
|---|---|---|
| Shaivam | 271 | Live |
| Vaishnavam | — | Pending |
| Ganapathyam | — | Pending |
| Saktham | — | Pending |
| Kaumaram | — | Pending |
| Sowram | — | Pending |

WhatsApp API integration is the final step, after MVP validation on Streamlit.
