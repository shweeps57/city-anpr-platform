# City-Wide ANPR Intelligence Platform

A centralized AI-powered Automatic Number Plate Recognition (ANPR) platform for processing multiple camera feeds, recognizing vehicle license plates, reconstructing vehicle trajectories, analyzing city-wide traffic movement, and generating security alerts.

Core principle:

One detection event → written once → used for trajectory, analytics, and alerts.

---

## Features

### AI-Based ANPR

- Vehicle detection using YOLO
- License plate detection
- License plate OCR using PaddleOCR
- Image preprocessing for difficult plate conditions
- Regex-based Indian license plate validation
- OCR confusion-character correction
- Temporal voting across multiple frames

### Multi-Camera Vehicle Intelligence

- Multiple virtual camera feeds
- Vehicle tracking within individual camera feeds
- Cross-camera plate correlation
- Vehicle trajectory reconstruction
- GIS-based trajectory visualization

### Traffic Analytics

- Per-camera traffic density
- City-wide heatmaps
- Origin-Destination (OD) movement patterns
- Congestion analysis
- Traffic flow and direction analysis
- Average speed estimation

### Security & Alerts

- Blacklisted vehicle detection
- Real-time alert generation
- Suspicious route anomaly detection
- WebSocket-based live alerts

### Dashboard

- Plate search
- Vehicle trajectory map
- Traffic heatmap
- Traffic analytics
- Live security alerts

---

# System Architecture

The platform is divided into the following layers:

    ┌──────────────────────────────────────────────┐
    │              CITY TRAFFIC DASHBOARD          │
    │          React + Leaflet + Recharts          │
    └──────────────────────┬───────────────────────┘
                           │
                           ▼
    ┌──────────────────────────────────────────────┐
    │              APPLICATION SERVICES            │
    │                   FastAPI                    │
    │                                              │
    │  Trajectory API │ Analytics API │ Alert API  │
    └──────────────────────┬───────────────────────┘
                           │
                           ▼
    ┌──────────────────────────────────────────────┐
    │                  DATA LAYER                  │
    │             PostgreSQL + PostGIS             │
    │                                              │
    │ cameras │ plate_events │ blacklist │ alerts │
    └──────────────────────┬───────────────────────┘
                           │
                           ▲
    ┌──────────────────────────────────────────────┐
    │                EVENT SPINE                   │
    │              Redis Streams                   │
    │               plate-events                   │
    └──────────────────────┬───────────────────────┘
                           ▲
    ┌──────────────────────────────────────────────┐
    │               PERCEPTION LAYER               │
    │                                              │
    │ Vehicle Detection → Tracking → Plate Detect │
    │        → Preprocessing → OCR → Voting        │
    └──────────────────────┬───────────────────────┘
                           ▲
    ┌──────────────────────────────────────────────┐
    │          CAMERA / VIDEO INPUT LAYER          │
    │                                              │
    │ CAM_01 │ CAM_02 │ CAM_03 │ CAM_04 │ CAM_05 │
    │                                              │
    │       Prerecorded videos / virtual feeds     │
    └──────────────────────────────────────────────┘

For the hackathon, prerecorded traffic videos are used as virtual camera feeds. Each video is mapped to a virtual camera using a camera configuration file.

The architecture can later accept real RTSP camera streams without changing the core backend design.

---

# Project Structure

    city-anpr-platform/
    │
    ├── backend/
    │   ├── main.py
    │   ├── routes/
    │   │   ├── trajectory.py
    │   │   ├── analytics.py
    │   │   ├── blacklist.py
    │   │   └── alerts.py
    │   ├── services/
    │   │   ├── trajectory.py
    │   │   ├── analytics.py
    │   │   └── alerts.py
    │   ├── database/
    │   │   └── connection.py
    │   ├── models/
    │   │   └── schemas.py
    │   ├── requirements.txt
    │   └── Dockerfile
    │
    ├── frontend/
    │   └── ...
    │
    ├── perception/
    │   ├── ...
    │   └── models/
    │
    ├── analytics/
    │   └── ...
    │
    ├── alerts/
    │   └── ...
    │
    ├── database/
    │   └── schema.sql
    │
    ├── data/
    │   ├── videos/
    │   └── validation/
    │
    ├── models/
    │   └── ...
    │
    ├── config/
    │   └── cameras.json
    │
    ├── docker/
    │   └── ...
    │
    ├── docker-compose.yml
    ├── .gitignore
    ├── LICENSE
    └── README.md

---

# Tech Stack

| Layer | Technology |
|---|---|
| Vehicle Detection | YOLO |
| Vehicle Tracking | ByteTrack / BoT-SORT |
| Plate Detection | YOLO fine-tuned for license plates |
| OCR | PaddleOCR |
| Image Processing | OpenCV |
| Backend | FastAPI |
| Database | PostgreSQL |
| GIS | PostGIS |
| Event Queue | Redis Streams |
| Frontend | React |
| Maps | Leaflet |
| Charts | Recharts |
| Real-Time Updates | WebSockets |
| Containers | Docker + Docker Compose |

