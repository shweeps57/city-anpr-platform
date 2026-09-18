FROM python:3.11-slim

# System deps for OpenCV + PaddleOCR
RUN apt-get update && apt-get install -y \
    libgl1 libglib2.0-0 libgomp1 wget \
    && rm -rf /var/lib/apt/lists/*

# Ensure Python output is not buffered (critical for Docker logs)
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
# Install CPU-only PyTorch FIRST to prevent ultralytics from pulling 1GB+ CUDA torch
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "run.py"]
