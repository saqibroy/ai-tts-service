from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import io
import os
import logging
from typing import Optional
import gc
import asyncio
from contextlib import asynccontextmanager
import psutil
from google.cloud import texttospeech
from google.auth.exceptions import DefaultCredentialsError

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

def verify_google_credentials():
    """Verify Google Cloud credentials are properly configured"""
    credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if not credentials_path:
        raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable is not set")
    
    if not os.path.exists(credentials_path):
        raise ValueError(f"Credentials file not found at {credentials_path}")
    
    if not os.access(credentials_path, os.R_OK):
        raise ValueError(f"Credentials file at {credentials_path} is not readable")
    
    logger.info(f"Found credentials file at {credentials_path}")
    return True

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global tts_service
    try:
        logger.info(f"Starting up - Memory usage: {get_memory_usage():.1f}MB")
        
        # Verify credentials before initializing service
        verify_google_credentials()
        
        tts_service = TTSService()
        logger.info(f"TTS Service initialized - Memory usage: {get_memory_usage():.1f}MB")
    except ValueError as e:
        logger.error(f"Credentials error: {str(e)}")
        tts_service = None
        raise HTTPException(
            status_code=500,
            detail=f"Google Cloud credentials error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to initialize TTS service: {str(e)}")
        tts_service = None
        raise HTTPException(
            status_code=500,
            detail=f"Service initialization failed: {str(e)}"
        )
    
    yield
    
    # Shutdown
    if tts_service:
        logger.info("Cleaning up TTS Service...")
        tts_service.cleanup()

app = FastAPI(
    title="Google Cloud TTS Microservice",
    version="1.0.0",
    description="Memory-optimized Text-to-Speech microservice using Google Cloud TTS",
    lifespan=lifespan
)

# CORS configuration - Updated to match frontend requirements
origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://ssohail.com",
    "https://www.ssohail.com",
    "https://your-domain.com",  # Add your production domain
    "https://www.your-domain.com"  # Add your production domain with www
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True, # Crucial: Allow credentials
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Length", "Content-Type", "Content-Disposition"],
    max_age=3600
)

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "en-US-Standard-C"
    speed: Optional[float] = 1.0
    pitch: Optional[float] = 0.0

