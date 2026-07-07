"""
db.py – WatchGuard AI
Centralised database initialisation and shared query helpers.
All tables (existing + new) are created here so every module imports
from one place and the schema never drifts.
"""

import os
import sqlite3

# Anchor the DB file to the project folder regardless of launch directory
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watchguard.db")


def get_connection() -> sqlite3.Connection:
    """Return an open SQLite connection with row_factory set to Row
    so columns are accessible by name as well as index.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create all tables if they do not already exist.

    Existing tables (incidents) are left untouched — only new tables
    are added so the AI monitoring module keeps working unchanged.
    """
    conn.executescript("""
        -- ── Existing AI monitoring table (kept as-is) ──────────────────
        CREATE TABLE IF NOT EXISTS incidents (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            date            TEXT    NOT NULL,
            time            TEXT    NOT NULL,
            anomaly_type    TEXT    NOT NULL,
            confidence      REAL    NOT NULL,
            screenshot_path TEXT    NOT NULL
        );

        -- ── Faculty ─────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS faculty (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            name                TEXT    NOT NULL,
            department          TEXT    NOT NULL,
            email               TEXT    UNIQUE NOT NULL,
            max_duties_per_week INTEGER NOT NULL DEFAULT 3,
            is_available        INTEGER NOT NULL DEFAULT 1   -- 1=available, 0=absent
        );

        -- ── Exams ───────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS exams (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            subject             TEXT    NOT NULL,
            date                TEXT    NOT NULL,
            start_time          TEXT    NOT NULL,
            end_time            TEXT    NOT NULL,
            venue               TEXT    NOT NULL,
            invigilator_count   INTEGER NOT NULL DEFAULT 1
        );

        -- ── Duties ──────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS duties (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id         INTEGER NOT NULL REFERENCES exams(id),
            faculty_id      INTEGER NOT NULL REFERENCES faculty(id),
            status          TEXT    NOT NULL DEFAULT 'assigned',
                                    -- assigned | absent | replaced
            replaced_by     INTEGER REFERENCES faculty(id),
            reason          TEXT
        );
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# Faculty helpers
# ---------------------------------------------------------------------------

def get_all_faculty(conn: sqlite3.Connection) -> list:
    return conn.execute(
        "SELECT * FROM faculty ORDER BY name"
    ).fetchall()


def get_available_faculty(conn: sqlite3.Connection) -> list:
    return conn.execute(
        "SELECT * FROM faculty WHERE is_available = 1 ORDER BY name"
    ).fetchall()


def add_faculty(conn: sqlite3.Connection, name: str, department: str,
                email: str, max_duties: int) -> None:
    conn.execute(
        "INSERT INTO faculty (name, department, email, max_duties_per_week) "
        "VALUES (?, ?, ?, ?)",
        (name, department, email, max_duties),
    )
    conn.commit()


def update_faculty_availability(conn: sqlite3.Connection,
                                faculty_id: int, available: bool) -> None:
    conn.execute(
        "UPDATE faculty SET is_available = ? WHERE id = ?",
        (1 if available else 0, faculty_id),
    )
    conn.commit()


def update_faculty(conn: sqlite3.Connection, faculty_id: int, name: str,
                   department: str, email: str, max_duties: int) -> None:
    conn.execute(
        "UPDATE faculty SET name=?, department=?, email=?, "
        "max_duties_per_week=? WHERE id=?",
        (name, department, email, max_duties, faculty_id),
    )
    conn.commit()


def delete_faculty(conn: sqlite3.Connection, faculty_id: int) -> None:
    conn.execute("DELETE FROM faculty WHERE id = ?", (faculty_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Exam helpers
# ---------------------------------------------------------------------------

def get_all_exams(conn: sqlite3.Connection) -> list:
    return conn.execute(
        "SELECT * FROM exams ORDER BY date, start_time"
    ).fetchall()


def add_exam(conn: sqlite3.Connection, subject: str, date: str,
             start_time: str, end_time: str, venue: str,
             invigilator_count: int) -> None:
    conn.execute(
        "INSERT INTO exams (subject, date, start_time, end_time, venue, invigilator_count) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (subject, date, start_time, end_time, venue, invigilator_count),
    )
    conn.commit()


def update_exam(conn: sqlite3.Connection, exam_id: int, subject: str,
                date: str, start_time: str, end_time: str,
                venue: str, invigilator_count: int) -> None:
    conn.execute(
        "UPDATE exams SET subject=?, date=?, start_time=?, end_time=?, "
        "venue=?, invigilator_count=? WHERE id=?",
        (subject, date, start_time, end_time, venue, invigilator_count, exam_id),
    )
    conn.commit()


def delete_exam(conn: sqlite3.Connection, exam_id: int) -> None:
    conn.execute("DELETE FROM duties WHERE exam_id = ?", (exam_id,))
    conn.execute("DELETE FROM exams WHERE id = ?", (exam_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Duty helpers
# ---------------------------------------------------------------------------

def get_duties_for_exam(conn: sqlite3.Connection, exam_id: int) -> list:
    return conn.execute("""
        SELECT d.id, d.status, d.reason,
               f.name  AS faculty_name,  f.department,
               r.name  AS replaced_by_name
        FROM   duties d
        JOIN   faculty f ON f.id = d.faculty_id
        LEFT JOIN faculty r ON r.id = d.replaced_by
        WHERE  d.exam_id = ?
    """, (exam_id,)).fetchall()


def get_all_duties(conn: sqlite3.Connection) -> list:
    return conn.execute("""
        SELECT d.id, e.subject, e.date, e.start_time, e.end_time, e.venue,
               f.name AS faculty_name, f.department,
               d.status, d.reason,
               r.name AS replaced_by_name
        FROM   duties d
        JOIN   exams   e ON e.id = d.exam_id
        JOIN   faculty f ON f.id = d.faculty_id
        LEFT JOIN faculty r ON r.id = d.replaced_by
        ORDER  BY e.date, e.start_time
    """).fetchall()


def assign_duty(conn: sqlite3.Connection, exam_id: int,
                faculty_id: int) -> None:
    conn.execute(
        "INSERT INTO duties (exam_id, faculty_id, status) VALUES (?, ?, 'assigned')",
        (exam_id, faculty_id),
    )
    conn.commit()


def accept_replacement(conn: sqlite3.Connection, duty_id: int,
                       replacement_id: int, reason: str) -> None:
    """Mark original duty as replaced and record who replaced and why."""
    conn.execute(
        "UPDATE duties SET status='replaced', replaced_by=?, reason=? WHERE id=?",
        (replacement_id, reason, duty_id),
    )
    conn.commit()


def get_weekly_duty_count(conn: sqlite3.Connection,
                          faculty_id: int, week_start: str, week_end: str) -> int:
    """Count how many duties a faculty member has in a given ISO week."""
    row = conn.execute("""
        SELECT COUNT(*) FROM duties d
        JOIN   exams e ON e.id = d.exam_id
        WHERE  d.faculty_id = ?
          AND  e.date BETWEEN ? AND ?
          AND  d.status != 'replaced'
    """, (faculty_id, week_start, week_end)).fetchone()
    return row[0] if row else 0


def faculty_has_conflict(conn: sqlite3.Connection, faculty_id: int,
                         exam_date: str, start_time: str,
                         end_time: str) -> bool:
    """Return True if the faculty already has a duty that overlaps this slot."""
    row = conn.execute("""
        SELECT COUNT(*) FROM duties d
        JOIN   exams e ON e.id = d.exam_id
        WHERE  d.faculty_id = ?
          AND  e.date = ?
          AND  d.status != 'replaced'
          AND  NOT (e.end_time <= ? OR e.start_time >= ?)
    """, (faculty_id, exam_date, start_time, end_time)).fetchone()
    return (row[0] > 0) if row else False


# ---------------------------------------------------------------------------
# Dashboard summary helpers
# ---------------------------------------------------------------------------

def get_summary(conn: sqlite3.Connection) -> dict:
    """Return counts used by the dashboard cards."""
    return {
        "faculty":   conn.execute("SELECT COUNT(*) FROM faculty").fetchone()[0],
        "exams":     conn.execute("SELECT COUNT(*) FROM exams").fetchone()[0],
        "duties":    conn.execute("SELECT COUNT(*) FROM duties").fetchone()[0],
        "incidents": conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0],
    }
