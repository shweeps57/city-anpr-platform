import uuid
from datetime import datetime, timezone
from database.connection import get_db_connection, get_redis


def check_blacklist(plate_number: str) -> dict | None:
    """
    Check if a plate is on the blacklist.
    Returns the blacklist entry if found, None otherwise.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM blacklist WHERE plate_number = %s",
                (plate_number.upper(),)
            )
            row = cur.fetchone()

    if row:
        return {
            "plate_number": row["plate_number"],
            "reason": row["reason"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }
    return None


def get_all_blacklist() -> list[dict]:
    """Get all blacklisted plates."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM blacklist ORDER BY created_at DESC")
            rows = cur.fetchall()

    return [
        {
            "plate_number": r["plate_number"],
            "reason": r["reason"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


def add_to_blacklist(plate_number: str, reason: str | None = None) -> dict:
    """Add a plate to the blacklist."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO blacklist (plate_number, reason)
                VALUES (%s, %s)
                ON CONFLICT (plate_number) DO UPDATE
                    SET reason = EXCLUDED.reason
                RETURNING *
            """, (plate_number.upper(), reason))
            row = cur.fetchone()
            conn.commit()

    return {
        "plate_number": row["plate_number"],
        "reason": row["reason"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


def remove_from_blacklist(plate_number: str) -> bool:
    """Remove a plate from the blacklist. Returns True if deleted."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM blacklist WHERE plate_number = %s",
                (plate_number.upper(),)
            )
            deleted = cur.rowcount > 0
            conn.commit()
    return deleted


def create_alert(plate_number: str, alert_type: str,
                 message: str | None = None,
                 camera_id: str | None = None) -> dict:
    """Create a new alert and return it."""
    alert_id = uuid.uuid4()

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO alerts (alert_id, plate_number, alert_type,
                                   message, camera_id)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *
            """, (str(alert_id), plate_number.upper(), alert_type,
                  message, camera_id))
            row = cur.fetchone()
            conn.commit()

    return {
        "alert_id": str(row["alert_id"]),
        "plate_number": row["plate_number"],
        "alert_type": row["alert_type"],
        "message": row["message"],
        "camera_id": row["camera_id"],
        "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,
    }


def get_recent_alerts(limit: int = 50) -> list[dict]:
    """Get the most recent alerts."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM alerts
                ORDER BY timestamp DESC
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()

    return [
        {
            "alert_id": str(r["alert_id"]),
            "plate_number": r["plate_number"],
            "alert_type": r["alert_type"],
            "message": r["message"],
            "camera_id": r["camera_id"],
            "timestamp": r["timestamp"].isoformat() if r["timestamp"] else None,
        }
        for r in rows
    ]
