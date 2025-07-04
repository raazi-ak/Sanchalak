import requests
import base64
import io
from pydub import AudioSegment
import streamlit as st
import os
import logging

# Backend URL configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def transcribe_audio(audio_bytes_io: io.BytesIO) -> dict:
    """
    Transcribe audio using the backend API with enhanced error handling
    
    Args:
        audio_bytes_io: Audio data in BytesIO format
    
    Returns:
        dict: Transcription result with status and transcribed text
    """
    try:
        # Reset stream position
        audio_bytes_io.seek(0)
        
        # Validate audio data
        if audio_bytes_io.getvalue() == b'':
            return {
                "status": "FAILED", 
                "error": "Empty audio data provided"
            }
        
        files = {"file": ("audio.mp3", audio_bytes_io, "audio/mpeg")}
        
        logger.info(f"🔄 Sending audio to transcription service: {BACKEND_URL}/transcribe/")
        
        response = requests.post(
            f"{BACKEND_URL}/transcribe/", 
            files=files,
            timeout=60  # Extended timeout for audio processing
        )
        response.raise_for_status()
        
        result = response.json()
        logger.info(f"✅ Transcription response: {result}")

        # Validate response format
        if "status" not in result:
            return {
                "status": "FAILED", 
                "error": "Invalid response format from transcription service"
            }
        
        return result
        
    except requests.exceptions.Timeout:
        error_msg = "🕒 Transcription service timeout. The audio might be too long or the server is busy."
        st.error(error_msg)
        return {"status": "FAILED", "error": error_msg}
        
    except requests.exceptions.ConnectionError:
        error_msg = "🌐 Cannot connect to transcription service. Please check your internet connection."
        st.error(error_msg)
        return {"status": "FAILED", "error": error_msg}
        
    except requests.exceptions.RequestException as e:
        error_msg = f"🌐 Network error during transcription: {str(e)}"
        st.error(error_msg)
        return {"status": "FAILED", "error": error_msg}
    
    except ValueError as e:
        error_msg = f"📄 Invalid response format: {str(e)}"
        st.error(error_msg)
        return {"status": "FAILED", "error": error_msg}
    
    except Exception as e:
        error_msg = f"⚠️ Unexpected error during transcription: {str(e)}"
        st.error(error_msg)
        logger.exception("Transcription failed with unexpected error")
        return {"status": "FAILED", "error": error_msg}

def tts_response(text: str, target_language: str) -> dict:
    """
    Generate Text-to-Speech response using the backend API with enhanced validation
    
    Args:
        text: Input text to be processed
        target_language: Target language code for TTS
    
    Returns:
        dict: TTS result with status and audio path
    """
    try:
        # Input validation
        if not text or not text.strip():
            return {
                "status": "FAILED", 
                "error": "Empty text provided for TTS generation"
            }
        
        if not target_language:
            return {
                "status": "FAILED", 
                "error": "No target language specified for TTS"
            }
        
        # Validate language code
        valid_languages = ["en", "hi", "gu", "pa", "bn", "te", "ta", "ml", "kn", "or"]
        if target_language not in valid_languages:
            return {
                "status": "FAILED", 
                "error": f"Unsupported language: {target_language}"
            }
        
        payload = {
            "text": text.strip(),
            "target_language": target_language
        }
        
        logger.info(f"🔄 Sending TTS request: {payload}")
        
        response = requests.post(
            f"{BACKEND_URL}/tts/", 
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30  # Reasonable timeout for TTS generation
        )
        response.raise_for_status()
        
        result = response.json()
        logger.info(f"✅ TTS response: {result}")
        
        # Validate response format
        if "status" not in result:
            return {
                "status": "FAILED", 
                "error": "Invalid response format from TTS service"
            }
        
        return result
        
    except requests.exceptions.Timeout:
        error_msg = "🕒 TTS service timeout. Please try with shorter text."
        st.error(error_msg)
        return {"status": "FAILED", "error": error_msg}
        
    except requests.exceptions.ConnectionError:
        error_msg = "🌐 Cannot connect to TTS service. Please check your internet connection."
        st.error(error_msg)
        return {"status": "FAILED", "error": error_msg}
        
    except requests.exceptions.RequestException as e:
        error_msg = f"🌐 Network error during TTS generation: {str(e)}"
        st.error(error_msg)
        return {"status": "FAILED", "error": error_msg}
    
    except ValueError as e:
        error_msg = f"📄 Invalid response format from TTS service: {str(e)}"
        st.error(error_msg)
        return {"status": "FAILED", "error": error_msg}
    
    except Exception as e:
        error_msg = f"⚠️ Unexpected error during TTS generation: {str(e)}"
        st.error(error_msg)
        logger.exception("TTS generation failed with unexpected error")
        return {"status": "FAILED", "error": error_msg}

