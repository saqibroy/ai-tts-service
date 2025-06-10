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

# Create main.py
echo "📝 Creating main.py..."
cat > main.py << 'EOF'
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import io
import os
import torch
import tempfile
import logging
from typing import Optional
import gc
import threading
import asyncio
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variable to store TTS service
tts_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global tts_service
    try:
        logger.info("Initializing TTS Service...")
        tts_service = TTSService()
        logger.info("TTS Service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize TTS service: {e}")
        tts_service = None
    
    yield
    
    # Shutdown
    if tts_service:
        logger.info("Cleaning up TTS Service...")
        tts_service.cleanup()

app = FastAPI(
    title="AI TTS Microservice",
    version="1.0.0",
    description="Professional Text-to-Speech microservice with neural voices",
    lifespan=lifespan
)

# CORS configuration
origins = [
    "*",  # Allow all origins for development - restrict in production
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "female_calm"
    speed: Optional[float] = 1.0

class TTSService:
    def __init__(self):
        self.models = {}
        self.model_lock = threading.Lock()
        
        # Simplified voice configuration for better compatibility
        self.available_voices = {
            "female_calm": {
                "model": "tts_models/en/ljspeech/tacotron2-DDC",
                "speaker": None,
                "description": "Female, calm and clear"
            },
            "female_fast": {
                "model": "tts_models/en/ljspeech/fast_pitch",
                "speaker": None,
                "description": "Female, faster generation"
            }
        }
        
        # Pre-warm one model to reduce first request latency
        try:
            self._preload_default_model()
        except Exception as e:
            logger.warning(f"Could not preload default model: {e}")
    
    def _preload_default_model(self):
        """Preload the default model in a separate thread"""
        def preload():
            try:
                logger.info("Preloading default model...")
                self.get_model("tts_models/en/ljspeech/tacotron2-DDC")
                logger.info("Default model preloaded successfully")
            except Exception as e:
                logger.error(f"Failed to preload default model: {e}")
        
        # Run preloading in background
        preload_thread = threading.Thread(target=preload, daemon=True)
        preload_thread.start()
    
    def get_model(self, model_name: str):
        """Load and cache TTS model with memory management"""
        with self.model_lock:
            if model_name not in self.models:
                try:
                    logger.info(f"Loading model: {model_name}")
                    
                    # Clear existing models if memory is limited
                    if len(self.models) >= 2:  # Keep max 2 models in memory
                        logger.info("Clearing oldest model to free memory")
                        oldest_model = next(iter(self.models))
                        del self.models[oldest_model]
                        gc.collect()
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                    
                    # Import TTS here to avoid startup issues
                    from TTS.api import TTS
                    
                    # Force CPU usage for stability
                    device = "cpu"
                    self.models[model_name] = TTS(model_name).to(device)
                    logger.info(f"Model {model_name} loaded successfully on {device}")
                    
                except Exception as e:
                    logger.error(f"Failed to load model {model_name}: {str(e)}")
                    raise HTTPException(
                        status_code=500, 
                        detail=f"Failed to load TTS model: {str(e)}"
                    )
            
            return self.models[model_name]
    
    def generate_speech(self, text: str, voice: str = "female_calm", speed: float = 1.0) -> bytes:
        """Generate speech from text with comprehensive error handling"""
        try:
            # Input validation and sanitization
            if not text or not text.strip():
                raise HTTPException(status_code=400, detail="Text cannot be empty")
            
            # Limit text length for memory management
            max_length = 1000
            if len(text) > max_length:
                text = text[:max_length]
                logger.warning(f"Text truncated to {max_length} characters")
            
            # Clean text
            text = text.strip()
            
            # Validate voice
            if voice not in self.available_voices:
                logger.warning(f"Invalid voice '{voice}', using default")
                voice = "female_calm"
            
            # Validate speed
            speed = max(0.5, min(2.0, float(speed)))  # Clamp between 0.5 and 2.0
            
            voice_config = self.available_voices[voice]
            model = self.get_model(voice_config["model"])
            
            # Generate speech with temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                try:
                    logger.info(f"Generating speech for {len(text)} characters")
                    
                    # Generate speech (simplified parameters for stability)
                    model.tts_to_file(
                        text=text,
                        file_path=tmp_file.name
                    )
                    
                    # Read the generated audio file
                    if not os.path.exists(tmp_file.name):
                        raise Exception("Audio file was not generated")
                    
                    with open(tmp_file.name, 'rb') as audio_file:
                        audio_data = audio_file.read()
                    
                    if not audio_data:
                        raise Exception("Generated audio file is empty")
                    
                    logger.info(f"Successfully generated {len(audio_data)} bytes of audio")
                    return audio_data
                    
                finally:
                    # Always clean up temp file
                    try:
                        if os.path.exists(tmp_file.name):
                            os.unlink(tmp_file.name)
                    except Exception as e:
                        logger.warning(f"Failed to clean up temp file: {e}")
                        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Speech generation failed: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Speech generation failed: {str(e)}"
            )
    
    def cleanup(self):
        """Clean up resources"""
        try:
            with self.model_lock:
                for model_name in list(self.models.keys()):
                    del self.models[model_name]
                self.models.clear()
            gc.collect()
            logger.info("TTS Service cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

@app.get("/")
async def root():
    return {
        "message": "AI TTS Microservice",
        "version": "1.0.0",
        "status": "running",
        "service_ready": tts_service is not None
    }

@app.get("/voices")
async def get_available_voices():
    """Get list of available voices"""
    if not tts_service:
        raise HTTPException(status_code=503, detail="TTS service not ready")
    
    return {
        "voices": tts_service.available_voices,
        "default": "female_calm"
    }

@app.post("/generate-speech")
async def generate_speech(request: TTSRequest, background_tasks: BackgroundTasks):
    """Generate speech from text"""
    if not tts_service:
        raise HTTPException(status_code=503, detail="TTS service not ready")
    
    try:
        # Validate request
        if not request.text or not request.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        # Generate speech
        audio_data = tts_service.generate_speech(
            text=request.text,
            voice=request.voice,
            speed=request.speed
        )
        
        # Return audio as streaming response
        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=speech.wav",
                "Content-Length": str(len(audio_data))
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        if not tts_service:
            return {
                "status": "unhealthy",
                "reason": "TTS service not initialized"
            }
        
        # Check if at least one model is loaded
        if not tts_service.models:
            return {
                "status": "unhealthy",
                "reason": "No models loaded"
            }
        
        return {
            "status": "healthy",
            "models_loaded": len(tts_service.models),
            "available_voices": list(tts_service.available_voices.keys())
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "reason": str(e)
        }

@app.options("/generate-speech")
async def options_generate_speech():
    """Handle OPTIONS request for CORS"""
    return {"status": "ok"}

@app.exception_handler(500)
async def internal_server_error_handler(request, exc):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {exc}")
    return {"detail": "Internal server error"}

@app.exception_handler(503)
async def service_unavailable_handler(request, exc):
    """Handle 503 errors"""
    logger.error(f"Service unavailable: {exc}")
    return {"detail": "Service unavailable"}

# Create requirements.txt
echo "📝 Creating requirements.txt..."
cat > requirements.txt << 'EOF'
# Core web framework dependencies
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
python-multipart==0.0.6

# TTS Library and its core dependencies
TTS==0.22.0
numpy
scipy
torch
torchaudio

# Audio processing dependencies
librosa
soundfile
numba

# Additional required dependencies for TTS
mecab-python3
unidic-lite
jamo
pypinyin
jieba
bangla
bnnumerizer
bnunicodenormalizer

# System dependencies
packaging
pyyaml
inflect
tqdm
matplotlib
pandas

# Optional but recommended for better performance
psutil
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
    scipy==1.9.3 \
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
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-keep-alive", "30"]
EOF

# Create render.yaml
echo "📝 Creating render.yaml..."
cat > render.yaml << 'EOF'
services:
  - type: web
    name: ai-tts-service
    env: python
    buildCommand: |
      apt-get update && apt-get install -y --no-install-recommends \
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
      && pip install -r requirements.txt
    startCommand: "uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1 --timeout-keep-alive 30"
    healthCheckPath: /health
    # Add memory optimization settings
    envVars:
      - key: PYTORCH_CUDA_ALLOC_CONF
        value: max_split_size_mb:128
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
EOF

# Make the script executable
chmod +x setup.sh

echo "✅ Setup script created successfully!"
echo ""
echo "To use the setup script:"
echo "1. Save it as 'setup.sh'"
echo "2. Make it executable: chmod +x setup.sh"
echo "3. Run it: ./setup.sh"