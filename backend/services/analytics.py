from database.connection import get_db_connection
from datetime import datetime, timedelta, timezone


def get_traffic_density(camera_id: str | None = None,
                        hours: int = 24,
                        bucket_minutes: int = 60) -> list[dict]:
    """
    Traffic density: count of plate_events per camera per time bucket.
    Groups events into time buckets and returns counts.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT
                    pe.camera_id,
                    c.name AS camera_name,
                    date_trunc('hour', pe.timestamp) +
                        (EXTRACT(minute FROM pe.timestamp)::int / %s) *
                        INTERVAL '1 minute' * %s AS time_bucket,
                    COUNT(*) AS vehicle_count
                FROM plate_events pe
                JOIN cameras c ON pe.camera_id = c.camera_id
                WHERE pe.timestamp >= %s
            """
            params = [bucket_minutes, bucket_minutes, since]

            if camera_id:
                query += " AND pe.camera_id = %s"
                params.append(camera_id)

            query += """
                GROUP BY pe.camera_id, c.name, time_bucket
                ORDER BY time_bucket ASC, pe.camera_id
            """

            cur.execute(query, params)
            rows = cur.fetchall()

    return [
        {
            "camera_id": r["camera_id"],
            "camera_name": r["camera_name"],
            "time_bucket": r["time_bucket"].isoformat() if r["time_bucket"] else None,
            "vehicle_count": r["vehicle_count"],
        }
        for r in rows
    ]


def get_heatmap_data(hours: int = 24) -> list[dict]:
    """
    Heatmap: returns camera locations weighted by distinct vehicle detection count.
    Avoids high FPS bias by counting unique plates rather than raw frame detections.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    c.camera_id,
                    c.name AS camera_name,
                    c.latitude,
                    c.longitude,
                    COUNT(DISTINCT pe.plate_number) AS weight
                FROM cameras c
                LEFT JOIN plate_events pe
                    ON c.camera_id = pe.camera_id
                    AND pe.timestamp >= %s
                GROUP BY c.camera_id, c.name, c.latitude, c.longitude
                ORDER BY weight DESC
            """, (since,))
            rows = cur.fetchall()

    max_w = max([r["weight"] for r in rows], default=1)
    return [
        {
            "camera_id": r["camera_id"],
            "camera_name": r["camera_name"],
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "weight": r["weight"],
            "intensity": round(r["weight"] / max(max_w, 1), 2),
        }
        for r in rows
    ]


def get_od_matrix(hours: int = 24) -> list[dict]:
    """
    Origin-Destination matrix: for each plate, find consecutive camera
    observations and count camera-to-camera movements.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                WITH ordered_events AS (
                    SELECT
                        plate_number,
                        camera_id,
                        timestamp,
                        LAG(camera_id) OVER (
                            PARTITION BY plate_number ORDER BY timestamp
                        ) AS prev_camera_id
                    FROM plate_events
                    WHERE timestamp >= %s
                ),
                transitions AS (
                    SELECT
                        prev_camera_id AS origin_camera,
                        camera_id AS destination_camera
                    FROM ordered_events
                    WHERE prev_camera_id IS NOT NULL
                      AND prev_camera_id != camera_id
                )
                SELECT
                    t.origin_camera,
                    t.destination_camera,
                    co.name AS origin_name,
                    cd.name AS destination_name,
                    COUNT(*) AS trip_count
                FROM transitions t
                JOIN cameras co ON t.origin_camera = co.camera_id
                JOIN cameras cd ON t.destination_camera = cd.camera_id
                GROUP BY t.origin_camera, t.destination_camera,
                         co.name, cd.name
                ORDER BY trip_count DESC
            """, (since,))
            rows = cur.fetchall()

    return [
        {
            "origin_camera": r["origin_camera"],
            "destination_camera": r["destination_camera"],
            "origin_name": r["origin_name"],
            "destination_name": r["destination_name"],
            "trip_count": r["trip_count"],
        }
        for r in rows
    ]


def get_congestion(hours: int = 1) -> list[dict]:
    """
    Congestion: camera-level vehicle count in recent time window,
    classified into congestion levels.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    c.camera_id,
                    c.name AS camera_name,
                    c.latitude,
                    c.longitude,
                    COUNT(pe.event_id) AS vehicle_count
                FROM cameras c
                LEFT JOIN plate_events pe
                    ON c.camera_id = pe.camera_id
                    AND pe.timestamp >= %s
                GROUP BY c.camera_id, c.name, c.latitude, c.longitude
                ORDER BY vehicle_count DESC
            """, (since,))
            rows = cur.fetchall()

    results = []
    for r in rows:
        count = r["vehicle_count"]
        if count >= 50:
            level = "severe"
        elif count >= 30:
            level = "high"
        elif count >= 15:
            level = "moderate"
        else:
            level = "low"

        results.append({
            "camera_id": r["camera_id"],
            "camera_name": r["camera_name"],
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "vehicle_count": count,
            "congestion_level": level,
        })

    return results
