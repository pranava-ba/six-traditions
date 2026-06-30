"""
streamlit_app.py — Six Traditions Temple Circuit MVP
Simulates the WhatsApp chatbot in a browser chat UI.
Deploy free: streamlit run streamlit_app.py
             or push to Streamlit Cloud.
"""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))

import streamlit as st
import folium
from streamlit_folium import st_folium

from chatbot import conversation, db as chatdb, router, resolver

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Six Traditions — Temple Circuit",
    page_icon="🛕",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS: WhatsApp-like chat bubbles ──────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif !important; }

.stApp { background: #ECE5DD; }

section[data-testid="stSidebar"] {
    background: #1a1a2e !important;
    border-right: 1px solid #2d2d44 !important;
}
section[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 { color: #d4a855 !important; }

/* Chat area */
.block-container { padding: 1rem 1.5rem 5rem !important; max-width: 860px !important; margin: 0 auto !important; }

/* User bubble */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background: #DCF8C6 !important;
    border-radius: 18px 18px 4px 18px !important;
    padding: 10px 14px !important;
    margin: 4px 0 4px auto !important;
    max-width: 75% !important;
    box-shadow: 0 1px 2px rgba(0,0,0,.12) !important;
}

/* Bot bubble */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    background: #FFFFFF !important;
    border-radius: 18px 18px 18px 4px !important;
    padding: 10px 14px !important;
    margin: 4px auto 4px 0 !important;
    max-width: 75% !important;
    box-shadow: 0 1px 2px rgba(0,0,0,.12) !important;
}

/* Header strip */
.chat-header {
    background: #075E54;
    color: white;
    padding: 10px 18px;
    border-radius: 10px 10px 0 0;
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
}
.chat-header h3 { margin: 0; font-size: 1rem; color: white; }
.chat-header p  { margin: 0; font-size: .75rem; opacity: .75; }

.online-dot { width: 9px; height: 9px; background: #25D366; border-radius: 50%; display: inline-block; }

/* Input box styling */
[data-testid="stChatInput"] textarea {
    background: #fff !important;
    border-radius: 24px !important;
    border: 1px solid #ccc !important;
    padding: 10px 16px !important;
}
</style>
""", unsafe_allow_html=True)


# ── Session bootstrap ─────────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    import uuid
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []
    # Seed the welcome message
    from chatbot.formatter import welcome_message
    st.session_state.messages.append({"role": "assistant", "content": welcome_message()})

SESSION_ID = st.session_state.session_id


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛕 Six Traditions")
    st.markdown("**Temple Circuit Planner**")
    st.markdown("---")

    tab_info, tab_flagged, tab_about = st.tabs(["ℹ️ Session", "⚠️ Flagged", "📖 Help"])

    with tab_info:
        state = chatdb.get_session(SESSION_ID)
        step  = state.get("step", "IDLE")
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
                    st.markdown(f"  - {n}")

        st.markdown("---")
        if st.button("🔄 Reset conversation", use_container_width=True):
            chatdb.clear_session(SESSION_ID)
            st.session_state.messages = []
            from chatbot.formatter import welcome_message
            st.session_state.messages.append({"role": "assistant", "content": welcome_message()})
            st.rerun()

    with tab_flagged:
        flagged = chatdb.flagged_temples()
        st.markdown(f"**{len(flagged)} temple(s) could not be resolved**")
        for f in flagged:
            st.markdown(f"""
**[{f['id']}] {f['name']}**
- District: {f['district'] or '—'}
- State: {f['state'] or '—'}
- Pincode: {f['pincode'] or '—'}
- _Reason: {f['reason']}_
""")

    with tab_about:
        st.markdown("""
**Commands you can type:**

| Input | What happens |
|---|---|
| `631502` | 6-digit pincode |
| `DIGIPIN` | 10-char code |
| `trichy` | district / city name |
| `50` | radius in km (after location) |
| `LIST` | full temple detail |
| `NAADU` | filter by region |
| `NEW` | restart search |
| `HELP` | command menu |

**Traditions supported (testing):**
- Shaivam (271 temples)

**Data:** India Post DIGIPIN · India Post Pincode DB
""")


# ── Main: two columns — chat + map ────────────────────────────────────────────
col_chat, col_map = st.columns([1.1, 1], gap="medium")

with col_chat:
    st.markdown("""
    <div class="chat-header">
      <span class="online-dot"></span>
      <div>
        <h3>🛕 Temple Circuit Bot</h3>
        <p>Shaivam · Six Traditions · MVP</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Render chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="🛕" if msg["role"] == "assistant" else "🙏"):
            st.markdown(msg["content"])

    # Input
    if user_input := st.chat_input("Type a pincode, DIGIPIN, or district name…"):
        # Show user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user", avatar="🙏"):
            st.markdown(user_input)

        # Get bot replies
        replies = conversation.handle(SESSION_ID, user_input)
        for reply in replies:
            st.session_state.messages.append({"role": "assistant", "content": reply})
            with st.chat_message("assistant", avatar="🛕"):
                st.markdown(reply)

        st.rerun()

with col_map:
    st.markdown("#### 🗺️ Temple Route Map")

    state = chatdb.get_session(SESSION_ID)
    route = state.get("route", [])
    origin = state.get("origin", {})

    if not route:
        # Show all temples (overview)
        all_t = chatdb.all_temples()
        m = folium.Map(location=[11.0, 79.0], zoom_start=7, tiles="CartoDB positron")
        for t in all_t:
            folium.CircleMarker(
                location=[t["lat"], t["lon"]],
                radius=4,
                color="#c97a1a",
                fill=True,
                fill_opacity=0.6,
                tooltip=f"{t['name']} · {t['district']}",
            ).add_to(m)
        st.caption(f"Overview — all {len(all_t)} Shaivam temples. Search to see a route.")
    else:
        # Centre map on origin
        center_lat = origin.get("lat", route[0]["lat"])
        center_lon = origin.get("lon", route[0]["lon"])
        m = folium.Map(location=[center_lat, center_lon], zoom_start=9, tiles="CartoDB positron")

        # Origin marker
        folium.Marker(
            location=[center_lat, center_lon],
            tooltip=f"Origin: {origin.get('label','Start')}",
            icon=folium.Icon(color="green", icon="home", prefix="fa"),
        ).add_to(m)

        # Draw route polyline
        coords = [[center_lat, center_lon]] + [[t["lat"], t["lon"]] for t in route]
        folium.PolyLine(coords, color="#c97a1a", weight=2.5, opacity=0.7, dash_array="6").add_to(m)

        # Temple markers
        for t in route:
            quality_note = " _(approx)_" if t.get("coord_quality") == "approximate" else ""
            folium.Marker(
                location=[t["lat"], t["lon"]],
                tooltip=f"{t['seq']}. {t['name']}{quality_note}\n{t['district']} · {t.get('naadu','')}",
                popup=folium.Popup(
                    f"<b>{t['name']}</b><br>{t['district']}<br>"
                    f"Naadu: {t.get('naadu','—')}<br>"
                    f"Pin: {t.get('pincode','—')}<br>"
                    f"{t['dist_km']} km from origin · leg {t['leg_km']} km",
                    max_width=220,
                ),
                icon=folium.DivIcon(
                    html=f'<div style="background:#c97a1a;color:white;border-radius:50%;'
                         f'width:22px;height:22px;display:flex;align-items:center;'
                         f'justify-content:center;font-size:11px;font-weight:700;'
                         f'box-shadow:0 1px 4px rgba(0,0,0,.4)">{t["seq"]}</div>',
                    icon_size=(22, 22),
                    icon_anchor=(11, 11),
                ),
            ).add_to(m)

        total_km = sum(t["leg_km"] for t in route)
        st.caption(
            f"{len(route)} temples · {total_km:.1f} km total · "
            f"~{total_km/35:.1f} hrs driving · click markers for details"
        )

    st_folium(m, use_container_width=True, height=540, returned_objects=[])
