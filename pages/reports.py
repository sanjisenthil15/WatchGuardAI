"""
pages/reports.py – WatchGuard AI
Post-exam reporting: incident history, evidence gallery, integrity report.
"""

import os
import sqlite3
from datetime import date

import pandas as pd
import streamlit as st
from PIL import Image

SCREENSHOT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "screenshots",
)

# Project root — used to resolve legacy relative paths stored in the DB
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _resolve_path(raw: str) -> str:
    """Return an absolute path for a screenshot stored in the DB.
    Handles both absolute paths (new) and relative paths (legacy).
    """
    if os.path.isabs(raw):
        return raw
    return os.path.join(_PROJECT_ROOT, raw)


def _render_incident_history(conn: sqlite3.Connection) -> None:
    st.markdown("#### 📋 Incident History")

    rows = conn.execute(
        "SELECT id, date, time, anomaly_type, confidence, screenshot_path "
        "FROM incidents ORDER BY id DESC"
    ).fetchall()

    if not rows:
        st.info("No incidents recorded yet.")
        return

    df = pd.DataFrame(
        [dict(r) for r in rows],
        columns=["id", "date", "time", "anomaly_type", "confidence", "screenshot_path"],
    )

    col_search, col_date = st.columns([3, 2])
    search    = col_search.text_input("🔍 Filter by type or date",
                                      placeholder="e.g. Mobile Phone")
    date_filt = col_date.date_input("Filter by date", value=None,
                                    key="report_date_filter")

    filtered = df.copy()
    if search:
        filtered = filtered[
            filtered["anomaly_type"].str.contains(search, case=False, na=False) |
            filtered["date"].str.contains(search, case=False, na=False)
        ]
    if date_filt:
        filtered = filtered[filtered["date"] == date_filt.isoformat()]

    st.caption(f"{len(filtered)} record(s) found")

    display = filtered.rename(columns={
        "id": "ID", "date": "Date", "time": "Time",
        "anomaly_type": "Type", "confidence": "Confidence",
        "screenshot_path": "Screenshot",
    })
    display["Confidence"] = display["Confidence"].apply(lambda x: f"{float(x):.0%}")
    display["Screenshot"]  = display["Screenshot"].apply(_resolve_path)
    st.dataframe(display, use_container_width=True, hide_index=True)

    csv = filtered.to_csv(index=False).encode("utf-8")
    st.download_button("⬇ Export CSV", csv, "incidents.csv", "text/csv")


def _render_evidence_gallery() -> None:
    st.markdown("#### 🖼️ Evidence Gallery")

    if not os.path.isdir(SCREENSHOT_DIR):
        st.info("Screenshots folder not found.")
        return

    images = sorted(
        [f for f in os.listdir(SCREENSHOT_DIR) if f.lower().endswith(".png")],
        reverse=True,
    )

    if not images:
        st.info("No screenshots saved yet.")
        return

    st.caption(f"{len(images)} evidence image(s)")
    cols = st.columns(3)
    for i, fname in enumerate(images):
        path = os.path.join(SCREENSHOT_DIR, fname)
        try:
            img = Image.open(path)
            cols[i % 3].image(img, caption=fname, use_container_width=True)
        except Exception:
            cols[i % 3].warning(f"Could not load {fname}")


def _render_integrity_report(conn: sqlite3.Connection) -> None:
    st.markdown("#### 🛡️ Exam Integrity Report")

    exams = conn.execute(
        "SELECT id, subject, date, start_time, end_time, venue FROM exams "
        "ORDER BY date, start_time"
    ).fetchall()

    if not exams:
        st.info("No exams found.")
        return

    total_incidents = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
    total_duties    = conn.execute("SELECT COUNT(*) FROM duties").fetchone()[0]

    score = max(0, min(100, round(100 - (total_incidents / max(total_duties, 1)) * 100)))
    color = "#22c55e" if score >= 80 else "#f59e0b" if score >= 50 else "#ef4444"
    label = "Excellent" if score >= 80 else "Needs Attention" if score >= 50 else "Critical"

    st.markdown(f"""
    <div style="background:#f0f7ff;border:1.5px solid #3b82f6;border-radius:12px;
                padding:18px 22px;margin-bottom:16px">
        <div style="font-size:.8rem;color:#64748b;margin-bottom:8px">
            OVERALL EXAM INTEGRITY SCORE
        </div>
        <div style="font-size:2.5rem;font-weight:800;color:{color}">{score}%</div>
        <div style="background:#e2e8f0;border-radius:999px;height:10px;margin-top:8px">
            <div style="width:{score}%;background:{color};height:10px;
                        border-radius:999px"></div>
        </div>
        <div style="font-size:.8rem;color:#64748b;margin-top:6px">
            {label} — {total_incidents} incident(s) across {total_duties} duty slot(s)
        </div>
    </div>""", unsafe_allow_html=True)

    st.markdown("**Per-Exam Breakdown**")
    rows = []
    for exam in exams:
        inc_count = conn.execute(
            "SELECT COUNT(*) FROM incidents WHERE date = ?", (exam["date"],)
        ).fetchone()[0]
        duty_count = conn.execute(
            "SELECT COUNT(*) FROM duties WHERE exam_id = ?", (exam["id"],)
        ).fetchone()[0]
        exam_score = max(0, min(100, round(
            100 - (inc_count / max(duty_count, 1)) * 100
        )))
        rows.append({
            "Subject":   exam["subject"],
            "Date":      exam["date"],
            "Time":      f"{exam['start_time']}–{exam['end_time']}",
            "Venue":     exam["venue"],
            "Duties":    duty_count,
            "Incidents": inc_count,
            "Score":     f"{exam_score}%",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇ Export Report CSV", csv,
                       "integrity_report.csv", "text/csv")


def render(conn: sqlite3.Connection) -> None:
    tab1, tab2, tab3 = st.tabs([
        "📋 Incident History",
        "🖼️ Evidence Gallery",
        "🛡️ Integrity Report",
    ])
    with tab1:
        _render_incident_history(conn)
    with tab2:
        _render_evidence_gallery()
    with tab3:
        _render_integrity_report(conn)
