"""
resolver.py — Converts user input (pincode, DIGIPIN, district name) to (lat, lon).

Resolution order:
  1. 6-digit pincode  → India Post DB centroid
  2. DIGIPIN (10-char, valid charset) → decode to lat/lon
  3. District/city name → aliases.json fuzzy lookup → DB centroid
"""

import re, json, math, pathlib
import pandas as pd
from difflib import SequenceMatcher

BASE = pathlib.Path(__file__).parent.parent

# ── Load alias map ─────────────────────────────────────────────────────────────
with open(BASE / "aliases.json", encoding="utf-8") as f:
    _ALIASES = json.load(f)

# ── Load pincode DB (once, module-level) ──────────────────────────────────────
_pin_df: pd.DataFrame | None = None

def _get_pin_db() -> pd.DataFrame:
    global _pin_df
    if _pin_df is None:
        df = pd.read_csv(
            BASE / "pincode_data.csv",
            usecols=["pincode", "district", "statename", "latitude", "longitude"],
        )
        df["pincode"] = df["pincode"].astype(str).str.strip()
        df["lat"] = pd.to_numeric(df["latitude"], errors="coerce")
        df["lon"] = pd.to_numeric(df["longitude"], errors="coerce")
        _pin_df = df.dropna(subset=["lat", "lon"]).copy()
    return _pin_df

# ── DIGIPIN ───────────────────────────────────────────────────────────────────
_GRID = [["F","C","9","8"],["J","3","2","7"],["K","4","5","6"],["L","M","P","T"]]
_VALID = set("23456789CJKLMPFT")
_BOUNDS = (2.5, 38.5, 63.5, 99.5)  # minLat, maxLat, minLon, maxLon

def encode_digipin(lat: float, lon: float) -> str:
    ml, xl, mlo, xlo = _BOUNDS
    pin = ""
    for _ in range(10):
        ld = (xl - ml) / 4
        lod = (xlo - mlo) / 4
        row = max(0, min(3, 3 - int((lat - ml) / ld)))
        col = max(0, min(3, int((lon - mlo) / lod)))
        pin += _GRID[row][col]
        xl = ml + ld * (4 - row)
        ml = ml + ld * (3 - row)
        mlo = mlo + lod * col
        xlo = mlo + lod
    return pin

def decode_digipin(pin: str) -> tuple[float, float]:
    pin = pin.strip().upper().replace("-", "")
    if len(pin) != 10 or not all(c in _VALID for c in pin):
        raise ValueError(f"Invalid DIGIPIN: {pin}")
    ml, xl, mlo, xlo = _BOUNDS
    for char in pin:
        for r in range(4):
            for c in range(4):
                if _GRID[r][c] == char:
                    ld = (xl - ml) / 4
                    lod = (xlo - mlo) / 4
                    xl, ml = ml + ld * (4 - r), ml + ld * (3 - r)
                    mlo, xlo = mlo + lod * c, mlo + lod * (c + 1)
                    break
    return round((ml + xl) / 2, 6), round((mlo + xlo) / 2, 6)

# ── Alias lookup ──────────────────────────────────────────────────────────────
def _alias_to_canonical(query: str) -> tuple[str | None, str | None]:
    """Return (canonical_district, source_label) or (None, None)."""
    q = query.lower().strip()

    # Direct district alias
    for canonical, aliases in _ALIASES["districts"].items():
        if canonical == "_note":
            continue
        if q in aliases:
            return canonical, "alias_district"

    # City/town alias → parent district
    for name, info in _ALIASES["cities_and_towns"].items():
        if name == "_note":
            continue
        if q in info["aliases"]:
            return info["district"], f"alias_city:{name}"

    # Fuzzy fallback: best SequenceMatcher ratio against all aliases
    best_ratio = 0.0
    best_canonical = None
    for canonical, aliases in _ALIASES["districts"].items():
        if canonical == "_note":
            continue
        for alias in aliases:
            ratio = SequenceMatcher(None, q, alias).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_canonical = canonical

    if best_ratio >= 0.80:
        return best_canonical, f"alias_fuzzy:{best_ratio:.2f}"

    return None, None

def _pincode_to_latlon(pincode: str) -> tuple[float, float] | None:
    db = _get_pin_db()
    hits = db[db["pincode"] == pincode.strip()]
    if hits.empty:
        return None
    row = hits.iloc[0]
    return float(row["lat"]), float(row["lon"])

def _district_to_latlon(district: str) -> tuple[float, float] | None:
    """
    Try canonical name + all known aliases against the pincode DB.
    Handles spelling divergence between our dataset and India Post DB
    (e.g. "Kancheepuram" → DB "KANCHIPURAM", "Thiruchirapalli" → "TIRUCHIRAPPALLI").
    """
    pin_db = _get_pin_db()

    # Collect search terms: canonical + its full alias list
    search_terms = [district]
    for canonical, aliases in _ALIASES["districts"].items():
        if canonical == "_note":
            continue
        if canonical.lower() == district.lower() or district.lower() in aliases:
            search_terms.extend(aliases)
            break

    seen: set[str] = set()
    unique = [t for t in search_terms if len(t) >= 4 and not (t in seen or seen.add(t))]

    tn = pin_db[pin_db["statename"].str.upper().str.contains("TAMIL", na=False)]

    for term in unique:
        key = term.upper()[:10]
        hits = tn[tn["district"].str.upper().str.contains(key, na=False)]
        if not hits.empty:
            row = hits.iloc[0]
            return float(row["lat"]), float(row["lon"])

    # Widen: try all states
    for term in unique:
        key = term.upper()[:10]
        hits = pin_db[pin_db["district"].str.upper().str.contains(key, na=False)]
        if not hits.empty:
            row = hits.iloc[0]
            return float(row["lat"]), float(row["lon"])

    return None

# ── Public entry point ────────────────────────────────────────────────────────
def resolve(query: str) -> dict | None:
    """
    Returns {lat, lon, label, source, confidence} or None.
    confidence: 'high' | 'medium' | 'low'
    """
    q = query.strip()

    # 1. 6-digit pincode
    if re.fullmatch(r"\d{6}", q):
        result = _pincode_to_latlon(q)
        if result:
            return {"lat": result[0], "lon": result[1],
                    "label": f"Pincode {q}", "source": "pincode", "confidence": "high"}
        return None

    # 2. DIGIPIN (10 chars, valid charset, with optional hyphens)
    dp_clean = q.upper().replace("-", "")
    if len(dp_clean) == 10 and all(c in _VALID for c in dp_clean):
        try:
            lat, lon = decode_digipin(dp_clean)
            return {"lat": lat, "lon": lon,
                    "label": f"DIGIPIN {q}", "source": "digipin", "confidence": "high"}
        except ValueError:
            pass

    # 3. Name → alias → district centroid
    canonical, src_label = _alias_to_canonical(q)
    if canonical:
        result = _district_to_latlon(canonical)
        if result:
            confidence = "high" if "fuzzy" not in (src_label or "") else "medium"
            return {"lat": result[0], "lon": result[1],
                    "label": canonical, "source": src_label, "confidence": confidence}

    return None
