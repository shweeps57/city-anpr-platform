from fastapi import APIRouter, HTTPException
from models.schemas import BlacklistCreate
from services.alerts import (
    get_all_blacklist,
    add_to_blacklist,
    remove_from_blacklist,
    check_blacklist,
)

router = APIRouter(prefix="/api/blacklist", tags=["Blacklist"])


@router.get("")
def list_blacklist():
    """Get all blacklisted plate numbers."""
    return get_all_blacklist()


@router.get("/{plate_number}")
def check_plate(plate_number: str):
    """Check if a specific plate is blacklisted."""
    result = check_blacklist(plate_number)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Plate {plate_number.upper()} is not blacklisted"
        )
    return result


@router.post("", status_code=201)
def add_plate(entry: BlacklistCreate):
    """
    Add a plate to the blacklist.

    If the plate already exists, updates the reason.
    """
    return add_to_blacklist(entry.plate_number, entry.reason)


@router.delete("/{plate_number}")
def delete_plate(plate_number: str):
    """Remove a plate from the blacklist."""
    deleted = remove_from_blacklist(plate_number)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Plate {plate_number.upper()} not found in blacklist"
        )
    return {"message": f"{plate_number.upper()} removed from blacklist"}
