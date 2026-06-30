"""
streamlit_app.py — Six Traditions Temple Circuit MVP
"""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))

import streamlit as st
import folium
from streamlit_folium import st_folium

from chatbot import conversation, db as chatdb, router, resolver

st.set_page_config(
    page_title="Six Traditions — Temple Circuit",
    page_icon="🛕",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif !important; }

.chat-header {
    background: #075E54;
    color: white;
    padding: 12px 20px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
}
.chat-header-text h3 { margin: 0; font-size: 1rem; color: white !important; }
.chat-header-text p  { margin: 0; font-size: .76rem; color: rgba(255,255,255,.7); }
.online-dot {
    width: 10px; height: 10px;
    background: #25D366; border-radius: 50%;
    display: inline-block; flex-shrink: 0;
}
</style>
""", unsafe_allow_html=True)


# ── Session bootstrap ─────────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    import uuid
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []
    from chatbot.formatter import welcome_message
    st.session_state.messages.append({"role": "assistant", "content": welcome_message()})

SESSION_ID = st.session_state.session_id


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛕 Six Traditions")
    st.markdown("**Temple Circuit Planner**")
    st.divider()

    tab_info, tab_flagged, tab_about = st.tabs(["Session", "Flagged", "Help"])

    with tab_info:
        state  = chatdb.get_session(SESSION_ID)
        step   = state.get("step", "IDLE")
        origin = state.get("origin", {})
        route  = state.get("route", [])

        st.markdown(f"**Status:** `{step}`")
        if origin:
            st.markdown(f"**Origin:** {origin.get('label','—')}")
            st.markdown(f"**Confidence:** {origin.get('confidence','—')}")
        if route:
            total_km = sum(t.get("leg_km", 0) for t in route)
            st.markdown(f"**Temples in route:** {len(route)}")
            st.markdown(f"**Total distance:** {total_km:.1f} km")
            naadus = sorted({t.get("naadu","") for t in route if t.get("naadu")})
            if naadus:
                st.markdown("**Naadus covered:**")
                for n in naadus:
                    st.markdown(f"- {n}")

        st.divider()
        if st.button("🔄 Reset conversation", use_container_width=True):
            chatdb.clear_session(SESSION_ID)
            st.session_state.messages = []
            from chatbot.formatter import welcome_message
            st.session_state.messages.append({"role": "assistant", "content": welcome_message()})
            st.rerun()

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
            <p>Shaivam · Six Traditions · MVP</p>
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

    state  = chatdb.get_session(SESSION_ID)
    route  = state.get("route", [])
    origin = state.get("origin", {})

    if not route:
        all_t = chatdb.all_temples()
        m = folium.Map(location=[11.0, 79.0], zoom_start=7)
        for t in all_t:
            folium.CircleMarker(
                location=[t["lat"], t["lon"]],
                radius=4,
                color="#c97a1a",
                fill=True,
                fill_color="#c97a1a",
                fill_opacity=0.6,
                tooltip=f"{t['name']} · {t['district']}",
            ).add_to(m)
        st.caption(f"Overview — all {len(all_t)} Shaivam temples. Search to see a route.")
    else:
        c_lat = origin.get("lat", route[0]["lat"])
        c_lon = origin.get("lon", route[0]["lon"])
        m = folium.Map(location=[c_lat, c_lon], zoom_start=9)

        folium.Marker(
            location=[c_lat, c_lon],
            tooltip=f"Origin: {origin.get('label','Start')}",
            icon=folium.Icon(color="green", icon="home", prefix="fa"),
        ).add_to(m)

        coords = [[c_lat, c_lon]] + [[t["lat"], t["lon"]] for t in route]
        folium.PolyLine(coords, color="#c97a1a", weight=2.5, opacity=0.8, dash_array="6").add_to(m)

        for t in route:
            approx = " (approx)" if t.get("coord_quality") == "approximate" else ""
            folium.Marker(
                location=[t["lat"], t["lon"]],
                tooltip=f"{t['seq']}. {t['name']}{approx}",
                popup=folium.Popup(
                    f"<b>{t['name']}</b><br>"
                    f"{t['district']}<br>"
                    f"Naadu: {t.get('naadu','—')}<br>"
                    f"Pin: {t.get('pincode','—')}<br>"
                    f"{t['dist_km']} km from origin · leg {t['leg_km']} km",
                    max_width=220,
                ),
                icon=folium.DivIcon(
                    html=(
                        f'<div style="background:#c97a1a;color:white;border-radius:50%;'
                        f'width:24px;height:24px;display:flex;align-items:center;'
                        f'justify-content:center;font-size:11px;font-weight:700;'
                        f'box-shadow:0 1px 4px rgba(0,0,0,.4);'
                        f'border:2px solid white">{t["seq"]}</div>'
                    ),
                    icon_size=(24, 24),
                    icon_anchor=(12, 12),
                ),
            ).add_to(m)

        total_km = sum(t["leg_km"] for t in route)
        st.caption(
            f"{len(route)} temples · {total_km:.1f} km · "
            f"~{total_km/35:.1f} hrs driving · click markers for details"
        )

    st_folium(m, use_container_width=True, height=560, returned_objects=[])
