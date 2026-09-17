CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS cameras (
    camera_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    road VARCHAR(150),
    direction VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS plate_events (
    event_id UUID PRIMARY KEY,
    plate_number VARCHAR(20) NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    camera_id VARCHAR(50) NOT NULL REFERENCES cameras(camera_id),
    timestamp TIMESTAMPTZ NOT NULL,
    vehicle_type VARCHAR(50),
    direction VARCHAR(50),
    track_id VARCHAR(100),
    location GEOMETRY(Point, 4326),
    snapshot_path TEXT
);

CREATE TABLE IF NOT EXISTS blacklist (
    plate_number VARCHAR(20) PRIMARY KEY,
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id UUID PRIMARY KEY,
    plate_number VARCHAR(20),
    alert_type VARCHAR(50) NOT NULL,
    message TEXT,
    camera_id VARCHAR(50),
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_plate_events_plate
    ON plate_events(plate_number);

CREATE INDEX IF NOT EXISTS idx_plate_events_timestamp
    ON plate_events(timestamp);

CREATE INDEX IF NOT EXISTS idx_plate_events_camera
    ON plate_events(camera_id);

CREATE INDEX IF NOT EXISTS idx_plate_events_location
    ON plate_events USING GIST(location);