# Database Directory

This directory contains the database schemas and initialization scripts for the PostGIS database.

## Contents
- **`schema.sql`**: The primary initialization script. It contains the schema definitions for the system, including tables like `plate_reads`, which store the plate text, timestamps, camera IDs, and PostGIS geometries (Point) for spatial querying.

When the `anpr-postgres` container starts, it may use these scripts to bootstrap the database schema.
