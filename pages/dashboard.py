"""
pages/dashboard.py – WatchGuard AI
Unified dashboard: faculty, exams, duties, AI incidents, integrity score.
"""

import sqlite3
from datetime import date

import pandas as pd
import streamlit as st

import db


def _integrity_score(incidents: int, duties: int) -> int:
    """Simple integrity score: 100 minus 5 points per incident per duty slot.
    Floors at 0, ceilings at 100.
    """
    if duties == 0:
        return 100
    penalty = (incidents / max(duties, 1)) * 100
    return max(0, min(100, round(100 - penalty)))


def _score_color(score: int) -> str:
    if score >= 80:
        return "#22c55e"   # green
    if score >= 50:
        return "#f59e0b"   # amber
    return "#ef4444"       # red


def render(conn: sqlite3.Connection) -> None:
    st.markdown("### 📊 Dashboard")
    st.caption("Live overview of the complete examination lifecycle.")

    summary = db.get_summary(conn)
    score   = _integrity_score(summary["incidents"], summary["duties"])
    color   = _score_color(score)

    # ── Top metric cards ────────────────────────────────────────────────────
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    cards = [
        (c1, "👨‍🏫", "Faculty",      summary["faculty"],   False),
        (c2, "📝", "Exams",        summary["exams"],     False),
        (c3, "📋", "Duties",       summary["duties"],    False),
        (c4, "🚨", "AI Incidents", summary["incidents"], summary["incidents"] > 0),
        (c5, "🟢", "Monitoring",   "Active" if st.session_state.get("monitoring_pid") else "Idle", False),
        (c6, "🛡️", "Integrity",    f"{score}%",          score < 80),
    ]
    for col, icon, label, value, alert in cards:
        border = "#ef4444" if alert else "#3b82f6"
        col.markdown(f"""
        <div style="background:#f0f7ff;border:1.5px solid {border};border-radius:12px;
                    padding:16px 10px;text-align:center;">
            <div style="font-size:1.6rem">{icon}</div>
            <div style="font-size:0.72rem;color:#64748b;text-transform:uppercase;
                        letter-spacing:.07em;margin:4px 0 2px">{label}</div>
            <div style="font-size:1.5rem;font-weight:700;color:#1e3a5f">{value}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Integrity score bar ─────────────────────────────────────────────────
    st.markdown(f"""
    <div style="background:#f0f7ff;border:1.5px solid #3b82f6;border-radius:12px;
                padding:16px 20px;margin-bottom:16px">
        <div style="font-size:.8rem;color:#64748b;margin-bottom:6px">
            EXAM INTEGRITY SCORE
        </div>
        <div style="background:#e2e8f0;border-radius:999px;height:14px">
            <div style="width:{score}%;background:{color};height:14px;
                        border-radius:999px;transition:width .4s"></div>
        </div>
        <div style="font-size:.8rem;color:{color};margin-top:4px;font-weight:600">
            {score}% — {'Excellent' if score>=80 else 'Needs Attention' if score>=50 else 'Critical'}
        </div>
    </div>""", unsafe_allow_html=True)

    # ── Recent activity columns ─────────────────────────────────────────────
    left, right = st.columns(2)

    with left:
        st.markdown("**🕐 Recent AI Incidents**")
        rows = conn.execute(
            "SELECT date, time, anomaly_type, confidence FROM incidents "
            "ORDER BY id DESC LIMIT 5"
        ).fetchall()
        if rows:
            df = pd.DataFrame(rows, columns=["Date", "Time", "Type", "Conf"])
            df["Conf"] = df["Conf"].apply(lambda x: f"{x:.0%}")
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No incidents recorded yet.")

    with right:
        st.markdown("**📅 Upcoming Exams**")
        today = date.today().isoformat()
        rows = conn.execute(
            "SELECT subject, date, start_time, venue FROM exams "
            "WHERE date >= ? ORDER BY date, start_time LIMIT 5",
            (today,)
        ).fetchall()
        if rows:
            df = pd.DataFrame(rows, columns=["Subject", "Date", "Time", "Venue"])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No upcoming exams scheduled.")
