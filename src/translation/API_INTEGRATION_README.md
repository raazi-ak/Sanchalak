# 🔗 Sanchalak API Integration Guide

## Overview
This document describes the comprehensive integration between the Sanchalak Streamlit UI and the FastAPI backend services for audio transcription and text-to-speech functionality.

## 📁 Project Structure

```
translation/
├── api/                          # FastAPI Backend Services
│   ├── transcribe_routes.py     # Audio transcription endpoints
│   └── tts_routes.py            # Text-to-speech endpoints
├── streamlit_app/               # ✨ Main UI (INTEGRATED)
│   ├── app.py                   # Main Streamlit application
│   └── utils.py                 # API integration utilities
├── streamlit_old/               # ⚠️ Deprecated - can be removed
│   ├── app.py                   # Old version
│   └── utils.py                 # Old utilities
├── main.py                      # FastAPI application entry point
├── models.py                    # Pydantic models and schemas
├── transcribe.py               # Transcription service logic
└── tts.py                      # Text-to-speech service logic
```

## 🚀 API Integration Features

### ✅ Implemented Features

1. **Audio Transcription Integration**
   - Real-time speech-to-text processing
   - Multi-language support (10+ languages)
   - Automatic language detection
   - Confidence scoring
   - Error handling and recovery

2. **Text-to-Speech Integration**
   - Multi-language voice synthesis
   - Real-time audio generation
   - Audio file serving
   - Language-specific voice selection

3. **Health Monitoring**
   - Real-time API status checking
   - Endpoint availability monitoring
   - Detailed error reporting
   - Integration testing suite

4. **Enhanced User Experience**
   - Loading indicators
   - Error messages with context
   - Audio playback controls
   - Language-specific UI content

## 🔌 API Endpoints Used

### Transcription Service
```
POST /transcribe/
Content-Type: multipart/form-data

Request:
- file: Audio file (MP3, WAV, M4A, WebM)

Response:
{
  "task_id": "audio_12345678",
  "status": "COMPLETED" | "FAILED",
  "transcribed_text": "Transcribed text content",
  "translated_text": "Translated text (if applicable)",
  "detected_language": "hi",
  "confidence_score": 0.95,
  "processing_time": 2.34,
  "error_details": null
}
```

### Text-to-Speech Service
```
POST /tts/
Content-Type: application/json

Request:
{
  "text": "Text to convert to speech",
  "target_language": "hi"
}

Response:
{
  "status": "COMPLETED" | "FAILED",
  "translated_text": "Translated text",
  "audio_path": "tts_output_12345.mp3",
  "error_message": null
}
```

### Audio File Serving
```
GET /tts/audio/{filename}
Response: Audio file (audio/mpeg)
```

### Health Check
```
GET /health
Response:
{
  "status": "healthy",
  "service": "Sanchalak API"
}
```

## 🛠️ Setup and Configuration

### Environment Variables
```bash
# Backend URL configuration
BACKEND_URL=http://localhost:8000  # Default value
```

### Backend Dependencies
- FastAPI
- Azure Cognitive Services (for transcription/TTS)
- Pydantic
- Python-multipart

### Frontend Dependencies  
- Streamlit
- Requests
- Pydub
- Base64

## 🔧 API Integration Details

### 1. Transcription Integration (`utils.py`)
```python
def transcribe_audio(audio_bytes_io: io.BytesIO) -> dict:
    """Enhanced transcription with type safety and error handling"""
    - Input validation and format checking
    - API request with proper headers and timeout
    - Response validation and type conversion
    - Enhanced error handling with user-friendly messages
    - Metadata tracking for debugging
```

### 2. TTS Integration (`utils.py`)
```python
def tts_response(text: str, target_language: str) -> dict:
    """Enhanced TTS with validation and metadata"""
    - Language code validation
    - Text preprocessing and validation
    - API request with proper JSON payload
    - Response enhancement with metadata
    - Error handling with context
```

### 3. Health Monitoring (`utils.py`)
```python
def health_check() -> dict:
    """Comprehensive API health monitoring"""
    - Main API health verification
    - Individual endpoint testing
    - Performance monitoring
    - Detailed status reporting
    - Error categorization
```

### 4. Integration Testing (`utils.py`)
```python
def test_api_integration() -> dict:
    """Complete integration test suite"""
    - Health check validation
    - API info retrieval
    - TTS endpoint testing
    - Transcription capability verification
    - Comprehensive reporting
```

## 📊 UI Integration Features

