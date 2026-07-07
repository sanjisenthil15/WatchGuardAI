"""
pages/faculty.py – WatchGuard AI
Faculty management: add, edit, toggle availability, delete.
"""

import sqlite3

import streamlit as st

import db


def render(conn: sqlite3.Connection) -> None:
    # ── Add faculty form ────────────────────────────────────────────────────
    with st.expander("➕  Add New Faculty", expanded=False):
        with st.form("add_faculty_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name       = c1.text_input("Full Name")
            department = c2.text_input("Department")
            email      = c1.text_input("Email")
            max_duties = c2.number_input("Max Duties / Week", min_value=1,
                                         max_value=10, value=3)
            submitted = st.form_submit_button("Add Faculty", type="primary")
            if submitted:
                if not name or not department or not email:
                    st.error("Name, department and email are required.")
                else:
                    try:
                        db.add_faculty(conn, name.strip(), department.strip(),
                                       email.strip(), int(max_duties))
                        st.success(f"✅ {name} added successfully.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not add faculty: {e}")

    # ── Faculty list ────────────────────────────────────────────────────────
    rows = db.get_all_faculty(conn)
    if not rows:
        st.info("No faculty members added yet.")
        return

    st.markdown(f"**{len(rows)} faculty member(s) registered**")

    editing_id = st.session_state.get("editing_faculty_id")

    for row in rows:
        fid       = row["id"]
        available = bool(row["is_available"])
        status_tag = (
            '<span style="color:#22c55e;font-weight:600">● Available</span>'
            if available else
            '<span style="color:#ef4444;font-weight:600">● Absent</span>'
        )

        st.markdown(f"""
        <div style="background:#f0f7ff;border:1px solid #bfdbfe;border-radius:10px;
                    padding:12px 16px;margin-bottom:4px">
            <div style="display:flex;justify-content:space-between;align-items:center">
                <div>
                    <span style="font-weight:700;color:#1e3a5f;font-size:1rem">
                        {row['name']}
                    </span>
                    &nbsp;·&nbsp;
                    <span style="color:#64748b">{row['department']}</span>
                    &nbsp;·&nbsp;
                    <span style="color:#64748b;font-size:.85rem">{row['email']}</span>
                </div>
                <div>{status_tag}</div>
            </div>
            <div style="font-size:.8rem;color:#94a3b8;margin-top:4px">
                Max duties/week: {row['max_duties_per_week']}
            </div>
        </div>""", unsafe_allow_html=True)

        col_toggle, col_edit, col_del, _ = st.columns([1.2, 1, 1, 5])
        toggle_label = "Mark Absent" if available else "Mark Available"

        if col_toggle.button(toggle_label, key=f"toggle_{fid}"):
            db.update_faculty_availability(conn, fid, not available)
            st.rerun()

        if col_edit.button("✏️ Edit", key=f"edit_fac_{fid}"):
            st.session_state.editing_faculty_id = fid
            st.rerun()

        if col_del.button("🗑 Delete", key=f"del_fac_{fid}"):
            db.delete_faculty(conn, fid)
            if editing_id == fid:
                st.session_state.editing_faculty_id = None
            st.rerun()

        # Inline edit form shown below the selected row
        if editing_id == fid:
            with st.form(f"edit_faculty_form_{fid}"):
                st.markdown("**Edit Faculty Details**")
                ec1, ec2 = st.columns(2)
                new_name  = ec1.text_input("Full Name",  value=row["name"])
                new_dept  = ec2.text_input("Department", value=row["department"])
                new_email = ec1.text_input("Email",      value=row["email"])
                new_max   = ec2.number_input(
                    "Max Duties / Week",
                    min_value=1, max_value=10,
                    value=int(row["max_duties_per_week"]),
                )
                save, cancel = st.columns([1, 1])
                do_save   = save.form_submit_button("💾 Save", type="primary")
                do_cancel = cancel.form_submit_button("Cancel")

                if do_save:
                    if not new_name or not new_dept or not new_email:
                        st.error("All fields are required.")
                    else:
                        try:
                            db.update_faculty(
                                conn, fid,
                                new_name.strip(), new_dept.strip(),
                                new_email.strip(), int(new_max),
                            )
                            st.session_state.editing_faculty_id = None
                            st.success("Faculty updated.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Update failed: {e}")

                if do_cancel:
                    st.session_state.editing_faculty_id = None
                    st.rerun()
