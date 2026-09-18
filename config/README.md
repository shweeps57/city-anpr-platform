# Config Directory

This directory stores configuration files for the ANPR platform.

## Contents
- **`cameras.json`**: This file defines the different camera nodes/feeds across the city. Each entry specifies a `camera_id`, `name`, `video_path` (pointing to the local video file), and geographic metadata like `latitude` and `longitude`.

The perception container mounts this directory as a read-only volume (`/app/config`) and reads `cameras.json` to spawn the necessary worker threads for each video feed.
