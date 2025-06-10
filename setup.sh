#!/bin/bash

echo "🚀 AI TTS Microservice Setup Script"
echo "=================================="

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "❌ Git is required but not installed."
    exit 1
fi

# Create project directory
echo "📁 Creating project directory..."
mkdir -p ai-tts-service
cd ai-tts-service

# Create requirements.txt
echo "📝 Creating requirements.txt..."
cat > requirements.txt << 'EOF'
# Core web framework dependencies - minimal versions
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0

# Essential TTS dependencies only
TTS==0.22.0

# Minimal required dependencies
numpy==1.24.3
torch==2.0.1
torchaudio==2.0.2

# Audio processing - essential only
soundfile==0.12.1
librosa==0.10.1

# System monitoring
psutil==5.9.6

# Essential text processing
inflect==7.0.0
pyyaml==6.0.1
EOF

# Create Dockerfile
echo "📝 Creating Dockerfile..."
cat > Dockerfile << 'EOF'
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
EOF

# Create render.yaml
echo "📝 Creating render.yaml..."
cat > render.yaml << 'EOF'
services:
  - type: web
    name: ai-tts-service
    env: python
    plan: free
    # Simplified build command to reduce memory usage during build
    buildCommand: |
      pip install --no-cache-dir --upgrade pip==23.3.1 &&
      pip install --no-cache-dir torch==2.0.1 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cpu &&
      pip install --no-cache-dir -r requirements.txt
    # Optimized start command with memory limits
    startCommand: "uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1 --timeout-keep-alive 120 --timeout-graceful-shutdown 120 --limit-concurrency 10 --backlog 2048"
    healthCheckPath: /health
    # Memory optimization environment variables
    envVars:
      - key: PYTHONDONTWRITEBYTECODE
        value: "1"
      - key: PYTHONUNBUFFERED
        value: "1"
      # Aggressive memory management for PyTorch
      - key: PYTORCH_CUDA_ALLOC_CONF
        value: "max_split_size_mb:128"
      - key: OMP_NUM_THREADS
        value: "1"
      - key: MKL_NUM_THREADS
        value: "1"
      - key: NUMBA_CACHE_DIR
        value: "/tmp/numba_cache"
EOF

# Create .gitignore
echo "📝 Creating .gitignore..."
cat > .gitignore << 'EOF'
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/
*.log
.DS_Store
*.wav
*.mp3
tmp/
EOF

# Initialize git repository
echo "🔧 Initializing git repository..."
git init
git add .
git commit -m "Initial commit - AI TTS Microservice"

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Create a GitHub repository and push this code:"
echo "   git remote add origin https://github.com/yourusername/ai-tts-service.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "2. Deploy to Render.com:"
echo "   - Go to https://render.com"
echo "   - Create new project from GitHub repo"
echo "   - Render will automatically deploy"
echo ""
echo "3. Update your Next.js app:"
echo "   - Add NEXT_PUBLIC_TTS_SERVICE_URL=https://your-service.render.com to .env.local"
echo "   - Replace your AudioSummaryPlayer component"
echo ""
echo "4. Test locally (optional):"
echo "   pip install -r requirements.txt"
echo "   uvicorn main:app --reload"
echo ""
echo "🎉 Your AI TTS microservice is ready for deployment!"