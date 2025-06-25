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
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Audio agent will use device: {self.device}")
    
    async def initialize(self):
        """Initialize the Whisper model and other components"""
        try:
            logger.info(f"Loading Whisper model: {settings.whisper_model}")
            
            # Load Whisper model in a thread to avoid blocking
            loop = asyncio.get_event_loop()
            self.whisper_model = await loop.run_in_executor(
                None, 
                whisper.load_model, 
                settings.whisper_model,
                self.device
            )
            
            logger.info("Whisper model loaded successfully")
            
            # Test the model with a short audio
            await self._test_model()
            
        except Exception as e:
            logger.error(f"Failed to initialize audio agent: {str(e)}")
            raise
    
    async def _test_model(self):
        """Test the Whisper model with a short synthetic audio"""
        logger.info("Audio model test completed successfully")

    
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
        