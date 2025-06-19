from fastapi import FastAPI, File, UploadFile, HTTPException
from pydub import AudioSegment
import whisper
import tempfile
import os
import langid
from langdetect import detect
import shutil
from extract_info import extract_info
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Audio Transcription API", version="1.0.0")

# Load Whisper model once at startup
try:
    model = whisper.load_model("base", device="cpu")
    logger.info("Whisper model loaded successfully")
except Exception as e:
    logger.error(f"Failed to load Whisper model: {e}")
    model = None

def convert_to_wav(input_file_path: str, output_file_path: str):
    """Convert audio file to WAV format with 16kHz sample rate and mono channel"""
    try:
        audio = AudioSegment.from_file(input_file_path)
        audio = audio.set_frame_rate(16000).set_channels(1)
        audio.export(output_file_path, format="wav")
        logger.info(f"Successfully converted {input_file_path} to WAV format")
    except Exception as e:
        logger.error(f"Error converting audio file: {e}")
        raise HTTPException(status_code=400, detail=f"Audio conversion failed: {str(e)}")

@app.post("/transcribe/")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribe uploaded audio file and extract information"""
    
    if model is None:
        raise HTTPException(status_code=500, detail="Whisper model not loaded")
    
    # Validate file type
    allowed_extensions = ['.mp3', '.wav', '.m4a', '.flac', '.ogg', '.webm', '.mp4']
    file_extension = os.path.splitext(file.filename)[1].lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file format. Allowed formats: {', '.join(allowed_extensions)}"
        )
    
    tmp_in_path = None
    tmp_out_path = None
    
    try:
        # Create temporary file for uploaded audio
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_in:
            shutil.copyfileobj(file.file, tmp_in)
            tmp_in_path = tmp_in.name
        
        # Create path for converted WAV file
        tmp_out_path = tmp_in_path + "_converted.wav"
        
        # Convert to WAV format
        convert_to_wav(tmp_in_path, tmp_out_path)
        
        # Transcribe audio
        logger.info("Starting transcription...")
        result = model.transcribe(tmp_out_path, fp16=False)
        text = result["text"].strip()
        
        if not text:
            return {
                "transcription": "",
                "language_langdetect": "undetected",
                "language_langid": "undetected",
                "confidence_langid": 0.0,
                "extracted_info": {}
            }
        
        # Extract structured data
        extracted_data = extract_info(text)
        
        # Language detection with langdetect
        try:
            lang_detected = detect(text)
        except:
            lang_detected = "undetected"
        
        # Language detection with langid
        try:
            lang_result = langid.classify(text)
            lang_langid_code = lang_result[0]
            lang_langid_confidence = abs(lang_result[1])  # Convert negative log probability to positive
        except:
            lang_langid_code = "undetected"
            lang_langid_confidence = 0.0
        
        logger.info("Transcription completed successfully")
        
        return {
            "transcription": text,
            "language_langdetect": lang_detected,
            "language_langid": lang_langid_code,
            "confidence_langid": lang_langid_confidence,
            "extracted_info": extracted_data
        }
        
    except Exception as e:
        logger.error(f"Error during transcription: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    
    finally:
        # Clean up temporary files
        if tmp_in_path and os.path.exists(tmp_in_path):
            os.remove(tmp_in_path)
        if tmp_out_path and os.path.exists(tmp_out_path):
            os.remove(tmp_out_path)

@app.get("/")
async def root():
    return {"message": "Audio Transcription API is running"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "whisper_model_loaded": model is not None
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
