# 🎙️ AI Text-to-Speech Microservice

A high-quality, AI-powered text-to-speech microservice built with FastAPI and Coqui TTS, designed to replace browser-based TTS with professional neural voices.

## 🌟 Features

- **🤖 Multiple AI Voices**: 6 different neural TTS voices with unique characteristics
- **🎛️ Voice Customization**: Female/male voices with different accents and styles
- **⚡ Fast Generation**: Optimized model caching for quick audio generation  
- **🎵 Speed Control**: Adjustable playback speed (0.5x to 2x)
- **📁 Audio Download**: Download generated audio files in WAV format
- **🚀 Free Deployment**: Runs on Railway's generous free tier
- **🔌 Easy Integration**: Simple REST API for seamless integration
- **📱 CORS Enabled**: Ready for web application integration

## 🎭 Available Voices

| Voice ID | Description | Gender | Style |
|----------|-------------|---------|-------|
| `female_calm` | Female, calm and clear | Female | Professional |
| `female_expressive` | Female, expressive | Female | Dynamic |
| `male_deep` | Male, deep voice | Male | Authoritative |
| `female_young` | Female, young and energetic | Female | Energetic |
| `male_british` | Male, British accent | Male | Sophisticated |
| `female_american` | Female, American accent | Female | Friendly |

## 🚀 Quick Start

### Option 1: Use Setup Script (Recommended)
```bash
curl -O https://raw.githubusercontent.com/yourusername/ai-tts-service/main/setup.sh
chmod +x setup.sh
./setup.sh
```

### Option 2: Manual Setup
```bash
# Clone the repository
git clone https://github.com/yourusername/ai-tts-service.git
cd ai-tts-service

# Install dependencies
pip install -r requirements.txt

# Run locally
uvicorn main:app --reload
```

## 🌐 API Endpoints

### Get Available Voices
```http
GET /voices
```

**Response:**
```json
{
  "voices": {
    "female_calm": {
      "model": "tts_models/en/ljspeech/tacotron2-DDC",
      "speaker": null,
      "description": "Female, calm and clear"
    }
  },
  "default": "female_calm"
}
```

### Generate Speech
```http
POST /generate-speech
Content-Type: application/json

{
  "text": "Hello, this is a test of the AI text-to-speech service!",
  "voice": "female_calm",
  "speed": 1.0
}
```

**Response:** Audio file (WAV format)

### Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "device": "cpu",
  "models_loaded": 2
}
```

## 🚀 Deployment

### Deploy to Railway (Free)

1. **Create Railway Account**: Go to [Railway.app](https://railway.app) and sign up

2. **Deploy from GitHub**:
   ```bash
   # Push your code to GitHub
   git remote add origin https://github.com/yourusername/ai-tts-service.git
   git push -u origin main
   
   # Deploy on Railway
   # - Create new project
   # - Connect GitHub repository  
   # - Railway auto-deploys
   ```

3. **Get Service URL**: Railway provides a URL like `https://your-service.railway.app`

### Alternative Platforms

<details>
<summary>Deploy to Render.com</summary>

```yaml
# render.yaml
services:
  - type: web
    name: ai-tts-service
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
```
</details>

<details>
<summary>Deploy to Fly.io</summary>

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Deploy
fly launch
fly deploy
```
</details>

## 🔧 Integration with Next.js

### 1. Environment Variables
Add to your `.env.local`:
```env
NEXT_PUBLIC_TTS_SERVICE_URL=https://your-service.railway.app
```

### 2. Update Your Component
Replace your existing `AudioSummaryPlayer` with the provided updated version that includes:
- AI voice selection dropdown
- Audio download functionality
- Real-time progress tracking
- Better error handling

### 3. Example Usage
```typescript
// In your React component
const generateAudio = async (text: string, voice: string = 'female_calm') => {
  const response = await fetch(`${process.env.NEXT_PUBLIC_TTS_SERVICE_URL}/generate-speech`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, voice, speed: 1.0 })
  });
  
  if (response.ok) {
    const audioBlob = await response.blob();
    const audioUrl = URL.createObjectURL(audioBlob);
    // Play or download the audio
  }
};
```

## 🎛️ Configuration

### Model Configuration
Modify `available_voices` in `main.py` to add custom voices:

```python
"custom_voice": {
    "model": "tts_models/en/vctk/vits",
    "speaker": "p243",
    "description": "Custom voice description"
}
```

### Performance Tuning
- **Memory**: Models are cached in memory for faster generation
- **GPU Support**: Automatically uses GPU if available (upgrade Railway plan)
- **Concurrent Requests**: Handles multiple requests efficiently

## 📊 Usage Limits

### Railway Free Tier
- ✅ 500 hours/month execution time
- ✅ $5 monthly credit
- ✅ 1GB RAM, 1 vCPU
- ⚠️ Sleeps after 1 hour inactivity

### Service Limits
- Max text length: 5,000 characters
- Audio format: WAV (high quality)
- Response time: 2-10 seconds (first request may be slower)

## 🔧 Monitoring & Maintenance

### Keep Service Awake
Add to your Next.js app to prevent sleeping:

```javascript
// Ping every 25 minutes
setInterval(async () => {
  try {
    await fetch(`${process.env.NEXT_PUBLIC_TTS_SERVICE_URL}/health`);
  } catch (error) {
    console.log('Keep-alive ping failed');
  }
}, 25 * 60 * 1000);
```

### Monitoring
```bash
# Check service health
curl https://your-service.railway.app/health

# View logs (Railway CLI)
railway logs --tail
```

## 🛠️ Development

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run with hot reload
uvicorn main:app --reload --port 8000

# Test endpoints
curl http://localhost:8000/voices
```

### Testing
```bash
# Test voice generation
curl -X POST http://localhost:8000/generate-speech \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world","voice":"female_calm"}' \
  --output test.wav
```

## 🔒 Security Considerations

- **Rate Limiting**: Consider adding rate limiting for production
- **CORS**: Configure CORS origins for your specific domains
- **Input Validation**: Text length and content validation included
- **API Authentication**: Add API keys for production use

## 🐛 Troubleshooting

### Common Issues

**Service won't start**
- Check Python version (3.10 required)
- Verify all dependencies in requirements.txt
- Check Railway logs for errors

**Audio generation fails**
- Ensure text is under 5,000 characters
- Check if service has enough memory
- Verify voice parameter is valid

**Long response times**
- First request loads models (30-60 seconds)
- Subsequent requests are much faster
- Consider upgrading to keep service warm

**CORS errors**
- Update allowed origins in main.py
- Ensure your domain is whitelisted

## 📈 Performance

- **First Request**: 30-60 seconds (model loading)
- **Subsequent Requests**: 2-5 seconds
- **Audio Quality**: 22kHz, 16-bit WAV
- **Model Size**: ~100-500MB per model
- **Memory Usage**: ~1-2GB with cached models

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Coqui TTS](https://github.com/coqui-ai/TTS) - Excellent open-source TTS library
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Railway](https://railway.app/) - Fantastic deployment platform

## 📞 Support

- Create an [issue](https://github.com/yourusername/ai-tts-service/issues) for bugs
- Check [discussions](https://github.com/yourusername/ai-tts-service/discussions) for questions
- Star ⭐ the repo if you find it useful!

---

**Made with ❤️ for better web audio experiences**