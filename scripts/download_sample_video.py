import urllib.request
import shutil
import sys
from pathlib import Path

# Intel IoT DevKit sample video (contains cars/traffic)
VIDEO_URL = "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/car-detection.mp4"

VIDEOS_DIR = Path(__file__).resolve().parent.parent / "data" / "videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

target_files = [
    "cam_01.mp4",
    "cam_02.mp4",
    "cam_03.mp4",
    "cam_04.mp4",
    "cam_05.mp4"
]

def download_sample():
    print(f"Downloading sample video to {target_files[0]}...")
    first_file = VIDEOS_DIR / target_files[0]
    
    try:
        urllib.request.urlretrieve(VIDEO_URL, first_file)
        print(f"Successfully downloaded {target_files[0]}")
    except Exception as e:
        print(f"Failed to download video: {e}")
        sys.exit(1)
        
    print("Duplicating video for all 5 simulated cameras...")
    for filename in target_files[1:]:
        dest = VIDEOS_DIR / filename
        shutil.copy(first_file, dest)
        print(f"Created {filename}")
        
    print("\n[OK] Sample videos are ready in data/videos/!")

if __name__ == "__main__":
    download_sample()
