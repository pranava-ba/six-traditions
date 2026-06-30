"""
router.py — Haversine radius filter + TSP route optimisation.
"""

import math
from chatbot.db import all_temples

_EARTH_R = 6371.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return _EARTH_R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def temples_in_radius(
    lat: float,
    lon: float,
    radius_km: float,
    max_results: int = 20,
    naadu_filter: str | None = None,
) -> list[dict]:
    temples = all_temples()
    results = []
    for t in temples:
        d = haversine(lat, lon, t["lat"], t["lon"])
        if d <= radius_km:
            if naadu_filter and t.get("naadu") != naadu_filter:
                continue
            results.append({**t, "dist_km": round(d, 2)})
    results.sort(key=lambda x: x["dist_km"])
    return results[:max_results]


def _total_distance(route: list[dict], o_lat: float, o_lon: float) -> float:
    d = 0.0
    prev_lat, prev_lon = o_lat, o_lon
    for t in route:
        d += haversine(prev_lat, prev_lon, t["lat"], t["lon"])
        prev_lat, prev_lon = t["lat"], t["lon"]
    return d


def _nearest_neighbour(temples: list[dict], o_lat: float, o_lon: float) -> list[dict]:
    remaining = list(temples)
    route = []
    cur_lat, cur_lon = o_lat, o_lon
    while remaining:
        best_idx = min(range(len(remaining)), key=lambda i: haversine(cur_lat, cur_lon, remaining[i]["lat"], remaining[i]["lon"]))
        best = remaining.pop(best_idx)
        route.append(best)
        cur_lat, cur_lon = best["lat"], best["lon"]
    return route


def _two_opt(route: list[dict], o_lat: float, o_lon: float) -> list[dict]:
    r = list(route)
    improved = True
    while improved:
        improved = False
        for i in range(len(r) - 1):
            for j in range(i + 1, len(r)):
                candidate = r[:i] + r[i:j+1][::-1] + r[j+1:]
                if _total_distance(candidate, o_lat, o_lon) < _total_distance(r, o_lat, o_lon):
                    r = candidate
                    improved = True
    return r


def optimise_route(temples: list[dict], o_lat: float, o_lon: float) -> list[dict]:
    """NN + 2-opt. Falls back to NN-only above 15 stops (2-opt gets expensive)."""
    if not temples:
        return []
    route = _nearest_neighbour(temples, o_lat, o_lon)
    if len(route) <= 15:
        route = _two_opt(route, o_lat, o_lon)

    # Annotate with leg distances
    prev_lat, prev_lon = o_lat, o_lon
    annotated = []
    for i, t in enumerate(route):
        leg = round(haversine(prev_lat, prev_lon, t["lat"], t["lon"]), 2)
        annotated.append({**t, "seq": i + 1, "leg_km": leg})
        prev_lat, prev_lon = t["lat"], t["lon"]
    return annotated
