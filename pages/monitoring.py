"""
pages/monitoring.py – WatchGuard AI
During-exam AI monitoring page.
Launches detect.py as a subprocess so the Streamlit UI stays responsive.
detect.py is never modified.
"""

import os
import sqlite3
import subprocess
import sys

import streamlit as st

DETECT_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "detect.py",
)


def _is_running() -> bool:
    """Check if the monitored subprocess is still alive.
    Uses Popen.poll() stored in session_state — works on all platforms.
    """
    proc: subprocess.Popen = st.session_state.get("monitoring_proc")
    if proc is None:
        return False
    return proc.poll() is None   # None means still running


def render(conn: sqlite3.Connection) -> None:
    running = _is_running()

    # If process died on its own, clean up
    if not running and st.session_state.get("monitoring_proc") is not None:
        st.session_state.monitoring_proc = None
        st.session_state.monitoring_pid  = None

    status_color = "#22c55e" if running else "#94a3b8"
    status_text  = "● RUNNING" if running else "● IDLE"

    st.markdown(f"""
    <div style="background:#f0f7ff;border:1.5px solid #3b82f6;border-radius:12px;
                padding:20px 24px;margin-bottom:20px;display:flex;
                justify-content:space-between;align-items:center">
        <div>
            <div style="font-size:1.1rem;font-weight:700;color:#1e3a5f">
                WatchGuard AI Detection Engine
            </div>
            <div style="color:#64748b;font-size:.88rem;margin-top:4px">
                YOLOv8n · Confidence ≥ 0.55 · 2s confirmation · 5s cooldown
            </div>
        </div>
        <div style="font-weight:700;color:{status_color};font-size:1rem">
            {status_text}
        </div>
    </div>""", unsafe_allow_html=True)

    col_start, col_stop, _ = st.columns([1.5, 1.5, 5])

    if col_start.button("▶  Start AI Monitoring", type="primary",
                        disabled=running):
        if not os.path.exists(DETECT_SCRIPT):
            st.error(f"detect.py not found at: {DETECT_SCRIPT}")
        else:
            proc = subprocess.Popen(
                [sys.executable, DETECT_SCRIPT],
                creationflags=(
                    subprocess.CREATE_NEW_CONSOLE
                    if sys.platform == "win32" else 0
                ),
            )
            st.session_state.monitoring_proc = proc
            st.session_state.monitoring_pid  = proc.pid
            st.success(
                f"✅ AI Monitoring started (PID {proc.pid}). "
                "A webcam window titled 'WatchGuard AI' will open. "
                "Press Q in that window to stop."
            )
            st.rerun()

    if col_stop.button("⏹  Stop Monitoring", disabled=not running):
        proc: subprocess.Popen = st.session_state.get("monitoring_proc")
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        st.session_state.monitoring_proc = None
        st.session_state.monitoring_pid  = None
        st.info("Monitoring stopped.")
        st.rerun()

    # ── Live incident counter ────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("**📊 Live Incident Summary**")

    import datetime
    total     = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
    today_str = datetime.date.today().isoformat()
    today     = conn.execute(
        "SELECT COUNT(*) FROM incidents WHERE date = ?", (today_str,)
    ).fetchone()[0]

    c1, c2 = st.columns(2)
    c1.metric("Total Incidents (All Time)", total)
    c2.metric("Today's Incidents", today)

    rows = conn.execute(
        "SELECT date, time, anomaly_type, confidence FROM incidents "
        "ORDER BY id DESC LIMIT 5"
    ).fetchall()
    if rows:
        import pandas as pd
        df = pd.DataFrame(rows, columns=["Date", "Time", "Type", "Confidence"])
        df["Confidence"] = df["Confidence"].apply(lambda x: f"{x:.0%}")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No incidents recorded yet. Start monitoring to begin detection.")

    if running:
        st.markdown("""
        <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:8px;
                    padding:10px 14px;font-size:.85rem;color:#166534;margin-top:12px">
            💡 <strong>Tip:</strong> Keep this browser tab open while monitoring runs.
            Refresh the page to see new incidents appear in the table above.
        </div>""", unsafe_allow_html=True)
