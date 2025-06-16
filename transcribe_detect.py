import whisper
from langdetect import detect
from pydub import AudioSegment
import os

def convert_to_wav(input_path, output_path):
    """Convert audio to 16kHz mono wav format"""
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_frame_rate(16000).set_channels(1)
    audio.export(output_path, format="wav")
    return output_path

def transcribe_audio_whisper(audio_path):
    """Transcribe audio using Whisper"""
    model = whisper.load_model("base")
    result = model.transcribe(audio_path)
    return result['text'], result['language']

def detect_language(text):
    """Detect language from text using langdetect"""
    try:
        lang_code = detect(text)
        return lang_code
    except:
        return "unknown"

def dummy_accent_classifier(text):
    """Placeholder: Replace with an ML model or accent classifier"""
    # Just an illustrative example
    if 'babu' in text or 'raja' in text:
        return "Indian Accent"
    elif 'mate' in text or 'bloody' in text:
        return "British Accent"
    elif 'y’all' in text or 'gonna' in text:
        return "American Accent"
    else:
        return "Unknown Accent"

if __name__ == "__main__":
    input_audio = "sample.mp3"  # 🔄 Replace with your file
    wav_audio = "converted.wav"

    print("[🔄] Converting audio...")
    convert_to_wav(input_audio, wav_audio)

    print("[🔊] Transcribing...")
    text, whisper_lang = transcribe_audio_whisper(wav_audio)
    print("Transcribed Text:", text)
    print("Language (Whisper):", whisper_lang)

    print("[🌐] Detecting language...")
    detected_lang = detect_language(text)
    print("Language (langdetect):", detected_lang)

    print("[🎤] Detecting accent...")
    accent = dummy_accent_classifier(text)
    print("Accent (placeholder):", accent)

    # Cleanup
    if os.path.exists(wav_audio):
        os.remove(wav_audio)
