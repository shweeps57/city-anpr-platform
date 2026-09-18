# Data Directory

This directory is used for local data storage for the ANPR pipeline.

## Subdirectories
- **`videos/`**: This is where you should place the raw `.mp4` video files representing traffic camera feeds. Update `config/cameras.json` to point to these files.
- **`snapshots/`**: The perception pipeline saves cropped images of recognized license plates into this directory for later review or validation.

*Note: In production deployments, this directory might be replaced by RTSP camera streams and cloud object storage (e.g. AWS S3) for snapshots.*
