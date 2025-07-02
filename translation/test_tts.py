import asyncio  # Ensure asyncio is imported for async operations
from tts import translate_to_target_language, synthesize_speech

async def main():
    english_response = "You are eligible for the Pradhan Mantri Fasal Bima Yojana."
    target_lang = "bn"  # Detected earlier in the pipeline

    print("Translating to regional language...")
    regional_text = await translate_to_target_language(english_response, target_lang)
    print("Translated:", regional_text)

    print("Generating speech...")
    await synthesize_speech(regional_text, target_lang)
    print("Saved output.mp3")

asyncio.run(main())
