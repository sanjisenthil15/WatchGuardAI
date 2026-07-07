"""
WatchGuard AI – Intelligent Invigilation Duty Anomaly Detection System
Stable build: YOLOv8 phone detection, alert banner, screenshots, SQLite logging.
"""

import os
import sqlite3
import sys
import time
from datetime import datetime

import cv2
from ultralytics import YOLO


def load_model(weights: str = "yolov8n.pt") -> YOLO:
    """Load YOLOv8 model. Downloads weights automatically on first run."""
    return YOLO(weights)


def open_webcam(index: int = 0) -> cv2.VideoCapture:
    """Open the default webcam and raise if unavailable."""
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        raise RuntimeError(
            f"Cannot access webcam (index={index}). "
            "Ensure it is connected and not in use by another application."
        )
    return cap


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TARGET_CLASS        = "cell phone"  # COCO class name used by YOLOv8
BOX_COLOR           = (0, 0, 255)   # Red in BGR
TEXT_COLOR          = (255, 255, 255)  # White
# Absolute path anchored to the directory containing this script.
# Prevents the "wrong folder" bug when detect.py is launched from a
# different working directory (e.g. python s:\path\detect.py from C:\).
SCREENSHOT_DIR      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
SCREENSHOT_COOLDOWN = 5                # Seconds between consecutive saves
CONF_THRESHOLD      = 0.55             # Minimum confidence for yolov8n real-world detections
CONFIRM_SECONDS     = 2.0              # Phone must be visible this long before alerting
DB_PATH             = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watchguard.db")


def ensure_screenshot_dir() -> None:
    """Create the screenshots folder if it does not already exist.

    Called at startup AND inside save_screenshot so a mid-run deletion
    of the folder does not cause silent write failures.
    """
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def init_db() -> sqlite3.Connection:
    """Open (or create) watchguard.db and ensure the incidents table exists.

    Returns an open connection; the caller is responsible for closing it.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            date            TEXT    NOT NULL,
            time            TEXT    NOT NULL,
            anomaly_type    TEXT    NOT NULL,
            confidence      REAL    NOT NULL,
            screenshot_path TEXT    NOT NULL
        )
    """)
    conn.commit()
    print(f"[DB] Database ready → {DB_PATH}")
    return conn


def log_incident(conn: sqlite3.Connection, anomaly_type: str,
                 confidence: float, screenshot_path: str) -> None:
    """Insert one incident record into the incidents table."""
    now = datetime.now()
    conn.execute(
        "INSERT INTO incidents (date, time, anomaly_type, confidence, screenshot_path) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S"),
            anomaly_type,
            round(confidence, 4),
            screenshot_path,
        ),
    )
    conn.commit()
    print(f"[DB] Incident logged → type={anomaly_type}  conf={confidence:.2f}  path={screenshot_path}")


# ---------------------------------------------------------------------------
# Frame annotation helpers
# ---------------------------------------------------------------------------

