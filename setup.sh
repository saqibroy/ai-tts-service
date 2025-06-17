#!/bin/bash

echo "🚀 Google Cloud TTS Microservice Setup Script"
echo "==========================================="

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
mkdir -p google-cloud-tts-service
cd google-cloud-tts-service

# Create requirements.txt
echo "📝 Creating requirements.txt..."
cat > requirements.txt << 'EOF'
# Core web framework dependencies
fastapi
uvicorn[standard]
pydantic

# Google Cloud TTS
google-cloud-texttospeech

# Minimal required dependencies
numpy
torch
torchaudio

# System monitoring
psutil
EOF

# Create Dockerfile
echo "📝 Creating Dockerfile..."
cat > Dockerfile << 'EOF'
# Use Python 3.10
FROM python:3.10-slim-bullseye

# Prevent Python from writing .pyc files and ensure real-time logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /app

# Copy requirements first for Docker layer caching
COPY requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

# Create render.yaml
echo "📝 Creating render.yaml..."
cat > render.yaml << 'EOF'
services:
  - type: web
    name: google-cloud-tts-service
    env: python
    plan: free
    # Simplified build command
    buildCommand: |
      pip install --no-cache-dir --upgrade pip setuptools wheel &&
      pip install --no-cache-dir -r requirements.txt
    # Simplified start command
    startCommand: "uvicorn main:app --host 0.0.0.0 --port $PORT"
    healthCheckPath: /health
    # Environment variables
    envVars:
      - key: PYTHONDONTWRITEBYTECODE
        value: "1"
      - key: PYTHONUNBUFFERED
        value: "1"
      - key: GOOGLE_APPLICATION_CREDENTIALS
        value: "/etc/secrets/google-credentials.json"
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
*.json
!package.json
!package-lock.json
EOF

# Initialize git repository
echo "🔧 Initializing git repository..."
git init
git add .
git commit -m "Initial commit - Google Cloud TTS Microservice"

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Create a GitHub repository and push this code:"
echo "   git remote add origin https://github.com/yourusername/google-cloud-tts-service.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "2. Deploy to Render.com:"
echo "   - Go to https://render.com"
echo "   - Create new project from GitHub repo"
echo "   - Upload your Google Cloud credentials as a secret file named 'google-credentials.json'"
echo "   - Render will automatically deploy"
echo ""
echo "3. Update your Next.js app:"
echo "   - Add NEXT_PUBLIC_TTS_SERVICE_URL=https://your-service.render.com to .env.local"
echo "   - Replace your AudioSummaryPlayer component"
echo ""
echo "4. Test locally (optional):"
echo "   pip install -r requirements.txt"
echo "   export GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/credentials.json"
echo "   uvicorn main:app --reload"
echo ""
echo "🎉 Your Google Cloud TTS microservice is ready for deployment!"