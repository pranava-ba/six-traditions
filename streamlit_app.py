"""
streamlit_app.py — Six Traditions Temple Circuit MVP
"""

import sys, pathlib, io, csv, uuid, math, json
sys.path.insert(0, str(pathlib.Path(__file__).parent))

import streamlit as st
import folium
from streamlit_folium import st_folium

from chatbot import conversation, db as chatdb, router as chatrouter, resolver as chatresolver
from chatbot.formatter import welcome_message

st.set_page_config(
    page_title="Six Traditions — Temple Circuit",
    page_icon="🛕",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Warm parchment theme + fonts (no :has()) ─────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Tiro+Devanagari+Sanskrit:ital@0;1&family=JetBrains+Mono:wght@400;600&family=DM+Sans:wght@400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif !important;
    background-color: #faf5ee;
    color: #1a0f00;
}

h1, h2, h3, h4 {
    font-family: 'Tiro Devanagari Sanskrit', serif !important;
    color: #7c2d0a !important;
}

code, pre, .stCode {
    font-family: 'JetBrains Mono', monospace !important;
}

.stChatMessage { border-radius: 12px; }

.chat-header {
    background: linear-gradient(135deg, #7c2d0a 0%, #d4600a 100%);
    color: white;
    padding: 14px 20px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
    box-shadow: 0 2px 8px rgba(124,45,10,0.3);
}
.chat-header-text h3 { margin: 0; font-size: 1rem; color: white !important; font-family: 'DM Sans', sans-serif !important; }
.chat-header-text p  { margin: 0; font-size: .76rem; color: rgba(255,255,255,.78); }

.online-dot {
    width: 10px; height: 10px;
    background: #b8860b; border-radius: 50%;
    display: inline-block; flex-shrink: 0;
    box-shadow: 0 0 6px #b8860b;
}

.route-table-wrapper {
    border: 1px solid #d4b896;
    border-radius: 10px;
    overflow: hidden;
    margin-top: 12px;
    background: #fff8ef;
}
</style>
""", unsafe_allow_html=True)


# ── DIGIPIN encoder ──────────────────────────────────────────────────────────
_DP_CHARS = "23456789CJKLMPFT"
_DP_GRID  = [
    ["F", "C", "9", "8"],
    ["J", "3", "2", "7"],
    ["K", "4", "5", "6"],
    ["L", "M", "P", "T"],
]

def encode_digipin(lat: float, lon: float) -> str:
    if not (2.5 <= lat <= 38.5 and 63.5 <= lon <= 99.5):
        return "—"
    min_lat, max_lat = 2.5, 38.5
    min_lon, max_lon = 63.5, 99.5
    code = ""
    for i in range(10):
        lat_step = (max_lat - min_lat) / 4
        lon_step = (max_lon - min_lon) / 4
        row = int((max_lat - lat) / lat_step)
        col = int((lon - min_lon) / lon_step)
        row = min(row, 3); col = min(col, 3)
        code += _DP_GRID[row][col]
        max_lat -= row * lat_step
        min_lat  = max_lat - lat_step
        min_lon += col * lon_step
        max_lon  = min_lon + lon_step
    return f"{code[:4]}-{code[4:8]}-{code[8:]}"


# ── Naadu colour palette ─────────────────────────────────────────────────────
NAADU_COLORS = {
    "Thondai Naadu":      "#d4600a",
    "Nadu Naadu":         "#b8860b",
    "Cauvery Vadakarai":  "#2d6e3e",
    "Cauvery Thenkarai":  "#1a6b8a",
    "Pandya Naadu":       "#7c2d0a",
    "Kongu Naadu":        "#6b3fa0",
    "Malai Naadu":        "#2e7d32",
    "Vada Naadu":         "#1565c0",
    "Thuluva Naadu":      "#4a148c",
    "Ezha Naadu":         "#546e7a",
}
_DEFAULT_COLOR = "#8d6e63"


# ── Session bootstrap ─────────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({"role": "assistant", "content": welcome_message()})

SESSION_ID = st.session_state.session_id


# ── URL param: share route ────────────────────────────────────────────────────
# ?q=<location>&r=<radius_km>&algo=<algorithm>
params = st.query_params
_shared_q    = params.get("q", "")
_shared_r    = params.get("r", "")
_shared_algo = params.get("algo", "nn2opt")

if _shared_q and _shared_r and "shared_loaded" not in st.session_state:
    st.session_state.shared_loaded = True
    origin = chatresolver.resolve(_shared_q)
    try:
        radius = float(_shared_r)
    except ValueError:
        radius = None
    if origin and radius:
        pool  = chatrouter.temples_in_radius(origin["lat"], origin["lon"], radius)
        route = chatrouter.optimise_route(pool, origin["lat"], origin["lon"], algorithm=_shared_algo)
        chatdb.save_session(SESSION_ID, {
            "step": "RESULTS",
            "origin": origin,
            "pool": pool,
            "route": route,
            "radius_km": radius,
        })
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"Loaded shared route: **{_shared_q}**, {radius} km radius, {len(route)} temples.",
        })


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<h2 style="font-family:\'Tiro Devanagari Sanskrit\',serif;color:#7c2d0a">🛕 Six Traditions</h2>',
        unsafe_allow_html=True,
    )
    st.markdown("**Temple Circuit Planner**")
    st.divider()

    tab_info, tab_tools, tab_flagged, tab_about = st.tabs(["Session", "Tools", "Flagged", "Help"])

    with tab_info:
        sess_state  = chatdb.get_session(SESSION_ID)
        step        = sess_state.get("step", "IDLE")
        origin_info = sess_state.get("origin", {})
        route_info  = sess_state.get("route", [])
        radius_info = sess_state.get("radius_km", "—")

        st.markdown(f"**Status:** `{step}`")
        if origin_info:
            st.markdown(f"**Origin:** {origin_info.get('label','—')}")
            st.markdown(f"**Confidence:** {origin_info.get('confidence','—')}")
        if route_info:
            total_km = sum(t.get("leg_km", 0) for t in route_info)
            st.markdown(f"**Radius:** {radius_info} km")
            st.markdown(f"**Temples:** {len(route_info)}")
            st.markdown(f"**Total dist:** {total_km:.1f} km")
            naadus_set = sorted({t.get("naadu","") for t in route_info if t.get("naadu")})
            if naadus_set:
                st.markdown("**Naadus covered:**")
                for n in naadus_set:
                    col_hex = NAADU_COLORS.get(n, _DEFAULT_COLOR)
                    st.markdown(
                        f'<span style="display:inline-block;width:10px;height:10px;'
                        f'border-radius:50%;background:{col_hex};margin-right:6px"></span>{n}',
                        unsafe_allow_html=True,
                    )
        st.divider()
        if st.button("🔄 Reset conversation", use_container_width=True):
            chatdb.clear_session(SESSION_ID)
            st.session_state.messages = []
            st.session_state.messages.append({"role": "assistant", "content": welcome_message()})
            st.rerun()

    with tab_tools:
        st.markdown("##### Route settings")

        algo = st.selectbox(
            "Algorithm",
            options=["nn2opt", "nn", "bf"],
            format_func=lambda x: {
                "nn2opt": "Nearest Neighbour + 2-opt (recommended)",
                "nn": "Nearest Neighbour (fast)",
                "bf": "Brute Force (optimal, ≤10 stops)",
            }[x],
            key="algo",
        )

        max_temples = st.slider("Max temples", min_value=5, max_value=50, value=20, step=5, key="max_temples")

        if st.button("♻️ Re-optimise with these settings", use_container_width=True):
            sess = chatdb.get_session(SESSION_ID)
            pool_now   = sess.get("pool", [])
            origin_now = sess.get("origin", {})
            if pool_now and origin_now:
                trimmed = pool_now[:max_temples]
                new_route = chatrouter.optimise_route(
                    trimmed,
                    origin_now["lat"],
                    origin_now["lon"],
                    algorithm=algo,
                )
                sess["route"] = new_route
                chatdb.save_session(SESSION_ID, sess)
                st.success(f"{len(new_route)} temples optimised with {algo}.")
                st.rerun()
            else:
                st.warning("No active route to re-optimise. Search first.")

        st.divider()
        st.markdown("##### Share this route")
        sess_s  = chatdb.get_session(SESSION_ID)
        orig_s  = sess_s.get("origin", {})
        rad_s   = sess_s.get("radius_km", "")
        if orig_s and rad_s:
            share_label = orig_s.get("label", "")
            share_url = f"?q={share_label}&r={rad_s}&algo={algo}"
            st.code(share_url, language=None)
            st.caption("Copy and share this URL fragment. Recipients open the app with this appended.")
        else:
            st.caption("Search for a location first to generate a share link.")

    with tab_flagged:
        flagged = chatdb.flagged_temples()
        st.markdown(f"**{len(flagged)} temple(s) flagged for review**")
        for f in flagged:
            with st.expander(f"[{f['id']}] {f['name']}"):
                st.markdown(f"""
- **District:** {f['district'] or '—'}
- **State:** {f['state'] or '—'}
- **Pincode:** {f['pincode'] or '—'}
- **Reason:** _{f['reason']}_
""")

    with tab_about:
        st.markdown("""
**Commands:**

| Input | Action |
|---|---|
| `631502` | 6-digit pincode |
| `DIGIPIN` | 10-char code |
| `trichy` | district / city |
| `50` | radius in km |
| `LIST` | full temple list |
| `NAADU` | filter by region |
| `NEW` | restart |
| `HELP` | command menu |

**Traditions (testing now):**
🟠 Shaivam — 271 temples
""")


# ── Main layout ───────────────────────────────────────────────────────────────
col_chat, col_map = st.columns([1, 1], gap="large")

with col_chat:
    st.markdown("""
    <div class="chat-header">
        <span class="online-dot"></span>
        <div class="chat-header-text">
            <h3>🛕 Temple Circuit Bot</h3>
            <p>Shaivam &middot; Six Traditions &middot; MVP</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    for msg in st.session_state.messages:
        avatar = "🛕" if msg["role"] == "assistant" else "🙏"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    if user_input := st.chat_input("Pincode, DIGIPIN, or district name…"):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user", avatar="🙏"):
            st.markdown(user_input)

        replies = conversation.handle(SESSION_ID, user_input)
        for reply in replies:
            st.session_state.messages.append({"role": "assistant", "content": reply})
            with st.chat_message("assistant", avatar="🛕"):
                st.markdown(reply)

        st.rerun()

with col_map:
    st.markdown("#### 🗺️ Temple Route Map")

    live_state  = chatdb.get_session(SESSION_ID)
    live_route  = live_state.get("route", [])
    live_origin = live_state.get("origin", {})

    if not live_route:
        all_t = chatdb.all_temples()
        m = folium.Map(
            location=[11.0, 79.0],
            zoom_start=7,
            tiles="CartoDB positron",
        )
        for t in all_t:
            col_hex = NAADU_COLORS.get(t.get("naadu", ""), _DEFAULT_COLOR)
            folium.CircleMarker(
                location=[t["lat"], t["lon"]],
                radius=4,
                color=col_hex,
                fill=True,
                fill_color=col_hex,
                fill_opacity=0.7,
                tooltip=f"{t['name']} · {t['district']} · {t.get('naadu','—')}",
            ).add_to(m)
        st.caption(f"Overview — all {len(all_t)} Shaivam temples, colour-coded by Naadu. Search to see a route.")

    else:
        c_lat = live_origin.get("lat", live_route[0]["lat"])
        c_lon = live_origin.get("lon", live_route[0]["lon"])
        m = folium.Map(
            location=[c_lat, c_lon],
            zoom_start=9,
            tiles="CartoDB positron",
        )

        folium.Marker(
            location=[c_lat, c_lon],
            tooltip=f"Origin: {live_origin.get('label','Start')}",
            icon=folium.Icon(color="darkred", icon="home", prefix="fa"),
        ).add_to(m)

        coords = [[c_lat, c_lon]] + [[t["lat"], t["lon"]] for t in live_route]
        folium.PolyLine(coords, color="#7c2d0a", weight=2.5, opacity=0.75, dash_array="6 4").add_to(m)

        for t in live_route:
            naadu_col = NAADU_COLORS.get(t.get("naadu", ""), _DEFAULT_COLOR)
            approx    = " ≈" if t.get("coord_quality") == "approximate" else ""
            dp        = encode_digipin(t["lat"], t["lon"])
            folium.Marker(
                location=[t["lat"], t["lon"]],
                tooltip=f"{t['seq']}. {t['name']}{approx}",
                popup=folium.Popup(
                    f"<b>{t['seq']}. {t['name']}</b><br>"
                    f"{t['district']} · {t.get('naadu','—')}<br>"
                    f"Pin: {t.get('pincode','—')}<br>"
                    f"DIGIPIN: {dp}<br>"
                    f"{t['dist_km']} km from origin · leg {t['leg_km']} km",
                    max_width=230,
                ),
                icon=folium.DivIcon(
                    html=(
                        f'<div style="background:{naadu_col};color:white;border-radius:50%;'
                        f'width:26px;height:26px;display:flex;align-items:center;'
                        f'justify-content:center;font-size:11px;font-weight:700;'
                        f'box-shadow:0 1px 5px rgba(0,0,0,.45);'
                        f'border:2px solid white">{t["seq"]}</div>'
                    ),
                    icon_size=(26, 26),
                    icon_anchor=(13, 13),
                ),
            ).add_to(m)

        total_km = sum(t["leg_km"] for t in live_route)
        st.caption(
            f"{len(live_route)} temples · {total_km:.1f} km · "
            f"~{total_km/35:.1f} hrs driving · markers colour-coded by Naadu"
        )

    st_folium(m, use_container_width=True, height=520, returned_objects=[])

    # ── Route table + exports ─────────────────────────────────────────────────
    if live_route:
        st.markdown("#### Route Table")

        rows = []
        for t in live_route:
            dp = encode_digipin(t["lat"], t["lon"])
            rows.append({
                "#":         t["seq"],
                "Temple":    t["name"],
                "District":  t["district"],
                "Naadu":     t.get("naadu", "—"),
                "Pincode":   t.get("pincode", "—"),
                "DIGIPIN":   dp,
                "Dist (km)": t["dist_km"],
                "Leg (km)":  t["leg_km"],
            })

        st.dataframe(rows, use_container_width=True, hide_index=True)

        # CSV export
        csv_buf = io.StringIO()
        writer = csv.DictWriter(csv_buf, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        st.download_button(
            "⬇ Download CSV",
            data=csv_buf.getvalue().encode("utf-8"),
            file_name="temple_circuit.csv",
            mime="text/csv",
        )

        # GPX export
        origin_label = live_origin.get("label", "Origin")
        gpx_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<gpx version="1.1" creator="Six Traditions" xmlns="http://www.topografix.com/GPX/1/1">',
            f'<trk><name>Temple Circuit — {origin_label}</name><trkseg>',
        ]
        o_lat = live_origin.get("lat", live_route[0]["lat"])
        o_lon = live_origin.get("lon", live_route[0]["lon"])
        gpx_lines.append(f'<trkpt lat="{o_lat}" lon="{o_lon}"><name>Origin: {origin_label}</name></trkpt>')
        for t in live_route:
            gpx_lines.append(
                f'<trkpt lat="{t["lat"]}" lon="{t["lon"]}">'
                f'<name>{t["seq"]}. {t["name"]}</name>'
                f'</trkpt>'
            )
        gpx_lines.extend(["</trkseg></trk>", "</gpx>"])
        gpx_data = "\n".join(gpx_lines)

        st.download_button(
            "⬇ Download GPX",
            data=gpx_data.encode("utf-8"),
            file_name="temple_circuit.gpx",
            mime="application/gpx+xml",
        )