class TTSService:
    def __init__(self):
        self.client = texttospeech.TextToSpeechClient()
        
        # Define available voices with their properties - Updated to match frontend expectations
        self.available_voices = {
            "en-US-Standard-C": {
                "language_code": "en-US",
                "name": "en-US-Standard-C",
                "ssml_gender": texttospeech.SsmlVoiceGender.FEMALE,
                "description": "Standard female voice"
            },
            "en-GB-Standard-B": {
                "language_code": "en-GB",
                "name": "en-GB-Standard-B",
                "ssml_gender": texttospeech.SsmlVoiceGender.MALE,
                "description": "British male voice"
            },
            # Additional voices for better variety
            "en-US-Wavenet-D": {
                "language_code": "en-US",
                "name": "en-US-Wavenet-D",
                "ssml_gender": texttospeech.SsmlVoiceGender.MALE,
                "description": "WaveNet male voice (deep)"
            },
            "en-GB-Standard-A": {
                "language_code": "en-GB",
                "name": "en-GB-Standard-A",
                "ssml_gender": texttospeech.SsmlVoiceGender.FEMALE,
                "description": "British female voice"
            },
            "en-AU-Standard-A": {
                "language_code": "en-AU",
                "name": "en-AU-Standard-A",
                "ssml_gender": texttospeech.SsmlVoiceGender.FEMALE,
                "description": "Australian female voice"
            }
        }
        
        logger.info(f"TTSService initialized - Memory: {get_memory_usage():.1f}MB")
    
    def generate_speech(self, text: str, voice: str = "en-US-Standard-C", speed: float = 1.0, pitch: float = 0.0) -> bytes:
        """Generate speech using Google Cloud TTS"""
        try:
            logger.info(f"Starting speech generation - Memory: {get_memory_usage():.1f}MB")
            
            # Input validation
            if not text or not text.strip():
                raise HTTPException(status_code=400, detail="Text cannot be empty")
            
            # Text length limit - increased for better summaries
            max_length = 1000  # Increased from 500 to handle longer summaries
            if len(text) > max_length:
                text = text[:max_length]
                logger.warning(f"Text truncated to {max_length} characters")
            
            text = text.strip()
            
            # Validate voice
            if voice not in self.available_voices:
                logger.warning(f"Invalid voice '{voice}', using en-US-Standard-C")
                voice = "en-US-Standard-C"
            
            # Validate speed and pitch
            speed = max(0.25, min(4.0, float(speed)))
            pitch = max(-20.0, min(20.0, float(pitch)))
            
            # Get voice configuration
            voice_config = self.available_voices[voice]
            
            # Set the text input to be synthesized
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            # Build the voice request
            voice_params = texttospeech.VoiceSelectionParams(
                language_code=voice_config["language_code"],
                name=voice_config["name"],
                ssml_gender=voice_config["ssml_gender"]
            )
            
            # Select the type of audio file - Changed to MP3 for better compression and compatibility
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,  # Changed from LINEAR16 to MP3
                speaking_rate=speed,
                pitch=pitch
            )
            
            # Perform the text-to-speech request
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=voice_params,
                audio_config=audio_config
            )
            
            logger.info(f"Successfully generated {len(response.audio_content)} bytes - Final memory: {get_memory_usage():.1f}MB")
            
            # Force garbage collection after generation
            gc.collect()
            
            return response.audio_content
            
        except Exception as e:
            logger.error(f"Speech generation failed: {str(e)}")
            if "GOOGLE_APPLICATION_CREDENTIALS" in str(e):
                raise HTTPException(
                    status_code=500,
                    detail="Google Cloud credentials not properly configured. Please ensure GOOGLE_APPLICATION_CREDENTIALS environment variable is set correctly."
                )
            raise HTTPException(
                status_code=500,
                detail=f"Speech generation failed: {str(e)}"
            )
    
    def cleanup(self):
        """Cleanup resources"""
        try:
            gc.collect()
            logger.info("TTS Service cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

@app.get("/")
async def root():
    return {
        "message": "Google Cloud TTS Microservice is running",
        "version": "1.0.0",
        "status": "healthy" if tts_service else "unhealthy"
    }

@app.get("/voices")
async def get_available_voices():
    """Get list of available voices - Updated to match frontend expectations"""
    if not tts_service:
        raise HTTPException(status_code=503, detail="TTS service not initialized")
    
    voices = []
    for voice_id, config in tts_service.available_voices.items():
        voices.append({
            "id": voice_id,
            "language_code": config["language_code"],
            "name": config["name"],
            "gender": config["ssml_gender"].name,  # Convert enum to string
            "description": config["description"]
        })
    
    return {"voices": voices}

@app.post("/generate-speech")
async def generate_speech(request: TTSRequest, background_tasks: BackgroundTasks):
    """Generate speech from text"""
    if not tts_service:
        raise HTTPException(status_code=503, detail="TTS service not initialized")
    
    try:
        audio_data = tts_service.generate_speech(
            text=request.text,
            voice=request.voice,
            speed=request.speed,
            pitch=request.pitch
        )
        
        # Add cleanup task
        background_tasks.add_task(gc.collect)
        
        # Updated to return MP3 instead of WAV
        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type="audio/mpeg",  # Changed from audio/wav to audio/mpeg
            headers={
                "Content-Disposition": "attachment; filename=speech.mp3",  # Changed extension
                "Content-Length": str(len(audio_data)),
                "Cache-Control": "no-cache"  # Prevent caching issues
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating speech: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if not tts_service:
        return {
            "status": "unhealthy",
            "message": "TTS service not initialized",
            "memory_usage_mb": get_memory_usage(),
            "service_available": False
        }
    
    return {
        "status": "healthy",
        "message": "Google Cloud TTS service is running",
        "memory_usage_mb": get_memory_usage(),
        "service_available": True,
        "available_voices": len(tts_service.available_voices)
    }

@app.get("/memory")
async def memory_info():
    """Get memory usage information"""
    return {
        "memory_usage_mb": get_memory_usage(),
        "message": "Memory usage is monitored for optimization"
    }

@app.post("/cleanup")
async def force_cleanup():
    """Force cleanup of resources"""
    if not tts_service:
        raise HTTPException(status_code=503, detail="TTS service not initialized")
    
    try:
        tts_service.cleanup()
        return {"message": "Cleanup completed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.options("/generate-speech")
async def options_generate_speech():
    """Handle OPTIONS request for CORS"""
    return {}

@app.exception_handler(500)
async def internal_server_error_handler(request, exc):
    logger.error(f"Internal server error: {str(exc)}")
    return {"detail": str(exc)}

@app.exception_handler(503)
async def service_unavailable_handler(request, exc):
    logger.error(f"Service unavailable: {str(exc)}")
    return {"detail": str(exc)}

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