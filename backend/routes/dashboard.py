from fastapi import APIRouter
from services.dashboard import get_dashboard_stats

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats")
def dashboard_stats():
    """
    Aggregated KPI stats for the frontend dashboard.

    Returns camera count, detection count, flagged count,
    alert count, and average confidence in a single call.
    """
    return get_dashboard_stats()
