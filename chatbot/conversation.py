"""
conversation.py — Multi-turn conversation state machine.

States:
  IDLE          — waiting for a location
  AWAIT_RADIUS  — location resolved, waiting for km
  RESULTS       — showing results, accepting commands

Each user turn calls handle(session_id, text) → list[str] (messages to send back).
"""

import re
from chatbot import db, resolver, router, formatter


# ── Helpers ──────────────────────────────────────────────────────────────────
def _is_radius(text: str) -> float | None:
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(?:km)?\s*", text.strip(), re.IGNORECASE)
    return float(m.group(1)) if m else None


def _available_naadus(route: list[dict]) -> list[str]:
    seen = []
    for t in route:
        n = t.get("naadu", "")
        if n and n not in seen:
            seen.append(n)
    return sorted(seen)


# ── Main handler ─────────────────────────────────────────────────────────────
def handle(session_id: str, text: str) -> list[str]:
    state = db.get_session(session_id)
    step  = state.get("step", "IDLE")
    cmd   = text.strip().upper()

    # ── Global commands (work in any state) ──────────────────────────────────
    if cmd in ("HELP", "HI", "HELLO", "START", "/START"):
        db.clear_session(session_id)
        return [formatter.welcome_message()]

    if cmd == "NEW":
        db.clear_session(session_id)
        return [
            "🔄 Starting fresh.\n\n"
            "Send a *pincode*, *DIGIPIN*, or *district name* to search."
        ]

    if cmd == "LIST" and step == "RESULTS":
        route = state.get("route", [])
        if not route:
            return ["No results to list. Send a location to start."]
        origin = state.get("origin", {})
        msgs = formatter.itinerary_messages(origin, route)
        return msgs[1:] if len(msgs) > 1 else msgs  # skip summary, show detail

    if cmd == "NAADU" and step == "RESULTS":
        route  = state.get("route", [])
        naadus = _available_naadus(route)
        if not naadus:
            return ["No Naadu data available for current results."]
        state["step"] = "AWAIT_NAADU"
        db.save_session(session_id, state)
        return [formatter.naadu_menu_message(naadus)]

    # ── AWAIT_NAADU ───────────────────────────────────────────────────────────
    if step == "AWAIT_NAADU":
        route  = state.get("route", [])
        naadus = _available_naadus(route)
        if cmd == "0":
            state["step"] = "RESULTS"
            db.save_session(session_id, state)
            origin = state.get("origin", {})
            return formatter.itinerary_messages(origin, route)

        if re.fullmatch(r"\d+", cmd):
            idx = int(cmd) - 1
            if 0 <= idx < len(naadus):
                chosen = naadus[idx]
                filtered = [t for t in route if t.get("naadu") == chosen]
                if not filtered:
                    return [f"No temples in *{chosen}* within the current search. Send *0* to go back."]
                state["step"] = "RESULTS"
                state["route"] = filtered
                db.save_session(session_id, state)
                origin = state.get("origin", {})
                return [f"Showing *{len(filtered)}* temples in _{chosen}_\n"] + formatter.itinerary_messages(origin, filtered)
            else:
                return [f"Please reply with a number between 1 and {len(naadus)}, or *0* for all."]

        return [f"Please reply with a number (1–{len(naadus)}) or *0* for all."]

    # ── IDLE — expect a location ───────────────────────────────────────────────
    if step == "IDLE":
        origin = resolver.resolve(text.strip())
        if not origin:
            return [formatter.unresolvable_location_message(text.strip())]
        state = {"step": "AWAIT_RADIUS", "origin": origin}
        db.save_session(session_id, state)
        return [formatter.ask_radius_message(origin)]

    # ── AWAIT_RADIUS — expect a number ────────────────────────────────────────
    if step == "AWAIT_RADIUS":
        radius = _is_radius(text)
        if radius is None:
            # Maybe they typed a new location instead
            origin = resolver.resolve(text.strip())
            if origin:
                state["origin"] = origin
                db.save_session(session_id, state)
                return [formatter.ask_radius_message(origin)]
            return [
                "Please reply with a distance in km, e.g. `50`\n\n"
                "Or send a new location to change the origin."
            ]

        if radius < 1 or radius > 1000:
            return ["Please enter a radius between *1* and *1000* km."]

        origin = state["origin"]
        pool   = router.temples_in_radius(origin["lat"], origin["lon"], radius)

        if not pool:
            db.clear_session(session_id)
            return [formatter.no_temples_message(radius, origin["label"])]

        route  = router.optimise_route(pool, origin["lat"], origin["lon"])
        state  = {"step": "RESULTS", "origin": origin, "pool": pool, "route": route, "radius_km": radius}
        db.save_session(session_id, state)
        return formatter.itinerary_messages(origin, route)

    # ── RESULTS — idle commands fall through here ─────────────────────────────
    if step == "RESULTS":
        # They may have typed a new location directly
        origin = resolver.resolve(text.strip())
        if origin:
            state = {"step": "AWAIT_RADIUS", "origin": origin}
            db.save_session(session_id, state)
            return [formatter.ask_radius_message(origin)]
        return [
            "Send *NEW* to start a new search,\n"
            "*LIST* to see the full temple list,\n"
            "*NAADU* to filter by region,\n"
            "or *HELP* for all commands."
        ]

    # Fallback
    db.clear_session(session_id)
    return [formatter.welcome_message()]
