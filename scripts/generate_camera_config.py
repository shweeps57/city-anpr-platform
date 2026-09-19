import os
import json
import argparse
from pathlib import Path

def generate_config(video_dir: str, output_file: str):
    video_dir_path = Path(video_dir)
    output_path = Path(output_file)
    
    if not video_dir_path.exists():
        print(f"Error: Directory '{video_dir}' does not exist.")
        return

    valid_extensions = {".mp4", ".avi", ".mkv", ".mov"}
    video_files = [f for f in video_dir_path.iterdir() if f.is_file() and f.suffix.lower() in valid_extensions]
    
    # Sort files alphabetically so they are assigned sequential orders predictably
    video_files.sort()

    if not video_files:
        print(f"No video files found in '{video_dir}'. Supported formats: {valid_extensions}")
        return

    cameras = []
    # Create a camera entry for each video
    for idx, video_file in enumerate(video_files, start=1):
        camera_id = f"CAM_{idx:02d}"
        
        # Use the filename (without extension) as a fallback name
        name = video_file.stem.replace("_", " ").title()
        
        # Map the path relative to the perception container's /app/data/videos if it's in data/videos
        # In the docker container, ./data/videos is mounted to /app/data/videos
        # We need to construct the container-side path.
        try:
            rel_path = video_file.relative_to(Path("data/videos"))
            container_video_path = f"data/videos/{rel_path.as_posix()}"
        except ValueError:
            # If not in data/videos, just use the absolute path or whatever was provided
            container_video_path = video_file.as_posix()

        camera = {
            "camera_id": camera_id,
            "name": name,
            "video_path": container_video_path,
            "latitude": 12.0000 + (idx * 0.0010),  # Mock coordinates spread out
            "longitude": 77.0000,
            "road": "Dataset Video",
            "direction": "northbound",
            "sequence_order": idx
        }
        cameras.append(camera)

    # Make sure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(cameras, f, indent=4)
    
    print(f"Successfully generated {output_path} with {len(cameras)} cameras.")
    print("You can now restart the perception container to process this dataset:")
    print("  docker compose restart perception")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate cameras.json from a folder of video files.")
    parser.add_argument(
        "--video-dir", 
        type=str, 
        default="data/videos/dataset",
        help="Path to the directory containing video files (e.g. data/videos/dataset)"
    )
    parser.add_argument(
        "--output", 
        type=str, 
        default="config/cameras.json",
        help="Path where cameras.json will be saved"
    )
    
    args = parser.parse_args()
    generate_config(args.video_dir, args.output)
