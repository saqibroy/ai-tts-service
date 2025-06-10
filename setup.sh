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
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import io
import os
import torch
import tempfile
from TTS.api import TTS
import logging
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI TTS Microservice", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "en_speaker_0"
    speed: Optional[float] = 1.0
    model: Optional[str] = "tts_models/en/ljspeech/tacotron2-DDC"

class TTSService:
    def __init__(self):
        self.models = {}
        self.available_voices = {
            "female_calm": {
                "model": "tts_models/en/ljspeech/tacotron2-DDC",
                "speaker": None,
                "description": "Female, calm and clear"
            },
            "female_expressive": {
                "model": "tts_models/en/vctk/vits",
                "speaker": "p225",  # Female speaker
                "description": "Female, expressive"
            },
            "male_deep": {
                "model": "tts_models/en/vctk/vits",
                "speaker": "p226",  # Male speaker
                "description": "Male, deep voice"
            },
            "female_young": {
                "model": "tts_models/en/vctk/vits",
                "speaker": "p231",  # Young female
                "description": "Female, young and energetic"
            },
            "male_british": {
                "model": "tts_models/en/vctk/vits",
                "speaker": "p237",  # British male
                "description": "Male, British accent"
            },
            "female_american": {
                "model": "tts_models/en/vctk/vits",
                "speaker": "p232",  # American female
                "description": "Female, American accent"
            }
        }
        
    def get_model(self, model_name: str):
        """Load and cache TTS model"""
        if model_name not in self.models:
            try:
                logger.info(f"Loading model: {model_name}")
                # Use GPU if available, otherwise CPU
                device = "cuda" if torch.cuda.is_available() else "cpu"
                self.models[model_name] = TTS(model_name).to(device)
                logger.info(f"Model loaded successfully on {device}")
            except Exception as e:
                logger.error(f"Failed to load model {model_name}: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Failed to load TTS model: {str(e)}")
        
        return self.models[model_name]
    
    def generate_speech(self, text: str, voice: str = "female_calm", speed: float = 1.0) -> bytes:
        """Generate speech from text"""
        if voice not in self.available_voices:
            voice = "female_calm"  # Default fallback
            
        voice_config = self.available_voices[voice]
        model = self.get_model(voice_config["model"])
        
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                # Generate speech
                if voice_config["speaker"]:
                    # For multi-speaker models
                    model.tts_to_file(
                        text=text,
                        speaker=voice_config["speaker"],
                        file_path=tmp_file.name,
                        speed=speed
                    )
                else:
                    # For single speaker models
                    model.tts_to_file(
                        text=text,
                        file_path=tmp_file.name,
                        speed=speed
                    )
                
                # Read the generated audio file
                with open(tmp_file.name, 'rb') as audio_file:
                    audio_data = audio_file.read()
                
                # Clean up temp file
                os.unlink(tmp_file.name)
                
                return audio_data
                
        except Exception as e:
            logger.error(f"Speech generation failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Speech generation failed: {str(e)}")

# Initialize TTS service
tts_service = TTSService()

@app.get("/")
async def root():
    return {
        "message": "AI TTS Microservice",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/voices")
async def get_available_voices():
    """Get list of available voices"""
    return {
        "voices": tts_service.available_voices,
        "default": "female_calm"
    }

@app.post("/generate-speech")
async def generate_speech(request: TTSRequest):
    """Generate speech from text"""
    try:
        # Validate text length
        if len(request.text) > 5000:
            raise HTTPException(status_code=400, detail="Text too long. Maximum 5000 characters.")
        
        if not request.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty.")
        
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
        # Simple health check - try to load a model
        device = "cuda" if torch.cuda.is_available() else "cpu"
        return {
            "status": "healthy",
            "device": device,
            "models_loaded": len(tts_service.models)
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
EOF

# Create requirements.txt
echo "📝 Creating requirements.txt..."
cat > requirements.txt << 'EOF'
numpy==1.22.0
torch==2.1.0
torchaudio==2.1.0
TTS==0.20.6
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
python-multipart==0.0.6
scipy==1.11.4
librosa==0.9.2
soundfile==0.12.1
EOF

# Create Dockerfile
echo "📝 Creating Dockerfile..."
cat > Dockerfile << 'EOF'
FROM python:3.10-slim-buster

# Prevent Python from writing .pyc files to disc
ENV PYTHONDONTWRITEBYTECODE 1

# Ensure output is sent straight to terminal
ENV PYTHONUNBUFFERED 1

# System dependencies for Coqui TTS and general compilation (best practice)
# We need libssl-dev for Python's SSL module to work correctly with pip via HTTPS
# and build-essential for general compilation of certain Python packages.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libssl-dev \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements.txt
# Using COPY --link for potentially faster builds if requirements.txt changes often
COPY --link requirements.txt .

# Upgrade pip to the latest version as suggested by previous logs
# Then install Python dependencies
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose the port your FastAPI application listens on
EXPOSE 8000

# Define the command to run your FastAPI application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

# Create render.yaml
echo "📝 Creating render.yaml..."
cat > render.yaml << 'EOF'
# Render.com service definition for ai-tts-service
# NOTE: Free instance type spins down after 15 minutes of inactivity. Upgrade for always-on service.
services:
  - type: web
    name: ai-tts-service
    env: python
    buildCommand: "pip install -r requirements.txt"
    startCommand: "uvicorn main:app --host 0.0.0.0 --port $PORT"
    healthCheckPath: /health
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