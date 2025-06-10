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
import psutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variable to store TTS service
tts_service = None

def get_memory_usage():
    """Get current memory usage in MB"""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global tts_service
    try:
        logger.info(f"Starting up - Memory usage: {get_memory_usage():.1f}MB")
        tts_service = TTSService()
        logger.info(f"TTS Service initialized - Memory usage: {get_memory_usage():.1f}MB")
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
    description="Memory-optimized Text-to-Speech microservice",
    lifespan=lifespan
)

# CORS configuration
origins = [
    "http://localhost:3000",
    "https://ssohail.com",
    "https://www.ssohail.com",
    "*"  # Allow all for development
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Length", "Content-Type", "Content-Disposition"],
    max_age=3600
)

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "lightweight"
    speed: Optional[float] = 1.0

class TTSService:
    def __init__(self):
        self.current_model = None
        self.current_model_name = None
        self.model_lock = threading.Lock()
        
        # Use only lightweight models that fit in 512MB
        self.available_voices = {
            "lightweight": {
                "model": "tts_models/en/ljspeech/tacotron2-DDC_ph",
                "description": "Lightweight female voice"
            },
            "fast": {
                "model": "tts_models/en/ljspeech/speedy-speech",
                "description": "Fast generation female voice"
            }
        }
        
        logger.info(f"TTSService initialized - Memory: {get_memory_usage():.1f}MB")
        # DO NOT preload models - load on demand only
    
    def get_model(self, model_name: str):
        """Load model on-demand with aggressive memory management"""
        with self.model_lock:
            try:
                # If we already have this model loaded, return it
                if self.current_model and self.current_model_name == model_name:
                    return self.current_model
                
                # Clear any existing model first
                if self.current_model:
                    logger.info(f"Clearing existing model to free memory")
                    del self.current_model
                    self.current_model = None
                    self.current_model_name = None
                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                
                logger.info(f"Loading model: {model_name} - Memory before: {get_memory_usage():.1f}MB")
                
                # Import TTS here to avoid memory usage during startup
                from TTS.api import TTS
                
                # Force CPU usage and minimal memory allocation
                device = "cpu"
                torch.set_num_threads(1)  # Limit CPU threads
                
                # Load model with minimal memory footprint
                self.current_model = TTS(model_name, progress_bar=False).to(device)
                self.current_model_name = model_name
                
                logger.info(f"Model loaded successfully - Memory after: {get_memory_usage():.1f}MB")
                
                # Check if we're close to memory limit
                if get_memory_usage() > 450:  # 450MB threshold
                    logger.warning(f"High memory usage: {get_memory_usage():.1f}MB")
                
                return self.current_model
                
            except Exception as e:
                logger.error(f"Failed to load model {model_name}: {str(e)}")
                # Clean up on failure
                if self.current_model:
                    del self.current_model
                    self.current_model = None
                    self.current_model_name = None
                    gc.collect()
                raise HTTPException(
                    status_code=500, 
                    detail=f"Model loading failed - try again in a moment"
                )
    
    def generate_speech(self, text: str, voice: str = "lightweight", speed: float = 1.0) -> bytes:
        """Generate speech with aggressive memory management"""
        try:
            logger.info(f"Starting speech generation - Memory: {get_memory_usage():.1f}MB")
            
            # Input validation
            if not text or not text.strip():
                raise HTTPException(status_code=400, detail="Text cannot be empty")
            
            # Strict text length limit for memory management
            max_length = 500  # Reduced from 1000
            if len(text) > max_length:
                text = text[:max_length]
                logger.warning(f"Text truncated to {max_length} characters")
            
            text = text.strip()
            
            # Validate voice
            if voice not in self.available_voices:
                logger.warning(f"Invalid voice '{voice}', using lightweight")
                voice = "lightweight"
            
            speed = max(0.5, min(2.0, float(speed)))
            
            # Get voice configuration
            voice_config = self.available_voices[voice]
            
            # Load model (this will clear any existing model)
            model = self.get_model(voice_config["model"])
            
            logger.info(f"Model loaded - Memory: {get_memory_usage():.1f}MB")
            
            # Generate speech with temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                try:
                    logger.info(f"Generating speech for {len(text)} characters")
                    
                    # Generate with minimal parameters
                    model.tts_to_file(
                        text=text,
                        file_path=tmp_file.name
                    )
                    
                    logger.info(f"Speech generated - Memory: {get_memory_usage():.1f}MB")
                    
                    # Read the generated audio file
                    if not os.path.exists(tmp_file.name):
                        raise Exception("Audio file was not generated")
                    
                    with open(tmp_file.name, 'rb') as audio_file:
                        audio_data = audio_file.read()
                    
                    if not audio_data:
                        raise Exception("Generated audio file is empty")
                    
                    logger.info(f"Successfully generated {len(audio_data)} bytes - Final memory: {get_memory_usage():.1f}MB")
                    
                    # Force garbage collection after generation
                    gc.collect()
                    
                    return audio_data
                    
                finally:
                    # Clean up temp file
                    try:
                        if os.path.exists(tmp_file.name):
                            os.unlink(tmp_file.name)
                    except Exception as e:
                        logger.warning(f"Failed to clean up temp file: {e}")
                        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Speech generation failed: {str(e)}")
            # Force cleanup on error
            gc.collect()
            raise HTTPException(
                status_code=500, 
                detail=f"Speech generation failed: {str(e)}"
            )
    
    def cleanup(self):
        """Aggressive cleanup"""
        try:
            with self.model_lock:
                if self.current_model:
                    del self.current_model
                    self.current_model = None
                    self.current_model_name = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("TTS Service cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

@app.get("/")
async def root():
    memory_mb = get_memory_usage()
    return {
        "message": "AI TTS Microservice",
        "version": "1.0.0",
        "status": "running",
        "service_ready": tts_service is not None,
        "memory_usage_mb": round(memory_mb, 1),
        "memory_status": "healthy" if memory_mb < 400 else "high" if memory_mb < 480 else "critical"
    }

@app.get("/voices")
async def get_available_voices():
    """Get list of available voices"""
    if not tts_service:
        raise HTTPException(status_code=503, detail="TTS service not ready")
    
    return {
        "voices": tts_service.available_voices,
        "default": "lightweight",
        "memory_usage_mb": round(get_memory_usage(), 1)
    }

@app.post("/generate-speech")
async def generate_speech(request: TTSRequest, background_tasks: BackgroundTasks):
    """Generate speech from text with memory monitoring"""
    if not tts_service:
        raise HTTPException(status_code=503, detail="TTS service not ready")
    
    # Check memory before processing
    memory_before = get_memory_usage()
    if memory_before > 480:  # 480MB threshold
        # Force cleanup and wait
        gc.collect()
        await asyncio.sleep(1)
        memory_after_gc = get_memory_usage()
        logger.warning(f"High memory usage before request: {memory_before:.1f}MB, after GC: {memory_after_gc:.1f}MB")
        
        if memory_after_gc > 480:
            raise HTTPException(
                status_code=503, 
                detail="Service temporarily overloaded - please try again in a moment"
            )
    
    try:
        # Validate request
        if not request.text or not request.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        if len(request.text) > 500:
            logger.warning("Text length exceeds limit, will be truncated")
        
        logger.info(f"Processing TTS request: {len(request.text)} characters, voice: {request.voice}")
        
        # Generate speech
        audio_data = tts_service.generate_speech(
            text=request.text.strip(),
            voice=request.voice or "lightweight",
            speed=request.speed or 1.0
        )
        
        # Add aggressive cleanup task
        background_tasks.add_task(lambda: (gc.collect(), logger.info(f"Background cleanup - Memory: {get_memory_usage():.1f}MB")))
        
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
        # Force cleanup on error
        gc.collect()
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    """Comprehensive health check with memory monitoring"""
    try:
        memory_mb = get_memory_usage()
        
        # Determine status based on memory usage
        if memory_mb > 500:
            status = "critical"
        elif memory_mb > 450:
            status = "warning"
        elif tts_service is None:
            status = "service_not_ready"
        else:
            status = "healthy"
        
        health_data = {
            "status": status,
            "memory_usage_mb": round(memory_mb, 1),
            "memory_limit_mb": 512,
            "memory_available_mb": round(512 - memory_mb, 1),
            "service_ready": tts_service is not None,
            "current_model_loaded": tts_service.current_model_name if tts_service else None,
            "available_voices": list(tts_service.available_voices.keys()) if tts_service else []
        }
        
        return health_data
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

@app.get("/memory")
async def memory_info():
    """Detailed memory information for debugging"""
    try:
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        return {
            "memory_usage_mb": round(memory_info.rss / 1024 / 1024, 1),
            "memory_percent": round(process.memory_percent(), 1),
            "virtual_memory_mb": round(memory_info.vms / 1024 / 1024, 1),
            "available_system_memory_mb": round(psutil.virtual_memory().available / 1024 / 1024, 1),
            "current_model": tts_service.current_model_name if tts_service and tts_service.current_model else None
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/cleanup")
async def force_cleanup():
    """Force memory cleanup - use sparingly"""
    try:
        if tts_service:
            with tts_service.model_lock:
                if tts_service.current_model:
                    del tts_service.current_model
                    tts_service.current_model = None
                    tts_service.current_model_name = None
        
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        return {
            "status": "cleanup_completed",
            "memory_usage_mb": round(get_memory_usage(), 1)
        }
    except Exception as e:
        return {"error": str(e)}

@app.options("/generate-speech")
async def options_generate_speech():
    """Handle CORS preflight requests"""
    return {"message": "CORS preflight handled"}

# Error handlers
@app.exception_handler(500)
async def internal_server_error_handler(request, exc):
    logger.error(f"Internal server error: {exc}")
    gc.collect()  # Cleanup on errors
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