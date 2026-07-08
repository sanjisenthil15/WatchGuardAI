"""
pages/exams.py – WatchGuard AI
Exam management: schedule, edit, view, and delete exams.

ROOT CAUSE FIX:
  st.form_submit_button() returns True only during the single render pass in
  which the button is clicked.  That value is only reliable INSIDE the same
  `with st.form(...)` block.  Any `if submitted:` placed outside the form
  block runs on the NEXT render pass where submitted is already False, so the
  DB insert / update never executes.  Both the add form and the edit form now
  have all validation and DB calls inside their respective form blocks.
"""

import datetime
import sqlite3

import streamlit as st

import db


def render(conn: sqlite3.Connection) -> None:

    # ── Success banner (persisted across rerun via session_state) ───────────
    if "exam_success" in st.session_state:
        st.success(st.session_state.pop("exam_success"))

    # ── Add exam form ───────────────────────────────────────────────────────
    with st.expander("➕  Schedule New Exam", expanded=False):
        with st.form("add_exam_form"):
            c1, c2 = st.columns(2)
            subject    = c1.text_input("Subject")
            venue      = c2.text_input("Venue")
            exam_date  = c1.date_input("Exam Date")
            start_time = c1.time_input("Start Time")
            end_time   = c2.time_input("End Time")
            inv_count  = c2.number_input(
                "Required Invigilators", min_value=1, max_value=10, value=2
            )
            submitted = st.form_submit_button(
                "📅 Schedule Exam", type="primary", use_container_width=True
            )
            # ── INSIDE the form block ──────────────────────────────────────
            if submitted:
                if not subject.strip():
                    st.error("Subject is required.")
                elif not venue.strip():
                    st.error("Venue is required.")
                elif end_time <= start_time:
                    st.error("End time must be after start time.")
                else:
                    try:
                        db.add_exam(
                            conn,
                            subject.strip(),
                            exam_date.isoformat(),
                            start_time.strftime("%H:%M"),
                            end_time.strftime("%H:%M"),
                            venue.strip(),
                            int(inv_count),
                        )
                        st.session_state["exam_success"] = (
                            f"✅ '{subject.strip()}' scheduled on {exam_date}."
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to save exam: {e}")

    # ── Exam list ───────────────────────────────────────────────────────────
    exams = db.get_all_exams(conn)
    if not exams:
        st.info("No exams scheduled yet.")
        return

    st.markdown(f"**{len(exams)} exam(s) scheduled**")

    editing_id = st.session_state.get("editing_exam_id")

    for exam in exams:
        eid = exam["id"]

        st.markdown(f"""
        <div style="background:#f0f7ff;border:1px solid #bfdbfe;border-radius:10px;
                    padding:12px 16px;margin-bottom:4px">
            <div style="font-weight:700;color:#1e3a5f;font-size:1rem">
                📝 {exam['subject']}
            </div>
            <div style="color:#64748b;font-size:.88rem;margin-top:4px">
                📅 {exam['date']} &nbsp;|&nbsp;
                🕐 {exam['start_time']} – {exam['end_time']} &nbsp;|&nbsp;
                📍 {exam['venue']} &nbsp;|&nbsp;
                👥 {exam['invigilator_count']} invigilator(s) required
            </div>
        </div>""", unsafe_allow_html=True)

        col_edit, col_del, _ = st.columns([1, 1, 6])

        if col_edit.button("✏️ Edit", key=f"edit_exam_{eid}"):
            st.session_state.editing_exam_id = eid
            st.rerun()

        if col_del.button("🗑 Delete", key=f"del_exam_{eid}"):
            db.delete_exam(conn, eid)
            if editing_id == eid:
                st.session_state.editing_exam_id = None
            st.rerun()

        # ── Inline edit form ────────────────────────────────────────────────
        if editing_id == eid:
            with st.form(f"edit_exam_form_{eid}"):
                st.markdown("**Edit Exam Details**")
                ec1, ec2 = st.columns(2)
                new_subject = ec1.text_input("Subject", value=exam["subject"])
                new_venue   = ec2.text_input("Venue",   value=exam["venue"])
                new_date    = ec1.date_input(
                    "Exam Date",
                    value=datetime.date.fromisoformat(exam["date"]),
                )
                new_start = ec1.time_input(
                    "Start Time",
                    value=datetime.time.fromisoformat(exam["start_time"]),
                )
                new_end = ec2.time_input(
                    "End Time",
                    value=datetime.time.fromisoformat(exam["end_time"]),
                )
                new_inv = ec2.number_input(
                    "Required Invigilators",
                    min_value=1, max_value=10,
                    value=int(exam["invigilator_count"]),
                )
                save_col, cancel_col = st.columns([1, 1])
                do_save   = save_col.form_submit_button("💾 Save", type="primary")
                do_cancel = cancel_col.form_submit_button("Cancel")

                # ── INSIDE the form block ──────────────────────────────────
                if do_save:
                    if not new_subject.strip():
                        st.error("Subject is required.")
                    elif not new_venue.strip():
                        st.error("Venue is required.")
                    elif new_end <= new_start:
                        st.error("End time must be after start time.")
                    else:
                        try:
                            db.update_exam(
                                conn, eid,
                                new_subject.strip(),
                                new_date.isoformat(),
                                new_start.strftime("%H:%M"),
                                new_end.strftime("%H:%M"),
                                new_venue.strip(),
                                int(new_inv),
                            )
                            st.session_state.editing_exam_id = None
                            st.session_state["exam_success"] = "✅ Exam updated."
                            st.rerun()
                        except Exception as e:
                            st.error(f"Update failed: {e}")

                if do_cancel:
                    st.session_state.editing_exam_id = None
                    st.rerun()