### Real-time Status Display
- Sidebar API status dashboard
- Individual endpoint monitoring
- Color-coded status indicators
- Last checked timestamps

### Interactive Testing
- One-click API testing
- Detailed test results
- Integration report generation
- Error diagnosis tools

### Enhanced Error Handling
- User-friendly error messages
- Agricultural-themed messaging
- Context-aware error reporting
- Recovery suggestions

## 🌟 Advanced Features

### Type Safety
- Pydantic models for API responses
- Type hints throughout codebase
- Response validation and sanitization
- Enhanced debugging capabilities

### Performance Optimization
- Request timeouts and retries
- Audio format optimization
- Efficient error handling
- Memory management for audio processing

### Monitoring and Analytics
- Request/response logging
- Performance metrics tracking
- Error rate monitoring
- User interaction analytics

## 🚀 Usage Examples

### Basic Audio Transcription
```python
# In the UI
audio_data = audio_to_bytesio(uploaded_file)
result = transcribe_audio(audio_data)

if result["status"] == "COMPLETED":
    transcribed_text = result["transcribed_text"]
    confidence = result["confidence_score"]
    language = result["detected_language"]
```

### Text-to-Speech Generation
```python
# In the UI
tts_result = tts_response("Hello, farmer!", "hi")

if tts_result["status"] == "COMPLETED":
    audio_file = tts_result["audio_path"]
    # Display audio player with autoplay_audio()
    audio_html = autoplay_audio(audio_file)
    st.markdown(audio_html, unsafe_allow_html=True)
```

### Health Monitoring
```python
# Real-time status checking
health_status = health_check()
status_message = health_status["message"]
api_info = health_status.get("api_info", {})
```

## 🔄 Integration Flow

```mermaid
graph TD
    A[User Input] --> B{Input Type}
    B -->|Audio| C[Audio Processing]
    B -->|Text| D[Text Processing]
    
    C --> E[transcribe_audio()]
    E --> F[POST /transcribe/]
    F --> G[Transcription Response]
    G --> H[Text Display]
    
    D --> I[tts_response()]
    I --> J[POST /tts/]
    J --> K[TTS Response]
    K --> L[Audio Playback]
    
    H --> M[User Interaction]
    L --> M
    M --> N[Response Generation]
    N --> I
```

## 🐛 Troubleshooting

### Common Issues

1. **API Connection Failed**
   - Check if backend server is running on `http://localhost:8000`
   - Verify BACKEND_URL environment variable
   - Check firewall and network settings

2. **Transcription Errors**
   - Ensure audio file is in supported format
   - Check audio quality and clarity
   - Verify internet connection for Azure services

3. **TTS Generation Failed**
   - Validate language code is supported
   - Check text length (Azure has limits)
   - Verify Azure Cognitive Services credentials

4. **Audio Playback Issues**
   - Ensure browser supports audio playback
   - Check audio file accessibility
   - Verify CORS settings for audio serving

### Debug Mode
Enable detailed logging by setting:
```python
logging.getLogger(__name__).setLevel(logging.DEBUG)
```

## 📈 Performance Considerations

### Optimization Tips
1. **Audio Processing**
   - Use compressed audio formats
   - Limit recording duration
   - Implement client-side audio optimization

2. **API Requests**
   - Implement request caching
   - Use connection pooling
   - Set appropriate timeouts

3. **Error Handling**
   - Implement exponential backoff
   - Cache health check results
   - Provide offline fallbacks

## 🔐 Security Considerations

1. **API Security**
   - Validate all input data
   - Sanitize file uploads
   - Implement rate limiting

2. **Data Privacy**
   - Secure audio data transmission
   - Implement data retention policies
   - Ensure GDPR compliance

## 🎯 Future Enhancements

1. **Advanced Features**
   - Real-time streaming transcription
   - Voice activity detection
   - Multi-speaker recognition
   - Custom voice models

2. **Performance Improvements**
   - Client-side audio processing
   - WebSocket connections
   - Progressive audio loading
   - Caching strategies

3. **Monitoring Enhancements**
   - Real-time metrics dashboard
   - Performance alerting
   - Usage analytics
   - A/B testing framework

## 📞 Support

For API integration issues or questions:
1. Check the health status in the UI sidebar
2. Run the integration test suite
3. Review the detailed error logs
4. Consult this documentation for troubleshooting steps

---

**Status**: ✅ **Fully Integrated and Operational**

The Sanchalak UI and API integration is complete and ready for production use with comprehensive error handling, monitoring, and user feedback systems.
