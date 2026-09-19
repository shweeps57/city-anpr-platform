"""Dashboard stats service — aggregated KPI data for the frontend."""

from database.connection import get_db_connection
from datetime import datetime, timedelta, timezone


def get_dashboard_stats() -> dict:
    """
    Return all KPI card data in a single query batch:
    - active_cameras: count of registered cameras
    - total_detections: total plate_events count
    - flagged_count: number of blacklisted plates that have been detected
    - open_alerts: count of alerts
    - avg_confidence: average OCR confidence across all events
    - recent_plates: list of the 5 most recent unique plates detected
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Active cameras
            cur.execute("SELECT COUNT(*) AS cnt FROM cameras")
            active_cameras = cur.fetchone()["cnt"]

            # Total detections
            cur.execute("SELECT COUNT(*) AS cnt FROM plate_events")
            total_detections = cur.fetchone()["cnt"]

            # Flagged: blacklisted plates that have been sighted
            cur.execute("""
                SELECT COUNT(DISTINCT pe.plate_number) AS cnt
                FROM plate_events pe
                JOIN blacklist b ON pe.plate_number = b.plate_number
            """)
            flagged_count = cur.fetchone()["cnt"]

            # Open alerts
            cur.execute("SELECT COUNT(*) AS cnt FROM alerts")
            open_alerts = cur.fetchone()["cnt"]

            # Average confidence
            cur.execute("SELECT COALESCE(AVG(confidence), 0) AS avg_conf FROM plate_events")
            avg_confidence = round(cur.fetchone()["avg_conf"] * 100, 1)

            # Blacklist count
            cur.execute("SELECT COUNT(*) AS cnt FROM blacklist")
            blacklist_count = cur.fetchone()["cnt"]

            # Recent unique plates (last 5)
            cur.execute("""
                SELECT DISTINCT ON (plate_number)
                    plate_number, camera_id, timestamp, confidence
                FROM plate_events
                ORDER BY plate_number, timestamp DESC
                LIMIT 5
            """)
            recent_plates = [
                {
                    "plate_number": r["plate_number"],
                    "camera_id": r["camera_id"],
                    "timestamp": r["timestamp"].isoformat(),
                    "confidence": r["confidence"],
                }
                for r in cur.fetchall()
            ]

    return {
        "active_cameras": active_cameras,
        "total_detections": total_detections,
        "flagged_count": flagged_count,
        "blacklist_count": blacklist_count,
        "open_alerts": open_alerts,
        "avg_confidence": avg_confidence,
        "recent_plates": recent_plates,
    }
