"""
portal.py – WatchGuard AI
Main entry point for the complete examination lifecycle portal.
Run with:  streamlit run portal.py
"""

import streamlit as st

import db
from pages import dashboard, duties, exams, faculty, monitoring, reports

# ---------------------------------------------------------------------------
# Page config — must be the very first Streamlit call
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="WatchGuard AI Portal",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Global CSS — blue & white professional theme
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    /* ── Base ── */
    html, body, [data-testid="stAppViewContainer"] {
        background: #f8fafc;
        color: #1e293b;
        font-family: 'Segoe UI', sans-serif;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e3a5f 0%, #1e40af 100%);
        border-right: none;
    }
    [data-testid="stSidebar"] * { color: #e0eaff !important; }

    /* ── Sidebar nav buttons ── */
    div[data-testid="stSidebar"] .stButton > button {
        width: 100%;
        background: transparent;
        border: 1px solid rgba(255,255,255,0.15);
        color: #e0eaff !important;
        border-radius: 8px;
        margin-bottom: 4px;
        text-align: left;
        padding: 10px 14px;
        font-size: 0.88rem;
        transition: background .2s;
    }
    div[data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(255,255,255,0.12);
        border-color: rgba(255,255,255,0.4);
    }

    /* ── Top header bar ── */
    .portal-header {
        background: linear-gradient(90deg, #1e3a5f, #2563eb);
        color: white;
        padding: 18px 28px;
        border-radius: 12px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    /* ── Section divider ── */
    .nav-section {
        font-size: .68rem;
        letter-spacing: .12em;
        text-transform: uppercase;
        color: rgba(255,255,255,0.45) !important;
        padding: 14px 4px 4px;
    }

    /* ── Login card ── */
    .login-card {
        max-width: 400px;
        margin: 80px auto;
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 40px;
        box-shadow: 0 4px 24px rgba(30,58,95,.10);
    }

    /* ── Hide Streamlit chrome ── */
    #MainMenu, footer, header { visibility: hidden; }
    [data-testid="stDecoration"] { display: none; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Admin credentials (hardcoded for hackathon demo)
# ---------------------------------------------------------------------------

ADMIN_USER = "admin"
ADMIN_PASS = "watchguard2025"

# ---------------------------------------------------------------------------
# Login gate
# ---------------------------------------------------------------------------

def render_login() -> None:
    st.markdown("""
    <div style="text-align:center;margin-top:60px">
        <div style="font-size:3rem">🛡️</div>
        <h2 style="color:#1e3a5f;margin:8px 0 4px">WatchGuard AI</h2>
        <p style="color:#64748b">Intelligent Invigilation Duty Monitoring System</p>
    </div>""", unsafe_allow_html=True)

    col = st.columns([1, 1.2, 1])[1]
    with col:
        with st.form("login_form"):
            st.markdown("**Admin Login**")
            username = st.text_input("Username", placeholder="admin")
            password = st.text_input("Password", type="password",
                                     placeholder="••••••••")
            submitted = st.form_submit_button("Sign In", type="primary",
                                              use_container_width=True)

        if submitted:
            if username == ADMIN_USER and password == ADMIN_PASS:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Invalid credentials. Try admin / watchguard2025")


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

NAV_ITEMS = [
    # (key, icon, label, section)
    ("dashboard",   "📊", "Dashboard",          "OVERVIEW"),
    ("faculty",     "👨🏫", "Faculty Management", "BEFORE EXAM"),
    ("exams",       "📝", "Exam Management",     "BEFORE EXAM"),
    ("duties",      "📋", "Duty Allocation",     "BEFORE EXAM"),
    ("monitoring",  "🎥", "AI Monitoring",       "DURING EXAM"),
    ("reports",     "📊", "Reports & Evidence",  "AFTER EXAM"),
]


def render_sidebar() -> str:
    with st.sidebar:
        st.markdown("""
        <div style="padding:16px 8px 8px;text-align:center">
            <div style="font-size:2rem">🛡️</div>
            <div style="font-weight:700;font-size:1.05rem;color:white">
                WatchGuard AI
            </div>
            <div style="font-size:.72rem;color:rgba(255,255,255,.55);margin-top:2px">
                Invigilation Portal
            </div>
        </div>
        <hr style="border-color:rgba(255,255,255,.15);margin:8px 0 12px">
        """, unsafe_allow_html=True)

        if "page" not in st.session_state:
            st.session_state.page = "dashboard"

        last_section = None
        for key, icon, label, section in NAV_ITEMS:
            if section != last_section:
                st.markdown(
                    f'<div class="nav-section">{section}</div>',
                    unsafe_allow_html=True,
                )
                last_section = section
            if st.button(f"{icon}  {label}", key=f"nav_{key}"):
                st.session_state.page = key

        st.markdown(
            '<hr style="border-color:rgba(255,255,255,.15);margin:16px 0 8px">',
            unsafe_allow_html=True,
        )
        if st.button("🚪  Sign Out", key="signout"):
            st.session_state.logged_in = False
            st.session_state.page = "dashboard"
            st.rerun()

        st.markdown(
            '<div style="font-size:.7rem;color:rgba(255,255,255,.35);'
            'text-align:center;padding-top:8px">YOLOv8 · SQLite · Streamlit</div>',
            unsafe_allow_html=True,
        )

    return st.session_state.get("page", "dashboard")


# ---------------------------------------------------------------------------
# Header bar
# ---------------------------------------------------------------------------

PAGE_TITLES = {
    "dashboard":  ("📊", "Dashboard",          "Complete examination lifecycle overview"),
    "faculty":    ("👨🏫", "Faculty Management", "Add and manage invigilation staff"),
    "exams":      ("📝", "Exam Management",     "Schedule and manage examinations"),
    "duties":     ("📋", "Duty Allocation",     "Smart AI-assisted duty assignment"),
    "monitoring": ("🎥", "AI Monitoring",       "Real-time phone detection during exams"),
    "reports":    ("📊", "Reports & Evidence",  "Post-exam analysis and integrity reports"),
}


def render_header(page: str) -> None:
    icon, title, subtitle = PAGE_TITLES.get(page, ("🛡️", page.title(), ""))
    st.markdown(f"""
    <div class="portal-header">
        <div>
            <div style="font-size:1.4rem;font-weight:700">{icon} {title}</div>
            <div style="font-size:.85rem;opacity:.8;margin-top:2px">{subtitle}</div>
        </div>
        <div style="font-size:.8rem;opacity:.7">WatchGuard AI Portal</div>
    </div>""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not st.session_state.get("logged_in"):
        render_login()
        return

    # Open a fresh connection on every Streamlit render cycle.
    # Reusing one connection across reruns (which run on different threads)
    # causes SQLite "ProgrammingError: objects created in a thread can only
    # be used in that same thread" even with check_same_thread=False,
    # leading to silent write failures on INSERT/UPDATE.
    conn = db.get_connection()
    db.init_schema(conn)

    page = render_sidebar()
    render_header(page)

    if page == "dashboard":
        dashboard.render(conn)
    elif page == "faculty":
        faculty.render(conn)
    elif page == "exams":
        exams.render(conn)
    elif page == "duties":
        duties.render(conn)
    elif page == "monitoring":
        monitoring.render(conn)
    elif page == "reports":
        reports.render(conn)


if __name__ == "__main__":
    main()
