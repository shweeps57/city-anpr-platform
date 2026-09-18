from fastapi import APIRouter, HTTPException
from services.trajectory import get_plate_trajectory

router = APIRouter(prefix="/api/trajectory", tags=["Trajectory"])


@router.get("/{plate_number}")
def trajectory(plate_number: str):
    """
    Get the observed trajectory of a vehicle by plate number.

    Returns chronologically ordered camera observations with
    geographic coordinates and a GeoJSON LineString for map display.
    """
    result = get_plate_trajectory(plate_number)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No observations found for plate: {plate_number.upper()}"
        )
    return result
