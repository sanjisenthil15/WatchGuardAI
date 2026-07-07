"""
WatchGuard AI – Intelligent Invigilation Duty Monitoring System
Streamlit Dashboard: incident metrics, evidence viewer, and incident history.
"""

import os
import sqlite3
from datetime import date

import pandas as pd
import streamlit as st
from PIL import Image

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH        = "watchguard.db"
SCREENSHOT_DIR = "screenshots"

st.set_page_config(
    page_title="WatchGuard AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Global dark-theme CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    /* ── Base ── */
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #0e1117;
        color: #e0e0e0;
    }
    [data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #30363d;
    }

    /* ── Metric cards ── */
    .card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 20px 24px;
        text-align: center;
    }
    .card-label {
        font-size: 0.78rem;
        color: #8b949e;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 6px;
    }
    .card-value {
        font-size: 2rem;
        font-weight: 700;
        color: #f0f6fc;
    }
    .card-sub {
        font-size: 0.78rem;
        color: #8b949e;
        margin-top: 4px;
    }

    /* ── Alert accent ── */
    .alert-card { border-color: #da3633; }
    .alert-card .card-value { color: #ff7b72; }

    /* ── Section headers ── */
    .section-title {
        font-size: 1rem;
        font-weight: 600;
        color: #8b949e;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin: 28px 0 12px;
        border-bottom: 1px solid #30363d;
        padding-bottom: 6px;
    }

    /* ── Dataframe ── */
    [data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }

    /* ── Sidebar nav buttons ── */
    div[data-testid="stSidebar"] .stButton > button {
        width: 100%;
        background: transparent;
        border: 1px solid #30363d;
        color: #c9d1d9;
        border-radius: 8px;
        margin-bottom: 6px;
        text-align: left;
        padding: 10px 14px;
        font-size: 0.9rem;
    }
    div[data-testid="stSidebar"] .stButton > button:hover {
        background: #21262d;
        border-color: #58a6ff;
        color: #58a6ff;
    }

    /* ── Hide default Streamlit chrome ── */
    #MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

@st.cache_resource
def get_connection() -> sqlite3.Connection:
    """Return a cached SQLite connection. Creates DB/table if absent."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            date            TEXT NOT NULL,
            time            TEXT NOT NULL,
            anomaly_type    TEXT NOT NULL,
            confidence      REAL NOT NULL,
            screenshot_path TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def load_incidents(conn: sqlite3.Connection) -> pd.DataFrame:
    """Load all incidents from the database into a DataFrame."""
    df = pd.read_sql_query(
        "SELECT id, date, time, anomaly_type, confidence, screenshot_path "
        "FROM incidents ORDER BY id DESC",
        conn,
    )
    return df

# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def compute_metrics(df: pd.DataFrame) -> dict:
    """Derive summary statistics from the incidents DataFrame."""
    today = date.today().isoformat()
    today_df = df[df["date"] == today]

    latest = df.iloc[0] if not df.empty else None
    highest = df.loc[df["confidence"].idxmax()] if not df.empty else None

    return {
        "total":          len(df),
        "today":          len(today_df),
        "latest_time":    f"{latest['date']}  {latest['time']}" if latest is not None else "—",
        "latest_type":    latest["anomaly_type"]                if latest is not None else "—",
        "highest_conf":   f"{highest['confidence']:.2%}"        if highest is not None else "—",
        "highest_time":   f"{highest['date']}  {highest['time']}" if highest is not None else "—",
        "latest_img":     latest["screenshot_path"]             if latest is not None else None,
    }

# ---------------------------------------------------------------------------
# UI components
# ---------------------------------------------------------------------------

def render_metric_card(label: str, value: str, sub: str = "",
                       alert: bool = False) -> str:
    """Return HTML for a single metric card."""
    accent = "alert-card" if alert else ""
    return f"""
    <div class="card {accent}">
        <div class="card-label">{label}</div>
        <div class="card-value">{value}</div>
        {"<div class='card-sub'>" + sub + "</div>" if sub else ""}
    </div>"""


def render_dashboard(df: pd.DataFrame, metrics: dict) -> None:
    """Render the main dashboard page."""
    st.markdown('<p class="section-title">Live Metrics</p>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(render_metric_card("Total Incidents",   str(metrics["total"]),
                                   alert=metrics["total"] > 0), unsafe_allow_html=True)
    c2.markdown(render_metric_card("Today's Incidents", str(metrics["today"]),
                                   alert=metrics["today"] > 0), unsafe_allow_html=True)
    c3.markdown(render_metric_card("Latest Detection",  metrics["latest_time"],
                                   sub=metrics["latest_type"]), unsafe_allow_html=True)
    c4.markdown(render_metric_card("Highest Confidence", metrics["highest_conf"],
                                   sub=metrics["highest_time"]), unsafe_allow_html=True)

    # Latest evidence image
    st.markdown('<p class="section-title">Latest Evidence</p>', unsafe_allow_html=True)
    img_path = metrics["latest_img"]
    if img_path and os.path.exists(img_path):
        img = Image.open(img_path)
        st.image(img, caption=os.path.basename(img_path), use_container_width=True)
    else:
        st.info("No evidence images recorded yet.")

    # Recent incidents table (top 10)
    st.markdown('<p class="section-title">Recent Incidents</p>', unsafe_allow_html=True)
    if df.empty:
        st.info("No incidents in the database yet.")
    else:
        display_cols = ["date", "time", "anomaly_type", "confidence", "screenshot_path"]
        st.dataframe(
            df[display_cols].head(10).rename(columns={
                "date":            "Date",
                "time":            "Time",
                "anomaly_type":    "Anomaly Type",
                "confidence":      "Confidence",
                "screenshot_path": "Screenshot Path",
            }),
            use_container_width=True,
            hide_index=True,
        )


def render_incident_history(df: pd.DataFrame) -> None:
    """Render the full incident history page with search and export."""
    st.markdown('<p class="section-title">Incident History</p>', unsafe_allow_html=True)

    if df.empty:
        st.info("No incidents recorded yet.")
        return

    # Search / filter
    search = st.text_input("🔍  Filter by date or anomaly type", placeholder="e.g. 2025-07-14")
    filtered = df[
        df["date"].str.contains(search, case=False, na=False) |
        df["anomaly_type"].str.contains(search, case=False, na=False)
    ] if search else df

    st.caption(f"{len(filtered)} record(s) found")

    display_cols = ["id", "date", "time", "anomaly_type", "confidence", "screenshot_path"]
    st.dataframe(
        filtered[display_cols].rename(columns={
            "id":              "ID",
            "date":            "Date",
            "time":            "Time",
            "anomaly_type":    "Anomaly Type",
            "confidence":      "Confidence",
            "screenshot_path": "Screenshot Path",
        }),
        use_container_width=True,
        hide_index=True,
    )

    # CSV export
    csv = filtered.to_csv(index=False).encode("utf-8")
    st.download_button("⬇  Export as CSV", csv, "incidents.csv", "text/csv")


def render_evidence_gallery(df: pd.DataFrame) -> None:
    """Render a grid gallery of all saved evidence screenshots."""
    st.markdown('<p class="section-title">Evidence Gallery</p>', unsafe_allow_html=True)

    # Collect valid image paths from the screenshots folder
    images = sorted(
        [f for f in os.listdir(SCREENSHOT_DIR) if f.lower().endswith(".png")],
        reverse=True,
    ) if os.path.isdir(SCREENSHOT_DIR) else []

    if not images:
        st.info("No screenshots found in the screenshots folder.")
        return

    st.caption(f"{len(images)} evidence image(s) stored")

    # 3-column responsive grid
    cols = st.columns(3)
    for idx, fname in enumerate(images):
        path = os.path.join(SCREENSHOT_DIR, fname)
        try:
            img = Image.open(path)
            cols[idx % 3].image(img, caption=fname, use_container_width=True)
        except Exception:
            cols[idx % 3].warning(f"Could not load {fname}")

# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

def render_sidebar() -> str:
    """Render the sidebar and return the selected page name."""
    with st.sidebar:
        st.markdown("## 🛡️ WatchGuard AI")
        st.markdown("---")
        st.markdown("**Navigation**")

        # Session-state driven navigation
        if "page" not in st.session_state:
            st.session_state.page = "Dashboard"

        for label, icon in [
            ("Dashboard",        "📊"),
            ("Incident History",  "📋"),
            ("Evidence Gallery",  "🖼️"),
        ]:
            if st.button(f"{icon}  {label}", key=label):
                st.session_state.page = label

        st.markdown("---")
        st.caption("Phase 5 · SQLite + YOLOv8")

    return st.session_state.page

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # Page header
    st.markdown(
        "## 🛡️ WatchGuard AI – Intelligent Invigilation Duty Monitoring System",
    )
    st.markdown("---")

    conn    = get_connection()
    df      = load_incidents(conn)
    metrics = compute_metrics(df)
    page    = render_sidebar()

    if page == "Dashboard":
        render_dashboard(df, metrics)
    elif page == "Incident History":
        render_incident_history(df)
    elif page == "Evidence Gallery":
        render_evidence_gallery(df)


if __name__ == "__main__":
    main()
