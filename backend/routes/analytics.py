from fastapi import APIRouter, Query
from services.analytics import (
    get_traffic_density,
    get_heatmap_data,
    get_od_matrix,
    get_congestion,
)

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/density")
def density(
    camera_id: str | None = Query(None, description="Filter by camera ID"),
    hours: int = Query(24, ge=1, le=720, description="Lookback window in hours"),
    bucket_minutes: int = Query(60, ge=5, le=1440, description="Time bucket size in minutes"),
):
    """
    Traffic density: vehicle counts per camera per time bucket.

    Returns time-series data suitable for bar/line charts.
    """
    return get_traffic_density(
        camera_id=camera_id, hours=hours, bucket_minutes=bucket_minutes
    )


@router.get("/heatmap")
def heatmap(
    hours: int = Query(24, ge=1, le=720, description="Lookback window in hours"),
):
    """
    Traffic heatmap: camera locations weighted by detection count.

    Returns lat/lng/weight data for Leaflet heatmap layer.
    """
    return get_heatmap_data(hours=hours)


@router.get("/od-matrix")
def od_matrix(
    hours: int = Query(24, ge=1, le=720, description="Lookback window in hours"),
):
    """
    Origin-Destination matrix: camera-to-camera movement patterns.

    Counts how many vehicles moved from one camera to another
    based on consecutive plate observations.
    """
    return get_od_matrix(hours=hours)


@router.get("/congestion")
def congestion(
    hours: int = Query(1, ge=1, le=24, description="Lookback window in hours"),
):
    """
    Congestion levels per camera based on recent detection volume.

    Levels: low (<15), moderate (15-29), high (30-49), severe (50+).
    """
    return get_congestion(hours=hours)
