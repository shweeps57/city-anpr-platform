# Backend Directory

This directory contains the FastAPI backend for the City-Wide ANPR Intelligence Platform.

## Purpose
The backend acts as the bridge between the AI perception pipeline and the database/frontend. Its main responsibilities include:
- Subscribing to the Redis stream (`plate-events`) populated by the perception workers.
- Validating and enriching the read data.
- Storing the license plate reads in the PostGIS database.
- Exposing REST API endpoints for frontend dashboards to query traffic data, vehicle logs, and spatial analytics.

## Running
The backend is designed to run via Docker Compose as defined in the `docker-compose.yml` file (`anpr-backend` container).
