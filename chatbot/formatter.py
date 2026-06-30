"""
formatter.py — Formats search results as WhatsApp-friendly plain text.

WhatsApp renders:
  *bold*    _italic_    ```mono```
  Lists with hyphens or numbers are plain text.
  Max recommended message: ~1000 chars before splitting.
"""

from chatbot.router import haversine

MAX_MSG_CHARS = 900   # split if itinerary exceeds this
DRIVE_SPEED   = 35.0  # km/h assumed average (temple roads, India)


def _coord_quality_note(temple: dict) -> str:
    if temple.get("coord_quality") == "approximate":
        src = temple.get("coord_source", "centroid")
        return f" _(approx — {src})_"
    return ""


def welcome_message() -> str:
    return (
        "🛕 *Six Traditions — Temple Circuit*\n\n"
        "Welcome! I'll help you plan a Shaivam temple visit.\n\n"
        "Send me your *pincode* (6 digits) or *DIGIPIN* to get started.\n\n"
        "_You can also type a district name like_ `Thanjavur` _or a city like_ `trichy`."
    )


def ask_radius_message(origin: dict) -> str:
    conf_note = "" if origin["confidence"] == "high" else f"\n_(Location resolved with {origin['confidence']} confidence — please verify)_"
    return (
        f"📍 Got it — *{origin['label']}*\n"
        f"Coordinates: `{origin['lat']}, {origin['lon']}`{conf_note}\n\n"
        "How far are you willing to travel?\n"
        "Reply with a number in *km*, e.g.:\n"
        "  `25`   `50`   `100`   `150`"
    )


def no_temples_message(radius_km: float, origin_label: str) -> str:
    return (
        f"😔 No Shaivam temples found within *{radius_km:.0f} km* of {origin_label}.\n\n"
        "Try a larger radius or a different location.\n"
        "Send a new pincode / DIGIPIN / district name to restart."
    )


def itinerary_messages(origin: dict, route: list[dict]) -> list[str]:
    """
    Returns a list of WhatsApp messages (split if too long).
    First message = summary. Subsequent = temple list chunks.
    """
    total_km   = sum(t["leg_km"] for t in route)
    drive_hrs  = total_km / DRIVE_SPEED
    districts  = len({t["district"] for t in route})

    # ── Summary card ──────────────────────────────────────────────────────────
    summary = (
        f"🛕 *Temple Circuit — {origin['label']}*\n"
        f"{'─' * 28}\n"
        f"🏛  Temples found : *{len(route)}*\n"
        f"📏  Total distance: *{total_km:.1f} km*\n"
        f"🕐  Est. drive    : *{drive_hrs:.1f} hrs*\n"
        f"🗺  Districts     : *{districts}*\n"
        f"{'─' * 28}\n"
        f"Route optimised (NN + 2-opt)\n\n"
        "Send *LIST* for full details\n"
        "Send *NEW* to search again\n"
        "Send *NAADU* to filter by region"
    )

    # ── Temple lines ──────────────────────────────────────────────────────────
    lines = []
    for t in route:
        naadu = f" · {t['naadu']}" if t.get("naadu") else ""
        approx = _coord_quality_note(t)
        pincode = f" · Pin {t['pincode']}" if t.get("pincode") else ""
        lines.append(
            f"*{t['seq']}.* {t['name']}{approx}\n"
            f"   📍 {t['district']}{naadu}{pincode}\n"
            f"   ↔ {t['dist_km']} km from origin · leg {t['leg_km']} km"
        )

    # Split into chunks under MAX_MSG_CHARS
    messages = [summary]
    chunk = ""
    for line in lines:
        candidate = (chunk + "\n\n" + line).lstrip()
        if len(candidate) > MAX_MSG_CHARS:
            if chunk:
                messages.append(chunk.strip())
            chunk = line
        else:
            chunk = candidate
    if chunk.strip():
        messages.append(chunk.strip())

    return messages


def naadu_menu_message(available_naadus: list[str]) -> str:
    opts = "\n".join(f"  {i+1}. {n}" for i, n in enumerate(available_naadus))
    return (
        "🗺 *Filter by Naadu (region)*\n\n"
        "Reply with a number:\n"
        f"{opts}\n\n"
        "Or send *0* to show all."
    )


def unresolvable_location_message(query: str) -> str:
    return (
        f"❓ Sorry, I couldn't recognise *\"{query}\"* as a location.\n\n"
        "Please try:\n"
        "  • A *6-digit pincode* (e.g. `631502`)\n"
        "  • A *DIGIPIN* (e.g. `J3K-4M5-P6T2`)\n"
        "  • A *district name* (e.g. `Thanjavur`, `trichy`, `kanchi`)"
    )


def help_message() -> str:
    return (
        "📖 *Commands*\n\n"
        "*NEW* — Start a new search\n"
        "*LIST* — Show full temple list\n"
        "*NAADU* — Filter current results by region\n"
        "*HELP* — Show this menu\n\n"
        "To search, send a pincode, DIGIPIN, or district name."
    )
