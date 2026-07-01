"""
router.py — Haversine radius filter + TSP route optimisation.
Algorithms: nn | nn2opt (default) | bf (brute-force, auto-caps at 10 temples)
"""

import math
from itertools import permutations
from chatbot.db import all_temples

_EARTH_R = 6371.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return _EARTH_R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def temples_in_radius(
    lat: float,
    lon: float,
    radius_km: float,
    max_results: int = 20,
    naadu_filter: str | None = None,
) -> list[dict]:
    results = []
    for t in all_temples():
        d = haversine(lat, lon, t["lat"], t["lon"])
        if d <= radius_km:
            if naadu_filter and t.get("naadu") != naadu_filter:
                continue
            results.append({**t, "dist_km": round(d, 2)})
    results.sort(key=lambda x: x["dist_km"])
    return results[:max_results]


def _total_distance(route: list[dict], o_lat: float, o_lon: float) -> float:
    d, prev_lat, prev_lon = 0.0, o_lat, o_lon
    for t in route:
        d += haversine(prev_lat, prev_lon, t["lat"], t["lon"])
        prev_lat, prev_lon = t["lat"], t["lon"]
    return d


def _nearest_neighbour(temples: list[dict], o_lat: float, o_lon: float) -> list[dict]:
    remaining = list(temples)
    route, cur_lat, cur_lon = [], o_lat, o_lon
    while remaining:
        idx = min(range(len(remaining)),
                  key=lambda i: haversine(cur_lat, cur_lon, remaining[i]["lat"], remaining[i]["lon"]))
        best = remaining.pop(idx)
        route.append(best)
        cur_lat, cur_lon = best["lat"], best["lon"]
    return route


def _two_opt(route: list[dict], o_lat: float, o_lon: float) -> list[dict]:
    r, improved = list(route), True
    while improved:
        improved = False
        for i in range(len(r) - 1):
            for j in range(i + 1, len(r)):
                candidate = r[:i] + r[i:j+1][::-1] + r[j+1:]
                if _total_distance(candidate, o_lat, o_lon) < _total_distance(r, o_lat, o_lon):
                    r, improved = candidate, True
    return r


def _brute_force(temples: list[dict], o_lat: float, o_lon: float) -> list[dict]:
    if len(temples) > 10:
        return _nearest_neighbour(temples, o_lat, o_lon)
    best_route, best_d = None, float("inf")
    for perm in permutations(temples):
        d = _total_distance(list(perm), o_lat, o_lon)
        if d < best_d:
            best_d, best_route = d, list(perm)
    return best_route


def optimise_route(
    temples: list[dict],
    o_lat: float,
    o_lon: float,
    algorithm: str = "nn2opt",
) -> list[dict]:
    """
    algorithm: 'nn' | 'nn2opt' (default) | 'bf'
    bf auto-falls back to nn when > 10 temples.
    nn2opt auto-skips 2-opt when > 15 temples.
    """
    if not temples:
        return []

    if algorithm == "nn":
        route = _nearest_neighbour(temples, o_lat, o_lon)
    elif algorithm == "bf":
        route = _brute_force(temples, o_lat, o_lon)
    else:  # nn2opt
        route = _nearest_neighbour(temples, o_lat, o_lon)
        if len(route) <= 15:
            route = _two_opt(route, o_lat, o_lon)

    prev_lat, prev_lon = o_lat, o_lon
    annotated = []
    for i, t in enumerate(route):
        leg = round(haversine(prev_lat, prev_lon, t["lat"], t["lon"]), 2)
        annotated.append({**t, "seq": i + 1, "leg_km": leg})
        prev_lat, prev_lon = t["lat"], t["lon"]
    return annotated