def audio_to_bytesio(uploaded_file) -> io.BytesIO:
    """
    Convert uploaded audio file to MP3 format in BytesIO with enhanced processing
    
    Args:
        uploaded_file: Streamlit uploaded file object or BytesIO
    
    Returns:
        io.BytesIO: Converted audio in MP3 format or None if failed
    """
    try:
        # File size validation (limit to 25MB for better user experience)
        max_size = 25 * 1024 * 1024  # 25MB
        
        if hasattr(uploaded_file, 'size') and uploaded_file.size > max_size:
            st.error("🚫 File size too large. Please upload a file smaller than 25MB.")
            return None
        
        # Read file content
        if hasattr(uploaded_file, 'read'):
            file_content = uploaded_file.read()
            # Reset file pointer if possible
            if hasattr(uploaded_file, 'seek'):
                uploaded_file.seek(0)
        else:
            file_content = uploaded_file
        
        # Validate file content
        if len(file_content) == 0:
            st.error("🚫 Empty audio file. Please upload a valid audio file.")
            return None
        
        # Create BytesIO from file content
        audio_io = io.BytesIO(file_content)
        
        logger.info(f"🔍 Processing audio file, size: {len(file_content)} bytes")
        
        # Convert to AudioSegment with error handling for different formats
        try:
            audio = AudioSegment.from_file(audio_io)
        except Exception as e:
            logger.error(f"Failed to load audio with pydub: {e}")
            st.error("🎵 Unsupported audio format or corrupted file. Please try MP3, WAV, or M4A format.")
            return None
        
        # Log audio properties
        logger.info(f"🔍 Audio Duration: {len(audio)}ms")
        logger.info(f"🔍 Channels: {audio.channels}")
        logger.info(f"🔍 Frame Rate: {audio.frame_rate}Hz")
        
        # Validate audio duration (minimum 0.5 seconds, maximum 300 seconds)
        if len(audio) < 500:
            st.error("🕒 Audio too short. Please record for at least 0.5 seconds.")
            return None
        
        if len(audio) > 300000:  # 5 minutes
            st.warning("⏱️ Audio is quite long. Consider splitting into shorter segments for better accuracy.")
            # Truncate to 5 minutes
            audio = audio[:300000]
        
        # Optimize audio for speech recognition
        try:
            # Normalize volume
            audio = audio.normalize()
            
            # Convert to mono if stereo
            if audio.channels > 1:
                audio = audio.set_channels(1)
                logger.info("🔄 Converted to mono")
            
            # Set optimal sample rate for speech recognition (16kHz)
            if audio.frame_rate != 16000:
                audio = audio.set_frame_rate(16000)
                logger.info("🔄 Resampled to 16kHz")
            
            # Apply noise reduction by removing very quiet parts
            # This helps with background noise
            if audio.dBFS < -30:  # Very quiet audio
                audio = audio + (20 - audio.dBFS)  # Boost volume
                logger.info("🔊 Boosted audio volume")
            
        except Exception as e:
            logger.warning(f"Audio optimization failed, proceeding with original: {e}")
        
        # Export to MP3 with optimized settings for speech
        mp3_buffer = io.BytesIO()
        audio.export(
            mp3_buffer, 
            format="mp3", 
            bitrate="64k",  # Sufficient for speech
            parameters=["-ac", "1"]  # Ensure mono output
        )
        mp3_buffer.seek(0)
        
        logger.info(f"✅ Audio processed successfully, output size: {len(mp3_buffer.getvalue())} bytes")
        
        return mp3_buffer
        
    except Exception as e:
        error_msg = f"Failed to process audio file: {str(e)}"
        st.error(f"🎵 {error_msg}")
        logger.exception("Audio processing failed")
        return None

