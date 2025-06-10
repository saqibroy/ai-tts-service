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

origins = [
    "http://localhost:3000",  # Your Next.js local development server
    "https://ssohail.com",    # Your Next.js production domain
    # Add any other domains that need to access your API
]

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Configure this properly in production
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
