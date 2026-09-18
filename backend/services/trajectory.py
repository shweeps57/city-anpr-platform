from database.connection import get_db_connection


def get_plate_trajectory(plate_number: str) -> dict:
    """
    Reconstruct the trajectory of a vehicle by plate number.
    Queries all plate_events for this plate, joins with camera locations,
    orders by timestamp, and builds a GeoJSON LineString.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    pe.event_id,
                    pe.plate_number,
                    pe.confidence,
                    pe.camera_id,
                    pe.timestamp,
                    pe.vehicle_type,
                    c.name AS camera_name,
                    c.latitude,
                    c.longitude
                FROM plate_events pe
                JOIN cameras c ON pe.camera_id = c.camera_id
                WHERE pe.plate_number = %s
                ORDER BY pe.timestamp ASC
            """, (plate_number.upper(),))
            rows = cur.fetchall()

    if not rows:
        return None

    points = []
    coordinates = []

    for row in rows:
        points.append({
            "camera_id": row["camera_id"],
            "camera_name": row["camera_name"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "timestamp": row["timestamp"].isoformat(),
            "confidence": row["confidence"],
            "vehicle_type": row["vehicle_type"],
        })
        coordinates.append([row["longitude"], row["latitude"]])

    # Build GeoJSON LineString (or Point if only one observation)
    if len(coordinates) == 1:
        geojson = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": coordinates[0],
            },
            "properties": {"plate_number": plate_number.upper()},
        }
    else:
        geojson = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coordinates,
            },
            "properties": {"plate_number": plate_number.upper()},
        }

    return {
        "plate_number": plate_number.upper(),
        "points": points,
        "total_observations": len(points),
        "geojson": geojson,
    }
