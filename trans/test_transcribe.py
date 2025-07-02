import asyncio
from transcribe import AudioIngestionAgent
from models import LanguageCode

async def main():
    agent = AudioIngestionAgent()
    await agent.initialize()

    # Replace this with the path to your test audio file
    audio_path = "test_audio.mp3"
    with open(audio_path, "rb") as f:
        result = await agent.process_audio(f, language_hint=LanguageCode.HINDI)

    print("=== TRANSCRIPTION RESULT ===")
    print("Transcribed Text:", result.transcribed_text)
    print("Translated to English:", result.translated_text)
    print("Detected Language:", result.detected_language)
    print("Confidence Score:", result.confidence_score)
    print("Processing Time (s):", result.processing_time)

asyncio.run(main())
