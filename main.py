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
        
        if len(request.text) > 1000:
            logger.warning("Text length exceeds limit, will be truncated")
        
        logger.info(f"Processing TTS request: {len(request.text)} characters, voice: {request.voice}")
        
        # Generate speech
        audio_data = tts_service.generate_speech(
            text=request.text.strip(),
            voice=request.voice or "female_calm",
            speed=request.speed or 1.0
        )
        
        # Add cleanup task
        background_tasks.add_task(gc.collect)
        
        # Return audio as streaming response
        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=speech.wav",
                "Content-Length": str(len(audio_data)),
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in generate_speech: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    """Comprehensive health check endpoint"""
    try:
        status = "healthy" if tts_service else "service_not_ready"
        device = "cuda" if torch.cuda.is_available() else "cpu"
        models_loaded = len(tts_service.models) if tts_service else 0
        
        # Check available memory
        import psutil
        memory = psutil.virtual_memory()
        
        health_data = {
            "status": status,
            "device": device,
            "models_loaded": models_loaded,
            "available_voices": len(tts_service.available_voices) if tts_service else 0,
            "memory": {
                "available_mb": round(memory.available / 1024 / 1024, 2),
                "used_percent": memory.percent
            },
            "torch_cuda_available": torch.cuda.is_available(),
            "service_ready": tts_service is not None
        }
        
        return health_data
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

@app.options("/generate-speech")
async def options_generate_speech():
    """Handle CORS preflight requests"""
    return {"message": "CORS preflight handled"}

# Error handlers
@app.exception_handler(500)
async def internal_server_error_handler(request, exc):
    logger.error(f"Internal server error: {exc}")
    return {"error": "Internal server error", "detail": str(exc)}

@app.exception_handler(503)
async def service_unavailable_handler(request, exc):
    logger.error(f"Service unavailable: {exc}")
    return {"error": "Service temporarily unavailable", "detail": str(exc)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting server on port {port}")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        workers=1,
        timeout_keep_alive=30,
        access_log=True
    )