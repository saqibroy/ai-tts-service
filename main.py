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
import gc
import threading

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI TTS Microservice", version="1.0.0")

# More permissive CORS for debugging
origins = [
    "*",  # Allow all origins for now - restrict in production
]

# CORS middleware
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
        # Reduced voice options for better memory management
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
        
    def get_model(self, model_name: str):
        """Load and cache TTS model with memory management"""
        with self.model_lock:
            if model_name not in self.models:
                try:
                    logger.info(f"Loading model: {model_name}")
                    
                    # Clear any existing models to free memory
                    if len(self.models) > 0:
                        logger.info("Clearing existing models to free memory")
                        for old_model in self.models.values():
                            del old_model
                        self.models.clear()
                        gc.collect()
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                    
                    # Use CPU for better stability on free tier
                    device = "cpu"  # Force CPU to avoid GPU memory issues
                    self.models[model_name] = TTS(model_name).to(device)
                    logger.info(f"Model loaded successfully on {device}")
                    
                except Exception as e:
                    logger.error(f"Failed to load model {model_name}: {str(e)}")
                    raise HTTPException(status_code=500, detail=f"Failed to load TTS model: {str(e)}")
            
            return self.models[model_name]
    
    def generate_speech(self, text: str, voice: str = "female_calm", speed: float = 1.0) -> bytes:
        """Generate speech from text with error handling"""
        try:
            # Limit text length for memory management
            if len(text) > 1000:  # Reduced from 5000
                text = text[:1000]
                logger.warning("Text truncated to 1000 characters")
            
            if voice not in self.available_voices:
                voice = "female_calm"  # Default fallback
                
            voice_config = self.available_voices[voice]
            model = self.get_model(voice_config["model"])
            
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                try:
                    # Generate speech with simple parameters
                    model.tts_to_file(
                        text=text,
                        file_path=tmp_file.name
                    )
                    
                    # Read the generated audio file
                    with open(tmp_file.name, 'rb') as audio_file:
                        audio_data = audio_file.read()
                    
                    logger.info(f"Successfully generated {len(audio_data)} bytes of audio")
                    return audio_data
                    
                finally:
                    # Clean up temp file
                    try:
                        os.unlink(tmp_file.name)
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"Speech generation failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Speech generation failed: {str(e)}")

# Initialize TTS service
try:
    tts_service = TTSService()
    logger.info("TTS Service initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize TTS service: {e}")
    tts_service = None

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
async def generate_speech(request: TTSRequest):
    """Generate speech from text"""
    if not tts_service:
        raise HTTPException(status_code=503, detail="TTS service not ready")
    
    try:
        # Validate text
        if not request.text or not request.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty.")
        
        if len(request.text) > 1000:  # Reduced limit
            logger.warning("Text too long, truncating...")
        
        logger.info(f"Processing TTS request: {len(request.text)} characters")
        
        # Generate speech
        audio_data = tts_service.generate_speech(
            text=request.text.strip(),
            voice=request.voice or "female_calm",
            speed=request.speed or 1.0
        )
        
        # Return audio as streaming response
        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=speech.wav",
                "Content-Length": str(len(audio_data)),
                "Access-Control-Allow-Origin": "*",  # Explicit CORS header
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "*"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in generate_speech: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        models_loaded = len(tts_service.models) if tts_service else 0
        
        return {
            "status": "healthy" if tts_service else "service_not_ready",
            "device": device,
            "models_loaded": models_loaded,
            "memory_info": {
                "available": True,
                "torch_cuda_available": torch.cuda.is_available()
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

# Handle preflight requests
@app.options("/generate-speech")
async def options_generate_speech():
    return {
        "message": "CORS preflight",
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)