---

# Getting Started

## Prerequisites

Install:

- Git
- Docker Desktop
- Docker Compose

You do not need to install PostgreSQL or Redis directly on your machine.

Docker Compose runs the required services in containers.

---

# 1. Clone the Repository

    git clone https://github.com/YOUR_USERNAME/city-anpr-platform.git
    cd city-anpr-platform

Replace YOUR_USERNAME with the GitHub account that owns the repository.

---

# 2. Start the Project with Docker

The Docker setup runs:

- PostgreSQL + PostGIS
- Redis
- FastAPI backend

Start the services:

    docker compose up -d --build

Check the running containers:

    docker compose ps

You should see containers similar to:

    anpr-postgres
    anpr-redis
    anpr-backend

---

# 3. Verify the Backend

Open:

    http://localhost:8000

Expected response:

    {
      "status": "ok"
    }

You can also check:

    http://localhost:8000/health

The health endpoint verifies connectivity between FastAPI, PostgreSQL, and Redis.

---

# 4. Access PostgreSQL

PostgreSQL is exposed on:

    localhost:5432

Default development credentials:

    Database: anpr
    Username: anpr
    Password: anpr_dev_password

These credentials are intended for local development only.

---

# 5. Verify PostGIS

Run:

    docker exec -it anpr-postgres psql -U anpr -d anpr -c "SELECT PostGIS_Version();"

A PostGIS version should be returned.

PostGIS provides the spatial functionality required for:

- Camera locations
- GIS visualization
- Distance calculations
- Vehicle trajectories
- Spatial queries
- Route anomaly detection

---

# Database

PostgreSQL is the central source of truth for the platform.

The main tables are:

    cameras
    plate_events
    blacklist
    alerts

## cameras

Stores metadata for each virtual or physical camera:

    camera_id
    name
    latitude
    longitude
    road
    direction

## plate_events

Stores every confirmed ANPR observation:

    event_id
    plate_number
    confidence
    camera_id
    timestamp
    vehicle_type
    direction
    track_id
    location
    snapshot_path

## blacklist

Stores plates that should trigger security alerts:

    plate_number
    reason
    created_at

## alerts

Stores generated alerts:

    alert_id
    plate_number
    alert_type
    message
    camera_id
    timestamp

---

# Initialize the Database

The database schema is located at:

    database/schema.sql

Apply the schema using:

    docker exec -i anpr-postgres psql -U anpr -d anpr < database/schema.sql

---

# Camera Configuration

For the hackathon, prerecorded traffic videos act as virtual camera feeds.

Camera metadata is stored separately from the video files.

Example `config/cameras.json`:

    [
      {
        "camera_id": "CAM_01",
        "name": "Junction A",
        "video_path": "data/videos/cam_01.mp4",
        "latitude": 31.2560,
        "longitude": 75.7030,
        "road": "GT Road",
        "direction": "north"
      },
      {
        "camera_id": "CAM_02",
        "name": "Junction B",
        "video_path": "data/videos/cam_02.mp4",
        "latitude": 31.2580,
        "longitude": 75.7070,
        "road": "GT Road",
        "direction": "east"
      }
    ]

The `video_path` maps a video file to a virtual camera.

The `camera_id` is attached to every plate event generated from that video.

    cam_01.mp4
         ↓
       CAM_01
         ↓
    ANPR detection
         ↓
    plate_events.camera_id = CAM_01
         ↓
    cameras table
         ↓
    latitude / longitude
         ↓
    GIS map

---

# Data

Large datasets, videos, and model weights should not be committed to Git.

Place local video files in:

    data/videos/

Example:

    data/videos/
    ├── cam_01.mp4
    ├── cam_02.mp4
    ├── cam_03.mp4
    └── cam_04.mp4

Place validation images in:

    data/validation/

Model weights should be stored locally in:

    models/

Example:

    models/
    ├── yolov8n.pt
    └── plate_detector.pt

These files are excluded from Git using `.gitignore`.

---

# AI Pipeline

The intended perception pipeline is:

    Video
      ↓
    Vehicle Detection
      ↓
    Vehicle Tracking
      ↓
    Plate Detection
      ↓
    Plate / Vehicle Association
      ↓
    Image Preprocessing
      ↓
    OCR
      ↓
    Regex Validation
      ↓
    Confusion Character Correction
      ↓
    Temporal Voting
      ↓
    Confirmed Plate Event

The system processes multiple frames of the same vehicle instead of relying on a single OCR result.

Image preprocessing may include:

- Grayscale conversion
- CLAHE
- Deskewing
- Sharpening

The OCR output is then validated and corrected before a confirmed plate event is generated.

---

# Event Flow

A confirmed detection becomes a single canonical event.

Example:

    {
      "event_id": "9c1e2f3a-...",
      "plate_number": "PB65AB1234",
      "confidence": 0.94,
      "camera_id": "CAM_01",
      "timestamp": "2026-09-13T10:42:15Z",
      "vehicle_type": "car",
      "direction": "northbound",
      "track_id": "17"
    }

