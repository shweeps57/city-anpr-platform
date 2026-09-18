# Scripts Directory

This directory contains utility and helper scripts for the ANPR platform.

## Available Scripts
- **`download_models.py`**: A setup script that downloads the required PyTorch (`.pt`) model weights for YOLOv8 (vehicle detection) and the custom plate detector. 
  
  **Usage**: 
  This script must be run ONCE on the host machine before starting the Docker environment, as it populates the `models/` directory which is mounted into the perception container.
  ```bash
  python scripts/download_models.py
  ```