def draw_alert_banner(frame, timestamp: str, evidence_saved: bool) -> None:
    """Render a red alert banner at the top of the frame.

    Shows the alert title, description, current timestamp, and optionally
    an 'Evidence Saved' confirmation when a screenshot was just taken.
    """
    banner_height = 70
    # Semi-transparent red overlay across the full width
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (frame.shape[1], banner_height), BOX_COLOR, -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

    # Line 1 – alert title
    cv2.putText(frame, "\u26a0  ALERT  |  Unauthorized Mobile Phone Detected",
                (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, TEXT_COLOR, 2, cv2.LINE_AA)

    # Line 2 – timestamp and optional evidence confirmation
    status = "  |  Evidence Saved" if evidence_saved else ""
    cv2.putText(frame, timestamp + status,
                (10, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.55, TEXT_COLOR, 1, cv2.LINE_AA)


def save_screenshot(frame) -> str:
    """Save the current frame as a PNG inside the screenshots folder.

    - Re-creates the screenshots folder if it was deleted mid-run.
    - Uses microseconds in the filename to guarantee uniqueness.
    - Checks cv2.imwrite() return value and logs success or failure.
    Returns the saved file path (even on failure, so the caller can log it).
    """
    # Guard: re-create folder in case it was deleted after startup
    ensure_screenshot_dir()

    # Microsecond precision prevents filename collisions within the same second
    filename = datetime.now().strftime("evidence_%Y%m%d_%H%M%S_%f.png")
    path     = os.path.join(SCREENSHOT_DIR, filename)

    print(f"[SCREENSHOT] Attempting to save → {path}")

    ok = cv2.imwrite(path, frame)
    if ok:
        print(f"[SCREENSHOT] ✓ Saved successfully → {path}")
    else:
        print(f"[SCREENSHOT] ✗ FAILED to save → {path}  "
              f"(check folder permissions and available disk space)")

    # Return the absolute path so the DB always stores a portable,
    # location-independent reference that the portal can resolve from any cwd.
    return os.path.abspath(path)


def annotate_frame(frame, results,
                   conf_threshold: float = CONF_THRESHOLD) -> tuple[bool, float]:
    """Draw red bounding boxes for detected cell phones only.

    Skips any detection whose confidence is below conf_threshold.
    Returns (detected: bool, best_conf: float) so the caller can log the score.
    """
    detected  = False
    best_conf = 0.0

    for box in results[0].boxes:
        label = results[0].names[int(box.cls[0])]
        conf  = float(box.conf[0])

        # Skip non-phone classes and low-confidence detections
        if label != TARGET_CLASS or conf < conf_threshold:
            continue

        detected  = True
        best_conf = max(best_conf, conf)
        x1, y1, x2, y2 = map(int, box.xyxy[0])

        # Red bounding box around the phone
        cv2.rectangle(frame, (x1, y1), (x2, y2), BOX_COLOR, 2)

        # Alert text with confidence score
        text = f"\u26a0 Mobile Phone Detected  {conf:.2f}"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)

        # Filled red background behind the label for contrast
        cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw, y1), BOX_COLOR, -1)
        cv2.putText(frame, text, (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, TEXT_COLOR, 2, cv2.LINE_AA)

    return detected, best_conf


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run() -> None:
    """Main detection loop."""
    ensure_screenshot_dir()
    conn  = init_db()
    model = load_model()

    try:
        cap = open_webcam()
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        conn.close()
        sys.exit(1)

    print("[INFO] WatchGuard AI started. Press 'Q' to quit.")

    last_saved       = 0.0   # Epoch time of the last saved screenshot
    evidence_saved   = False  # Controls the 'Evidence Saved' label visibility
    evidence_until   = 0.0    # Show the label until this epoch time
    phone_first_seen = None   # Epoch time when the current detection streak began

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[WARNING] Failed to grab frame. Retrying...")
                continue

            now       = time.time()
            timestamp = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")

            # Run YOLOv8 inference (verbose=False suppresses per-frame console logs)
            results = model(frame, verbose=False)

            # Annotate phone bounding boxes; returns (detected, best_conf)
            phone_detected, best_conf = annotate_frame(frame, results)

            if phone_detected:
                print(f"[DETECTION] Phone detected  conf={best_conf:.2f}")

                # Start the continuous-presence timer on the first frame of a new streak
                if phone_first_seen is None:
                    phone_first_seen = now
                    print(f"[DETECTION] Confirmation timer started — "
                          f"alert triggers in {CONFIRM_SECONDS}s")

                time_visible = now - phone_first_seen

                # Only alert once the phone has been visible for CONFIRM_SECONDS
                if time_visible >= CONFIRM_SECONDS:
                    cooldown_remaining = SCREENSHOT_COOLDOWN - (now - last_saved)
                    if cooldown_remaining <= 0:
                        # Save screenshot and log the incident to the database
                        path           = save_screenshot(frame)
                        log_incident(conn, "Unauthorized Mobile Phone", best_conf, path)
                        last_saved     = now
                        evidence_until = now + 3   # Show 'Evidence Saved' for 3 s
                    else:
                        print(f"[COOLDOWN] Screenshot blocked — "
                              f"{cooldown_remaining:.1f}s remaining")

                    # Evaluate evidence_saved on every frame so it clears after 3 s
                    evidence_saved = now < evidence_until
                    draw_alert_banner(frame, timestamp, evidence_saved)
                else:
                    print(f"[DETECTION] Confirming... "
                          f"{time_visible:.1f}s / {CONFIRM_SECONDS}s")
            else:
                # Phone gone – reset the streak timer to avoid carry-over
                if phone_first_seen is not None:
                    print("[DETECTION] Phone lost — confirmation timer reset")
                phone_first_seen = None
                evidence_saved   = False  # Clear banner when phone leaves frame

            cv2.imshow("WatchGuard AI", frame)

            # Exit on 'Q' or 'q'
            if cv2.waitKey(1) & 0xFF == ord("q"):
                print("[INFO] Exit requested by user.")
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        conn.close()
        print("[DB] Connection closed.")


if __name__ == "__main__":
    run()
