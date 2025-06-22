"""
Audio Ingestion Agent
Handles audio file processing, transcription using Whisper, and language detection
"""

import os
import tempfile
import time
import asyncio
from typing import Optional, BinaryIO
import whisper
import librosa
import numpy as np
from pydub import AudioSegment
from langdetect import detect, DetectorFactory
import torch

from config import get_settings
from models import AudioProcessingResponse, LanguageCode, ProcessingStatus
from utils.logger import get_logger

# Set seed for consistent language detection
DetectorFactory.seed = 0

settings = get_settings()
logger = get_logger(__name__)


class AudioIngestionAgent:
    """Agent for processing audio files and extracting text with language detection"""
    
    def __init__(self):
        self.whisper_model = None
        self.supported_formats = settings.supported_audio_formats
        self.max_duration = 300  # 5 minutes max
        self.sample_rate = 16000
        # Device selection: prioritize MPS (Metal) on Mac, then CUDA, then CPU
        if torch.backends.mps.is_available():
            self.device = "mps"  # Apple Metal Performance Shaders
        elif torch.cuda.is_available():
            self.device = "cuda"  # NVIDIA GPU
        else:
            self.device = "cpu"   # CPU fallback
        logger.info(f"Audio agent will use device: {self.device}")
    
    async def initialize(self):
        """Initialize the Whisper model and other components"""
        try:
            logger.info(f"🤖 Initializing Audio Agent with Whisper model: {settings.whisper_model}")
            logger.info(f"🔧 Target device: {self.device}")
            
            # Check if model needs to be downloaded
            model_size_info = {
                "tiny": "~39 MB",
                "base": "~74 MB", 
                "small": "~244 MB",
                "medium": "~769 MB",
                "large": "~1550 MB",
                "large-v2": "~1550 MB",
                "large-v3": "~1550 MB"
            }
            
            estimated_size = model_size_info.get(settings.whisper_model, "Unknown size")
            logger.info(f"📦 Model '{settings.whisper_model}' estimated size: {estimated_size}")
            
            # Check if this is likely the first download
            import whisper
            try:
                model_path = whisper._MODELS[settings.whisper_model]
                cache_dir = os.path.expanduser("~/.cache/whisper")
                model_file = os.path.join(cache_dir, os.path.basename(model_path))
                
                if os.path.exists(model_file):
                    logger.info(f"✅ Model file found in cache: {model_file}")
                    logger.info(f"📁 File size: {os.path.getsize(model_file) / (1024*1024):.1f} MB")
                else:
                    logger.info(f"⬇️ Model not cached, will download from: {model_path}")
                    logger.info(f"💾 Cache directory: {cache_dir}")
                    logger.info("🕐 This may take several minutes depending on your internet connection...")
                    
            except Exception as cache_check_error:
                logger.warning(f"Could not check model cache: {cache_check_error}")
            
            # Load Whisper model with progress monitoring
            logger.info("🚀 Starting Whisper model loading...")
            start_time = time.time()
            
            # Load model in a thread to avoid blocking
            loop = asyncio.get_event_loop()
            self.whisper_model = await loop.run_in_executor(
                None, 
                self._load_model_with_progress,
                settings.whisper_model,
                self.device
            )
            
            load_time = time.time() - start_time
            logger.info(f"✅ Whisper model loaded successfully in {load_time:.1f} seconds")
            
            # Skip model test to avoid segfaults - model will be tested during actual audio processing
            logger.info("ℹ️ Skipping model test - model ready for audio processing")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize audio agent: {str(e)}")
            import traceback
            logger.error(f"🔍 Traceback: {traceback.format_exc()}")
            raise
    
    def _load_model_with_progress(self, model_name: str, device: str):
        """Load Whisper model with detailed progress logging"""
        import whisper
        import urllib.request
        import tempfile
        import shutil
        
        try:
            logger.info(f"🔄 Loading Whisper model '{model_name}' on device '{device}'...")
            
            # Create a custom progress hook for download
            last_logged_percent = [0]  # Use list to allow modification in nested function
            
            def progress_hook(block_num, block_size, total_size):
                if total_size > 0:
                    downloaded = block_num * block_size
                    percent = min(100, (downloaded * 100) // total_size)
                    mb_downloaded = downloaded / (1024 * 1024)
                    mb_total = total_size / (1024 * 1024)
                    
                    # Log progress every 10% only once
                    if percent >= last_logged_percent[0] + 10 and percent > 0:
                        last_logged_percent[0] = (percent // 10) * 10
                        logger.info(f"⬇️ Download progress: {last_logged_percent[0]}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)")
            
            # Check if we need to download
            model_url = whisper._MODELS[model_name]
            cache_dir = os.path.expanduser("~/.cache/whisper")
            os.makedirs(cache_dir, exist_ok=True)
            model_file = os.path.join(cache_dir, os.path.basename(model_url))
            
            if not os.path.exists(model_file):
                logger.info(f"📥 Downloading model from: {model_url}")
                logger.info(f"💾 Saving to: {model_file}")
                
                # Download with progress
                urllib.request.urlretrieve(model_url, model_file, progress_hook)
                logger.info(f"✅ Download completed: {os.path.getsize(model_file) / (1024*1024):.1f} MB")
            else:
                logger.info(f"📂 Using cached model: {model_file}")
            
            # Now load the model
            logger.info(f"🧠 Loading model into memory on {device}...")
            model = whisper.load_model(model_name, device=device)
            logger.info(f"🎯 Model loaded successfully with {sum(p.numel() for p in model.parameters())} parameters")
            
            return model
            
        except Exception as e:
            logger.error(f"❌ Model loading failed: {str(e)}")
            raise

    async def _test_model(self):
        """Test the Whisper model with a short synthetic audio"""
        try:
            logger.info("🧪 Testing Whisper model...")
            
            # Create a short silence for testing (1 second of silence)
            import numpy as np
            test_audio = np.zeros(16000, dtype=np.float32)  # 1 second at 16kHz
            
            # Run a quick transcription test
            result = self.whisper_model.transcribe(test_audio, language="en", task="transcribe")
            
            logger.info(f"✅ Model test completed successfully")
            logger.info(f"🔤 Test transcription result: '{result.get('text', '').strip()}'")
            
        except Exception as e:
            logger.warning(f"⚠️ Audio model test failed: {str(e)}")
            logger.warning("Model may still work for actual audio processing")
    
    async def process_audio(
        self, 
        audio_file: BinaryIO, 
        language_hint: Optional[LanguageCode] = None
    ) -> AudioProcessingResponse:
        """
        Process audio file and return transcription with language detection
        
        Args:
            audio_file: Audio file to process
            language_hint: Optional language hint for better processing
            
        Returns:
            AudioProcessingResponse with transcription and metadata
        """
        start_time = time.time()
        task_id = f"audio_{int(time.time() * 1000)}"
        
        try:
            logger.info(f"Starting audio processing for task {task_id}")
            
            # Step 1: Validate and preprocess audio
            processed_audio = await self._preprocess_audio(audio_file)
            
            # Step 2: Transcribe using Whisper
            transcription_result = await self._transcribe_audio(
                processed_audio, 
                language_hint
            )
            
            # Step 3: Detect language from transcribed text
            detected_language = await self._detect_language(
                transcription_result["text"]
            )
            
            # Step 4: Calculate confidence score
            confidence_score = self._calculate_confidence(transcription_result)
            
            processing_time = time.time() - start_time
            
            logger.info(f"Audio processing completed for task {task_id} in {processing_time:.2f}s")
            
            return AudioProcessingResponse(
                task_id=task_id,
                status=ProcessingStatus.COMPLETED,
                transcribed_text=transcription_result["text"],
                detected_language=detected_language,
                confidence_score=confidence_score,
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"Audio processing failed for task {task_id}: {str(e)}")
            return AudioProcessingResponse(
                task_id=task_id,
                status=ProcessingStatus.FAILED,
                processing_time=time.time() - start_time
            )
    
    async def _preprocess_audio(self, audio_file: BinaryIO) -> np.ndarray:
        """
        Preprocess audio file: convert format, resample, normalize
        
        Args:
            audio_file: Input audio file
            
        Returns:
            Preprocessed audio as numpy array
        """
        try:
            # Save uploaded file to temporary location
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                temp_file.write(audio_file.read())
                temp_path = temp_file.name
            
            try:
                # Load and convert audio using pydub
                audio = AudioSegment.from_file(temp_path)
                
                # Check duration
                duration_seconds = len(audio) / 1000
                if duration_seconds > self.max_duration:
                    logger.warning(f"Audio duration {duration_seconds}s exceeds maximum {self.max_duration}s")
                    # Truncate to max duration
                    audio = audio[:self.max_duration * 1000]
                
                # Convert to mono and resample
                audio = audio.set_channels(1).set_frame_rate(self.sample_rate)
                
                # Convert to numpy array
                audio_array = np.array(audio.get_array_of_samples(), dtype=np.float32)
                
                # Normalize
                if len(audio_array) > 0:
                    audio_array = audio_array / np.max(np.abs(audio_array))
                
                logger.info(f"Audio preprocessed: {len(audio_array)/self.sample_rate:.2f}s duration")
                
                return audio_array
                
            finally:
                # Clean up temporary file
                os.unlink(temp_path)
                
        except Exception as e:
            logger.error(f"Audio preprocessing failed: {str(e)}")
            raise ValueError(f"Failed to preprocess audio: {str(e)}")
    
    async def _transcribe_audio(
        self, 
        audio_array: np.ndarray, 
        language_hint: Optional[LanguageCode] = None
    ) -> dict:
        """
        Transcribe audio using Whisper model
        
        Args:
            audio_array: Preprocessed audio array
            language_hint: Optional language hint
            
        Returns:
            Whisper transcription result
        """
        try:
            # Prepare transcription options
            options = {
                "language": language_hint.value if language_hint else None,
                "task": "transcribe",
                "fp16": False,  # Use fp32 for better compatibility
            }
            
            # Remove None values
            options = {k: v for k, v in options.items() if v is not None}
            
            # Run transcription in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.whisper_model.transcribe(audio_array, **options)
            )
            
            logger.info(f"Transcription completed: {len(result['text'])} characters")
            
            return result
            
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            raise ValueError(f"Failed to transcribe audio: {str(e)}")
    
    async def _detect_language(self, text: str) -> Optional[LanguageCode]:
        """
        Detect language from transcribed text
        
        Args:
            text: Transcribed text
            
        Returns:
            Detected language code
        """
        try:
            if not text or len(text.strip()) < 10:
                return None
            
            # Use langdetect for language detection
            detected_lang = detect(text)
            
            # Map to our language codes
            lang_mapping = {
                'hi': LanguageCode.HINDI,
                'en': LanguageCode.ENGLISH,
                'gu': LanguageCode.GUJARATI,
                'pa': LanguageCode.PUNJABI,
                'bn': LanguageCode.BENGALI,
                'te': LanguageCode.TELUGU,
                'ta': LanguageCode.TAMIL,
                'ml': LanguageCode.MALAYALAM,
                'kn': LanguageCode.KANNADA,
                'or': LanguageCode.ODIA
            }
            
            detected_language = lang_mapping.get(detected_lang, LanguageCode.HINDI)
            
            logger.info(f"Language detected: {detected_language.value}")
            
            return detected_language
            
        except Exception as e:
            logger.warning(f"Language detection failed: {str(e)}")
            return LanguageCode.HINDI  # Default to Hindi
    
    def _calculate_confidence(self, transcription_result: dict) -> float:
        """
        Calculate confidence score from Whisper result
        
        Args:
            transcription_result: Whisper transcription result
            
        Returns:
            Confidence score between 0 and 1
        """
        try:
            # Whisper doesn't provide direct confidence scores
            # We'll estimate based on available information
            
            text = transcription_result.get("text", "")
            segments = transcription_result.get("segments", [])
            
            if not segments:
                # Fallback based on text length
                return max(0.1, min(0.9, len(text) / 100))
            
            # Calculate average probability from segments
            total_prob = 0
            total_segments = 0
            
            for segment in segments:
                if "avg_logprob" in segment:
                    # Convert log probability to probability
                    prob = np.exp(segment["avg_logprob"])
                    total_prob += prob
                    total_segments += 1
            
            if total_segments > 0:
                avg_confidence = total_prob / total_segments
                return max(0.1, min(0.9, avg_confidence))
            
            # Default confidence
            return 0.7
            
        except Exception as e:
            logger.warning(f"Confidence calculation failed: {str(e)}")
            return 0.5  # Default confidence
    
    async def is_ready(self) -> bool:
        """Check if the agent is ready to process audio"""
        return self.whisper_model is not None
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            if self.whisper_model:
                # Clear GPU memory if using CUDA
                if self.device == "cuda":
                    torch.cuda.empty_cache()
                self.whisper_model = None
            
            logger.info("Audio agent cleaned up successfully")
            
        except Exception as e:
            logger.error(f"Error during audio agent cleanup: {str(e)}")
    
    async def get_supported_formats(self) -> list:
        """Get list of supported audio formats"""
        return self.supported_formats
    
    async def estimate_processing_time(self, duration_seconds: float) -> float:
        """
        Estimate processing time for given audio duration
        
        Args:
            duration_seconds: Audio duration in seconds
            
        Returns:
            Estimated processing time in seconds
        """
        # Rough estimate: Whisper processes at 10-20x real-time
        # depending on model size and hardware
        model_factors = {
            "tiny": 0.02,
            "base": 0.05,
            "small": 0.1,
            "medium": 0.2,
            "large": 0.4
        }
        
        factor = model_factors.get(settings.whisper_model, 0.1)
        
        if self.device == "cuda":
            factor *= 0.3  # GPU acceleration
        
        return duration_seconds * factor
    
    async def get_health_status(self) -> dict:
        """Get health status of the audio agent"""
        return {
            "model_loaded": self.whisper_model is not None,
            "device": self.device,
            "model_name": settings.whisper_model,
            "supported_formats": self.supported_formats,
            "max_duration": self.max_duration
        }
        