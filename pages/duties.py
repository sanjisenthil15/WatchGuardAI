"""
pages/duties.py – WatchGuard AI
Smart Duty Allocation:
  - Checks availability, time conflicts, and weekly workload cap.
  - Detects absent/unavailable assigned faculty and recommends replacements.
  - One-click accept for recommendations.
"""

import sqlite3
from datetime import date, timedelta

import streamlit as st

import db


# ── Allocation engine ────────────────────────────────────────────────────────

def _week_bounds(ref_date: str) -> tuple:
    d      = date.fromisoformat(ref_date)
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    return monday.isoformat(), sunday.isoformat()


def _get_assigned_faculty_ids(conn: sqlite3.Connection, exam_id: int) -> list:
    """Return faculty_id list for active (non-replaced) duties on this exam."""
    rows = conn.execute(
        "SELECT faculty_id FROM duties WHERE exam_id = ? AND status != 'replaced'",
        (exam_id,),
    ).fetchall()
    return [r[0] for r in rows]


def _eligible_faculty(conn: sqlite3.Connection,
                      exam: sqlite3.Row,
                      exclude_ids: list) -> list:
    """Return available faculty with no conflict and under their weekly cap."""
    week_start, week_end = _week_bounds(exam["date"])
    candidates = []
    for f in db.get_available_faculty(conn):
        fid = f["id"]
        if fid in exclude_ids:
            continue
        if db.faculty_has_conflict(conn, fid, exam["date"],
                                   exam["start_time"], exam["end_time"]):
            continue
        weekly = db.get_weekly_duty_count(conn, fid, week_start, week_end)
        if weekly >= f["max_duties_per_week"]:
            continue
        candidates.append({"row": f, "weekly_duties": weekly})
    candidates.sort(key=lambda x: x["weekly_duties"])
    return candidates


def _auto_allocate(conn: sqlite3.Connection, exam: sqlite3.Row) -> list:
    """Fill all required invigilator slots for an exam."""
    messages     = []
    assigned_ids = _get_assigned_faculty_ids(conn, exam["id"])
    slots_needed = exam["invigilator_count"] - len(assigned_ids)

    if slots_needed <= 0:
        return ["All slots already filled."]

    eligible = _eligible_faculty(conn, exam, assigned_ids)
    for i in range(min(slots_needed, len(eligible))):
        f = eligible[i]["row"]
        db.assign_duty(conn, exam["id"], f["id"])
        messages.append(f"✅ Assigned **{f['name']}** ({f['department']})")

    shortfall = slots_needed - len(eligible)
    if shortfall > 0:
        messages.append(
            f"⚠️ Could not fill **{shortfall}** slot(s) — "
            "no eligible faculty available."
        )
    return messages


# ── Page renderer ────────────────────────────────────────────────────────────

def render(conn: sqlite3.Connection) -> None:
    exams = db.get_all_exams(conn)
    if not exams:
        st.warning("No exams scheduled. Add exams first.")
        return

    for exam in exams:
        eid    = exam["id"]
        duties = db.get_duties_for_exam(conn, eid)
        filled = sum(1 for d in duties if d["status"] in ("assigned", "replaced"))
        needed = exam["invigilator_count"]

        status_color = "#22c55e" if filled >= needed else "#f59e0b"
        status_text  = "Fully Staffed" if filled >= needed else f"{filled}/{needed} Assigned"

        st.markdown(f"""
        <div style="background:#f0f7ff;border:1.5px solid #3b82f6;border-radius:12px;
                    padding:14px 18px;margin-bottom:6px">
            <div style="display:flex;justify-content:space-between;align-items:center">
                <div>
                    <span style="font-weight:700;color:#1e3a5f;font-size:1rem">
                        📝 {exam['subject']}
                    </span>
                    &nbsp;·&nbsp;
                    <span style="color:#64748b;font-size:.88rem">
                        {exam['date']}  {exam['start_time']}–{exam['end_time']}
                        &nbsp;|&nbsp; 📍 {exam['venue']}
                    </span>
                </div>
                <span style="color:{status_color};font-weight:600;font-size:.88rem">
                    ● {status_text}
                </span>
            </div>
        </div>""", unsafe_allow_html=True)

        col_alloc, col_clear, _ = st.columns([2, 2, 4])
        if col_alloc.button("⚡ Auto-Allocate", key=f"alloc_{eid}"):
            msgs = _auto_allocate(conn, exam)
            for m in msgs:
                st.markdown(m)
            st.rerun()

        if col_clear.button("🗑 Clear Duties", key=f"clear_{eid}"):
            conn.execute("DELETE FROM duties WHERE exam_id = ?", (eid,))
            conn.commit()
            st.rerun()

        # Refresh duties after possible allocation
        duties = db.get_duties_for_exam(conn, eid)
        if not duties:
            st.caption("  No duties assigned yet.")
        else:
            for duty in duties:
                did    = duty["id"]
                status = duty["status"]

                if status == "replaced":
                    st.markdown(
                        f"&nbsp;&nbsp;👤 ~~{duty['faculty_name']}~~ → "
                        f"**{duty['replaced_by_name']}** — "
                        f"<span style='color:#3b82f6'>Replaced</span> "
                        f"<span style='color:#94a3b8;font-size:.8rem'>"
                        f"({duty['reason']})</span>",
                        unsafe_allow_html=True,
                    )
                    continue

                # Check if assigned faculty is now absent
                fac_row = conn.execute(
                    "SELECT is_available FROM faculty WHERE id = "
                    "(SELECT faculty_id FROM duties WHERE id = ?)", (did,)
                ).fetchone()
                is_absent = fac_row is not None and not bool(fac_row[0])

                if is_absent:
                    current_fac_id = conn.execute(
                        "SELECT faculty_id FROM duties WHERE id = ?", (did,)
                    ).fetchone()[0]
                    replacements = _eligible_faculty(
                        conn, exam, exclude_ids=[current_fac_id]
                    )
                    st.markdown(f"""
                    <div style="background:#fff7ed;border:1.5px solid #f59e0b;
                                border-radius:10px;padding:12px 16px;margin:6px 0">
                        <div style="color:#92400e;font-weight:600">
                            ⚠️ {duty['faculty_name']} is marked absent
                        </div>
                    </div>""", unsafe_allow_html=True)

                    if replacements:
                        rec = replacements[0]["row"]
                        st.markdown(
                            f"Recommended replacement: **{rec['name']}** "
                            f"({rec['department']}) — "
                            f"{replacements[0]['weekly_duties']} duties this week."
                        )
                        if st.button(f"✅ Accept: Assign {rec['name']}",
                                     key=f"accept_{did}"):
                            db.accept_replacement(
                                conn, did, rec["id"],
                                f"Original faculty absent. Auto-replaced with {rec['name']}.",
                            )
                            db.assign_duty(conn, eid, rec["id"])
                            st.success(f"Replacement accepted: {rec['name']}")
                            st.rerun()
                    else:
                        st.warning("No eligible replacement found.")
                else:
                    st.markdown(
                        f"&nbsp;&nbsp;👤 **{duty['faculty_name']}** "
                        f"({duty['department']}) — "
                        f"<span style='color:#22c55e'>Assigned</span>",
                        unsafe_allow_html=True,
                    )

        st.markdown("---")
