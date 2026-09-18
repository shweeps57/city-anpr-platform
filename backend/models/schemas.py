from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from uuid import UUID


# ─── Camera ───

class CameraBase(BaseModel):
    camera_id: str
    name: str
    latitude: float
    longitude: float
    road: Optional[str] = None
    direction: Optional[str] = None


class CameraResponse(CameraBase):
    pass


# ─── Plate Event ───

class PlateEventResponse(BaseModel):
    event_id: UUID
    plate_number: str
    confidence: float
    camera_id: str
    timestamp: datetime
    vehicle_type: Optional[str] = None
    direction: Optional[str] = None
    track_id: Optional[str] = None
    snapshot_path: Optional[str] = None


class PlateEventCreate(BaseModel):
    """Canonical event emitted by the perception pipeline."""
    event_id: UUID
    plate_number: str = Field(..., min_length=1, max_length=20)
    confidence: float = Field(..., ge=0.0, le=1.0)
    camera_id: str = Field(..., min_length=1, max_length=50)
    timestamp: datetime
    vehicle_type: Optional[str] = None
    direction: Optional[str] = None
    track_id: Optional[str] = None
    snapshot_path: Optional[str] = None


# ─── Trajectory ───

class TrajectoryPoint(BaseModel):
    """A single point in a vehicle's trajectory."""
    camera_id: str
    camera_name: str
    latitude: float
    longitude: float
    timestamp: datetime
    confidence: float
    vehicle_type: Optional[str] = None


class TrajectoryResponse(BaseModel):
    """Full trajectory for a plate number."""
    plate_number: str
    points: list[TrajectoryPoint]
    total_observations: int
    geojson: dict  # GeoJSON LineString


# ─── Analytics ───

class DensityBucket(BaseModel):
    """Vehicle count in a time bucket for a camera."""
    camera_id: str
    camera_name: str
    time_bucket: str
    vehicle_count: int


class HeatmapPoint(BaseModel):
    """Geographic point with traffic weight."""
    latitude: float
    longitude: float
    weight: int
    intensity: Optional[float] = 0.0
    camera_id: str
    camera_name: str


class ODEntry(BaseModel):
    """Origin-Destination pair with count."""
    origin_camera: str
    destination_camera: str
    origin_name: str
    destination_name: str
    trip_count: int


class CongestionInfo(BaseModel):
    """Congestion level for a camera."""
    camera_id: str
    camera_name: str
    latitude: float
    longitude: float
    vehicle_count: int
    congestion_level: str  # low, moderate, high, severe


# ─── Blacklist ───

class BlacklistEntry(BaseModel):
    plate_number: str
    reason: Optional[str] = None
    created_at: Optional[datetime] = None


class BlacklistCreate(BaseModel):
    plate_number: str = Field(..., min_length=1, max_length=20)
    reason: Optional[str] = None


# ─── Alerts ───

class AlertResponse(BaseModel):
    alert_id: UUID
    plate_number: Optional[str] = None
    alert_type: str
    message: Optional[str] = None
    camera_id: Optional[str] = None
    timestamp: datetime


class AlertCreate(BaseModel):
    plate_number: str
    alert_type: str = "blacklist"
    message: Optional[str] = None
    camera_id: Optional[str] = None
