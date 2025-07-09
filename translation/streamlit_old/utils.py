import requests
import base64
import io
from pydub import AudioSegment
import streamlit as st
import os

# Backend URL configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

def transcribe_audio(audio_bytes_io: io.BytesIO) -> dict:
    """
    Transcribe audio using the backend API
    
    Args:
        audio_bytes_io: Audio data in BytesIO format
    
    Returns:
        dict: Transcription result with status and transcribed text
    """
    try:
        # Reset stream position
        audio_bytes_io.seek(0)
        
        files = {"file": ("audio.mp3", audio_bytes_io, "audio/mpeg")}
        
        response = requests.post(
            f"{BACKEND_URL}/transcribe/", 
            files=files,
            timeout=60  # Add timeout for better error handling
        )
        response.raise_for_status()
        
        result = response.json()
        print("Calling backend /transcribe/")
        print("Response:", response.json())

        # Validate response format
        if "status" not in result:
            return {"status": "FAILED", "error": "Invalid response format from transcription service"}
        
        return result
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error during transcription: {str(e)}"
        st.error(f"🌐 {error_msg}")
        return {"status": "FAILED", "error": error_msg}
    
    except Exception as e:
        error_msg = f"Unexpected error during transcription: {str(e)}"
        st.error(f"⚠️ {error_msg}")
        return {"status": "FAILED", "error": error_msg}

def tts_response(text: str, target_language: str) -> dict:
    """
    Generate Text-to-Speech response using the backend API
    
    Args:
        text: Input text to be processed
        target_language: Target language code for TTS
    
    Returns:
        dict: TTS result with status and audio path
    """
    try:
        payload = {
            "text": text.strip(),
            "target_language": target_language
        }
        
        # Validate input
        if not text or not text.strip():
            return {"status": "FAILED", "error": "Empty text provided"}
        
        if not target_language:
            return {"status": "FAILED", "error": "No target language specified"}
        
        response = requests.post(
            f"{BACKEND_URL}/tts/", 
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30  # Add timeout for better error handling
        )
        response.raise_for_status()
        
        result = response.json()
        
        # Validate response format
        if "status" not in result:
            return {"status": "FAILED", "error": "Invalid response format from TTS service"}
        
        return result
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error during TTS generation: {str(e)}"
        st.error(f"🌐 {error_msg}")
        return {"status": "FAILED", "error": error_msg}
    
    except Exception as e:
        error_msg = f"Unexpected error during TTS generation: {str(e)}"
        st.error(f"⚠️ {error_msg}")
        return {"status": "FAILED", "error": error_msg}

def audio_to_bytesio(uploaded_file) -> io.BytesIO:
    """
    Convert uploaded audio file to MP3 format in BytesIO
    
    Args:
        uploaded_file: Streamlit uploaded file object
    
    Returns:
        io.BytesIO: Converted audio in MP3 format or None if failed
    """
    try:
        # Check file size (limit to 10MB)
        if hasattr(uploaded_file, 'size') and uploaded_file.size > 10 * 1024 * 1024:
            st.error("🚫 File size too large. Please upload a file smaller than 10MB.")
            return None
        
        # Read file content
        if hasattr(uploaded_file, 'read'):
            file_content = uploaded_file.read()
            uploaded_file.seek(0)  # Reset for potential re-use
        else:
            file_content = uploaded_file
        
        # Create BytesIO from file content
        audio_io = io.BytesIO(file_content)
        if not audio_io:
            st.session_state.chat_history.append(("bot", "🚫 Failed to process audio. Make sure the file is valid MP3/WAV and under 10MB."))
            st.rerun()
        
        # Convert to MP3 using pydub
        audio = AudioSegment.from_file(audio_io)
        print("🔍 Audio Duration:", len(audio))
        print("Channels:", audio.channels)
        print("Frame Rate:", audio.frame_rate)
        
        # Optimize audio for speech recognition
        # Normalize volume and convert to mono
        audio = audio.normalize()
        if audio.channels > 1:
            audio = audio.set_channels(1)
        
        # Set sample rate to 16kHz for better transcription
        audio = audio.set_frame_rate(16000)
        
        # Export to MP3
        mp3_buffer = io.BytesIO()
        audio.export(mp3_buffer, format="mp3", bitrate="64k")
        mp3_buffer.seek(0)
        
        return mp3_buffer
        
    except Exception as e:
        error_msg = f"Failed to process audio file: {str(e)}"
        st.error(f"🎵 {error_msg}")
        return None

def autoplay_audio(filename: str) -> str:
    """
    Create auto-playing audio HTML element using API server endpoint
    
    Args:
        filename: Audio filename from the TTS response
    
    Returns:
        str: HTML string for audio player
    """
    try:
        if not filename:
            return f"<p>🔇 No audio file provided</p>"
        
        # Create audio URL using the API server endpoint
        audio_url = f"{BACKEND_URL}/tts/audio/{filename}"
        
        # Create enhanced audio HTML with controls and styling
        audio_html = f"""
        <div style="margin: 1rem 0; padding: 1rem; background: #F5F5F5; border-radius: 8px; border-left: 4px solid #4CAF50;">
            <div style="margin-bottom: 0.5rem; font-weight: bold; color: #2E4A2E;">
                🔊 Audio Response:
            </div>
            <audio controls autoplay style="width: 100%; border-radius: 6px;">
                <source src="{audio_url}" type="audio/mpeg">
                Your browser does not support the audio element.
            </audio>
            <div style="margin-top: 0.5rem; font-size: 0.8rem; color: #666;">
                💡 Click play if audio doesn't start automatically
            </div>
        </div>
        """
        
        return audio_html
        
    except Exception as e:
        return f"<p>🔇 Audio playback error: {str(e)}</p>"

def validate_audio_format(file_path: str) -> bool:
    """
    Validate if the audio file format is supported
    
    Args:
        file_path: Path to the audio file
    
    Returns:
        bool: True if format is supported, False otherwise
    """
    try:
        supported_formats = ['.mp3', '.wav', '.m4a', '.webm', '.ogg']
        file_extension = os.path.splitext(file_path)[1].lower()
        return file_extension in supported_formats
    except Exception:
        return False

def format_error_message(error: str, context: str = "") -> str:
    """
    Format error messages for better user experience
    
    Args:
        error: Error message
        context: Additional context about the error
    
    Returns:
        str: Formatted error message
    """
    error_messages = {
        "network": "🌐 Network connection issue. Please check your internet connection and try again.",
        "timeout": "⏱️ Request timed out. The server might be busy. Please try again in a moment.",
        "file_size": "📁 File size is too large. Please use a smaller audio file (max 10MB).",
        "format": "🎵 Unsupported audio format. Please use MP3, WAV, M4A, or WebM files.",
        "microphone": "🎤 Microphone access denied. Please allow microphone permissions in your browser.",
        "processing": "⚙️ Error processing your request. Please try again.",
    }
    
    # Try to match error type
    error_lower = error.lower()
    for key, message in error_messages.items():
        if key in error_lower:
            return f"{message} {context}".strip()
    
    # Default error message
    return f"⚠️ {error} {context}".strip()