def autoplay_audio(filename: str) -> str:
    """
    Create auto-playing audio HTML element with agricultural theme
    
    Args:
        filename: Audio filename from the TTS response
    
    Returns:
        str: HTML string for audio player with agricultural styling
    """
    try:
        if not filename:
            return """
            <div style="margin: 1rem 0; padding: 1rem; background: #FFEBEE; border-radius: 10px; border-left: 4px solid #F44336;">
                <p style="margin: 0; color: #C62828;">🔇 No audio file provided</p>
            </div>
            """
        
        # Create audio URL using the API server endpoint
        audio_url = f"{BACKEND_URL}/tts/audio/{filename}"
        
        # Create enhanced audio HTML with agricultural theme
        audio_html = f"""
        <div style="margin: 1.5rem 0; padding: 1.5rem; 
                    background: linear-gradient(135deg, #F1F8E9 0%, #DCEDC8 100%); 
                    border-radius: 15px; border-left: 5px solid #4CAF50;
                    box-shadow: 0 4px 15px rgba(76, 175, 80, 0.2);">
            <div style="margin-bottom: 1rem; font-weight: 600; color: #2E7D32; display: flex; align-items: center;">
                <span style="font-size: 1.5rem; margin-right: 0.5rem;">🔊</span>
                <span>Agricultural Assistant Response:</span>
            </div>
            <audio controls autoplay style="width: 100%; border-radius: 8px; outline: none;">
                <source src="{audio_url}" type="audio/mpeg">
                <source src="{audio_url}" type="audio/wav">
                Your browser does not support the audio element.
            </audio>
            <div style="margin-top: 1rem; font-size: 0.9rem; color: #558B2F; 
                        display: flex; align-items: center; justify-content: space-between;">
                <span>💡 Click play if audio doesn't start automatically</span>
                <span>🌾 Harvested with care by Sanchalak</span>
            </div>
        </div>
        """
        
        return audio_html
        
    except Exception as e:
        logger.error(f"Audio playback HTML generation failed: {e}")
        return f"""
        <div style="margin: 1rem 0; padding: 1rem; background: #FFEBEE; border-radius: 10px; border-left: 4px solid #F44336;">
            <p style="margin: 0; color: #C62828;">🔇 Audio playback error: {str(e)}</p>
        </div>
        """

def validate_audio_format(file_path: str) -> bool:
    """
    Validate if the audio file format is supported
    
    Args:
        file_path: Path to the audio file
    
    Returns:
        bool: True if format is supported, False otherwise
    """
    try:
        supported_formats = ['.mp3', '.wav', '.m4a', '.webm', '.ogg', '.flac', '.aac']
        file_extension = os.path.splitext(file_path)[1].lower()
        return file_extension in supported_formats
    except Exception:
        return False

def format_error_message(error: str, context: str = "") -> str:
    """
    Format error messages for better user experience with agricultural metaphors
    
    Args:
        error: Error message
        context: Additional context about the error
    
    Returns:
        str: Formatted error message with agricultural theme
    """
    error_messages = {
        "network": "🌐 Connection to the digital farm failed. Please check your internet and try planting again.",
        "timeout": "⏱️ The harvest took too long. Our digital tractors might be busy. Please try again.",
        "file_size": "📁 Your audio seedling is too large. Please use a smaller file (max 25MB).",
        "format": "🎵 Unsupported audio crop type. Please use MP3, WAV, M4A, or WebM seeds.",
        "microphone": "🎤 Cannot access your voice harvester. Please allow microphone permissions.",
        "processing": "⚙️ Error in our digital processing mill. Please try again.",
        "empty": "🌾 No content to harvest. Please provide some audio or text seeds.",
        "language": "🗣️ Unsupported language dialect. Please choose from our cultivated language varieties."
    }
    
    # Try to match error type with agricultural metaphors
    error_lower = error.lower()
    for key, message in error_messages.items():
        if key in error_lower:
            return f"{message} {context}".strip()
    
    # Default error message with agricultural theme
    return f"🚜 Agricultural processing error: {error} {context}".strip()

def get_audio_info(audio_file) -> dict:
    """
    Get detailed information about an audio file
    
    Args:
        audio_file: Audio file object or path
    
    Returns:
        dict: Audio information including duration, format, channels, etc.
    """
    try:
        if hasattr(audio_file, 'read'):
            audio_data = audio_file.read()
            audio_file.seek(0)
            audio_io = io.BytesIO(audio_data)
        else:
            audio_io = io.BytesIO(audio_file)
        
        audio = AudioSegment.from_file(audio_io)
        
        info = {
            "duration_ms": len(audio),
            "duration_seconds": len(audio) / 1000,
            "channels": audio.channels,
            "frame_rate": audio.frame_rate,
            "sample_width": audio.sample_width,
            "max_dBFS": audio.max_dBFS,
            "dBFS": audio.dBFS
        }
        
        return info
        
    except Exception as e:
        logger.error(f"Failed to get audio info: {e}")
        return {"error": str(e)}

def health_check() -> dict:
    """
    Check the health status of backend services
    
    Returns:
        dict: Health status of transcription and TTS services
    """
    try:
        health_status = {
            "transcription_service": "unknown",
            "tts_service": "unknown",
            "backend_url": BACKEND_URL
        }
        
        # Check transcription service
        try:
            response = requests.get(f"{BACKEND_URL}/health", timeout=5)
            if response.status_code == 200:
                health_status["transcription_service"] = "healthy"
            else:
                health_status["transcription_service"] = "unhealthy"
        except:
            health_status["transcription_service"] = "offline"
        
        # Check TTS service
        try:
            response = requests.get(f"{BACKEND_URL}/tts/health", timeout=5)
            if response.status_code == 200:
                health_status["tts_service"] = "healthy"
            else:
                health_status["tts_service"] = "unhealthy"
        except:
            health_status["tts_service"] = "offline"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"error": str(e)}
