# Use Python 3.10 specifically for TTS compatibility
FROM python:3.10-slim-bullseye

# Prevent Python from writing .pyc files and ensure real-time logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Memory optimization for free tier deployment
ENV PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV NUMBA_CACHE_DIR=/tmp/numba_cache

# Install system dependencies required for TTS and audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    libsndfile1-dev \
    ffmpeg \
    espeak-ng \
    espeak-ng-data \
    libespeak-ng-dev \
    mecab \
    libmecab-dev \
    mecab-ipadic-utf8 \
    git \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /app

# Copy requirements first for Docker layer caching
COPY requirements.txt .

# Upgrade pip and install Python dependencies
# Install in specific order to avoid conflicts
RUN pip install --no-cache-dir --upgrade pip==23.3.1 setuptools==68.2.2 wheel==0.41.2

# Install dependencies with verbose output for debugging
RUN pip install --no-cache-dir --verbose \
    numpy==1.22.0 \
    && pip install --no-cache-dir --verbose \
    torch==2.0.1 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir --verbose \
    torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies
RUN pip install --no-cache-dir --verbose -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/tmp /tmp/numba_cache && chmod 777 /app/tmp /tmp/numba_cache

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application with optimized settings
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-keep-alive", "120", "--timeout-graceful-shutdown", "120", "--limit-concurrency", "10", "--backlog", "2048"]