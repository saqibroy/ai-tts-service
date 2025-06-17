# 🎙️ Google Cloud Text-to-Speech Microservice

A high-quality text-to-speech microservice built with FastAPI and Google Cloud Text-to-Speech API, designed to provide professional neural voices with minimal resource usage.

## 🌟 Features

- **🤖 High-Quality Voices**: Multiple neural voices from Google Cloud TTS
- **🎛️ Voice Customization**: Adjustable speed and pitch
- **⚡ Fast Generation**: Cloud-based processing for quick audio generation
- **🎵 Speed Control**: Adjustable playback speed (0.25x to 4.0x)
- **🎯 Pitch Control**: Adjustable pitch (-20.0 to 20.0)
- **📁 Audio Download**: Download generated audio files in WAV format
- **🚀 Free Deployment**: Runs on Render's generous free tier
- **🔌 Easy Integration**: Simple REST API for seamless integration
- **📱 CORS Enabled**: Ready for web application integration

## 🎭 Available Voices

| Voice ID | Description | Gender | Type |
|----------|-------------|---------|-------|
| `en-US-Standard-C` | Standard female voice | Female | Standard |
| `en-US-Wavenet-A` | WaveNet male voice | Male | WaveNet |
| `en-US-Neural2-C` | Neural2 female voice | Female | Neural2 |
| `en-GB-Standard-B` | British male voice | Male | Standard |

## 🚀 Quick Start

### Option 1: Use Setup Script (Recommended)
```bash
curl -O https://raw.githubusercontent.com/<yourusername>/google-cloud-tts-service/main/setup.sh
chmod +x setup.sh
./setup.sh
```

### Option 2: Manual Setup
```bash
# Clone the repository
git clone https://github.com/<yourusername>/google-cloud-tts-service.git
cd google-cloud-tts-service

# Install dependencies
pip install -r requirements.txt

# Set up Google Cloud credentials
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/credentials.json"

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
  "voices": [
    {
      "id": "en-US-Standard-C",
      "language_code": "en-US",
      "name": "en-US-Standard-C",
      "gender": "FEMALE",
      "description": "Standard female voice"
    }
  ]
}
```

### Generate Speech
```http
POST /generate-speech
Content-Type: application/json

{
  "text": "Hello, this is a test of the text-to-speech service!",
  "voice": "en-US-Standard-C",
  "speed": 1.0,
  "pitch": 0.0
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
  "message": "Google Cloud TTS service is running",
  "memory_usage_mb": 45.2
}
```

## 🚀 Deployment

### Deploy to Render.com (Free)

1. **Create a Render Account**: Go to [Render.com](https://render.com) and sign up.
2. **Push Your Code to GitHub**:
   ```bash
   git remote add origin https://github.com/<yourusername>/google-cloud-tts-service.git
   git branch -M main
   git push -u origin main
   ```
3. **Deploy on Render**:
   - Go to the Render Dashboard
   - Click "New Web Service"
   - Connect your GitHub repository
   - Upload your Google Cloud credentials as a secret file named `google-credentials.json`
   - Render will auto-detect the `render.yaml` file and deploy your service
4. **Get Service URL**: Render provides a URL like `https://your-service-name.onrender.com`

#### `render.yaml` Example
```yaml
services:
  - type: web
    name: google-cloud-tts-service
    env: python
    buildCommand: "pip install -r requirements.txt"
    startCommand: "uvicorn main:app --host 0.0.0.0 --port $PORT"
    healthCheckPath: /health
    envVars:
      - key: GOOGLE_APPLICATION_CREDENTIALS
        value: "/etc/secrets/google-credentials.json"
```

## 📊 Usage Limits

### Render Free Tier
- ✅ 750 hours/month execution time
- ✅ 100 GB/month bandwidth
- ✅ 512 MB RAM, 0.5 vCPU
- ⚠️ Spins down after 15 minutes of inactivity (cold start ~30s)

### Google Cloud TTS Free Tier
- ✅ 4 million characters per month
- ✅ Multiple voice types (Standard, WaveNet, Neural2)
- ✅ High-quality audio output

### Service Limits
- Max text length: 500 characters per request
- Audio format: WAV (high quality)
- Response time: 1-3 seconds

## 🔧 Monitoring & Maintenance

### Keep Service Awake
Add to your Next.js app to prevent sleeping (ping every 10-14 minutes):

```javascript
// Ping every 12 minutes
setInterval(async () => {
  try {
    await fetch(`${process.env.NEXT_PUBLIC_TTS_SERVICE_URL}/health`);
  } catch (error) {
    console.log('Keep-alive ping failed');
  }
}, 12 * 60 * 1000);
```

### Monitoring
```bash
# Check service health
curl https://your-service-name.onrender.com/health

# View logs
# Go to the Render Dashboard > your service > Logs
```

## 🛠️ Development

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set up Google Cloud credentials
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/credentials.json"

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
  -d '{"text":"Hello world","voice":"en-US-Standard-C"}' \
  --output test.wav
```

## 🔒 Security Considerations

- **Rate Limiting**: Consider adding rate limiting for production
- **CORS**: Configure CORS origins for your specific domains
- **Input Validation**: Text length and content validation included
- **API Authentication**: Add API keys for production use
- **Google Cloud Credentials**: Keep your credentials secure and never commit them to version control

## 🐛 Troubleshooting

### Common Issues

**Service won't start**
- Check Python version (3.10 required)
- Verify all dependencies in requirements.txt
- Check Render logs for errors
- Ensure Google Cloud credentials are properly configured

**Audio generation fails**
- Ensure text is under 500 characters
- Check if Google Cloud credentials are valid
- Verify voice parameter is valid

**CORS errors**
- Update allowed origins in main.py
- Ensure your domain is whitelisted

## 📈 Performance

- **Response Time**: 1-3 seconds
- **Audio Quality**: High-quality WAV
- **Memory Usage**: ~50MB (much lower than local TTS)
- **Scalability**: Cloud-based processing

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Google Cloud Text-to-Speech](https://cloud.google.com/text-to-speech) - High-quality TTS service
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Render](https://render.com/) - Fantastic deployment platform

## 📞 Support

- Create an [issue](https://github.com/<yourusername>/google-cloud-tts-service/issues) for bugs
- Check [discussions](https://github.com/<yourusername>/google-cloud-tts-service/discussions) for questions
- Star ⭐ the repo if you find it useful!

---

**Made with ❤️ for better web audio experiences**