The same event can then power multiple platform features:

                        plate_event
                             │
              ┌──────────────┼──────────────┐
              ↓              ↓              ↓
          Trajectory      Analytics       Alerts
              │              │              │
              ↓              ↓              ↓
           GIS Map       Heatmap / OD    Live Alert

This avoids building separate data pipelines for each requirement.

---

# Redis Event Flow

The intended production-style flow is:

    Camera Worker
         ↓
    Detection + OCR
         ↓
    Redis Stream
         ↓
    Event Consumer
         ↓
    PostgreSQL + PostGIS
         ↓
    FastAPI
         ↓
    Dashboard

The Redis stream is named:

    plate-events

For local development or if Redis is unavailable, the perception service can use a direct PostgreSQL write as a fallback.

---

# API

Planned API endpoints include:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/trajectory/{plate_number}` | GET | Get vehicle trajectory |
| `/api/analytics/heatmap` | GET | City-wide traffic heatmap |
| `/api/analytics/density` | GET | Per-camera traffic density |
| `/api/analytics/od-matrix` | GET | Origin-Destination flow |
| `/api/analytics/congestion` | GET | Congestion information |
| `/api/blacklist` | GET | List blacklisted plates |
| `/api/blacklist` | POST | Add a blacklisted plate |
| `/ws/alerts` | WebSocket | Real-time alerts |

---

# Traffic Analytics

Analytics are generated from the same `plate_events` table.

## Traffic Density

Traffic events can be aggregated by camera and time interval:

    camera_id + time_bucket → event count

## Heatmap

Event locations can be converted into:

    latitude
    longitude
    weight

and rendered on the city map.

## Origin-Destination

If a plate is observed in:

    CAM_01 → CAM_03 → CAM_05

the system can aggregate these camera-to-camera movements to generate an OD matrix.

## Congestion

Traffic volume and available movement/speed signals can be aggregated over time to identify cameras experiencing unusually high traffic.

---

# Alerts

## Blacklist Alert

When a new plate event matches a plate in the blacklist:

    plate event
         ↓
    blacklist lookup
         ↓
       match
         ↓
    alert generated
         ↓
      WebSocket
         ↓
      dashboard

## Route Anomaly

If the same plate appears at geographically separated cameras in an elapsed time that is physically implausible, the system can flag the event for investigation.

This represents a possible anomaly and should not automatically be interpreted as proof of a cloned vehicle.

---

# Docker Commands

## Start

    docker compose up -d

## Start and rebuild

Use this after changing dependencies or Docker configuration:

    docker compose up -d --build

## Stop

    docker compose down

## Check containers

    docker compose ps

## View all logs

    docker compose logs

## View backend logs

    docker compose logs backend

## Follow backend logs

    docker compose logs -f backend

## Restart backend

    docker compose restart backend

## Stop and remove containers + volumes

WARNING: This deletes the local PostgreSQL and Redis data stored in Docker volumes.

    docker compose down -v

---

# Development Workflow

    1. Clone repository
           ↓
    2. Start Docker
           ↓
    3. Initialize database
           ↓
    4. Add local videos
           ↓
    5. Configure virtual cameras
           ↓
    6. Run perception pipeline
           ↓
    7. Generate plate events
           ↓
    8. Store events in PostgreSQL
           ↓
    9. Query through FastAPI
           ↓
    10. Visualize through React dashboard

---

# Development Status

## Completed

- Project repository
- Docker Compose setup
- PostgreSQL + PostGIS
- Redis
- FastAPI backend
- Backend health check
- Initial database schema
- Project architecture

## In Development

- Vehicle detection
- License plate detection
- OCR pipeline
- Vehicle tracking
- Camera configuration
- Event ingestion
- Trajectory API
- Traffic analytics
- Dashboard
- Alert system

## Planned

- Multi-camera correlation
- GIS trajectory visualization
- Traffic heatmaps
- OD matrix
- Congestion analysis
- Real-time WebSocket alerts
- OCR validation benchmark
- Vehicle re-identification fallback
- Average speed estimation
- Predictive traffic analysis

---

# Accuracy Evaluation

ANPR accuracy should be measured using a manually labeled validation dataset rather than relying on an unsupported accuracy claim.

The planned validation process is:

    50–100 labeled plate crops
              ↓
    Run complete OCR pipeline
              ↓
    Compare with ground truth
              ↓
    Calculate accuracy
              ↓
    Report measured result

The measured accuracy should be reported together with the size and conditions of the validation dataset.

---

# Contributing

1. Fork the repository.

2. Create a feature branch:

    git checkout -b feature/your-feature

3. Make your changes.

4. Test locally.

5. Commit your changes:

    git add .
    git commit -m "Add your feature"

6. Push the branch:

    git push origin feature/your-feature

7. Open a Pull Request.

---

# License

This project is licensed under the MIT License.

See `LICENSE` for details.

Individual third-party libraries, models, pretrained weights, datasets, and video sources may have their own licenses. Check their respective licenses before redistribution or commercial use.
