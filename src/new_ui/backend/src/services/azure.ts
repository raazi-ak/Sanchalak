import * as sdk from 'microsoft-cognitiveservices-speech-sdk';
import fs from 'fs';
import path from 'path';
import { v4 as uuidv4 } from 'uuid';
import { logger } from './logger';

// Language mapping for Azure Speech Service
const AZURE_LANGUAGE_MAP: Record<string, string> = {
  'en': 'en-US',
  'hi': 'hi-IN',
  'gu': 'gu-IN',
  'pa': 'pa-IN',
  'bn': 'bn-IN',
  'te': 'te-IN',
  'ta': 'ta-IN',
  'ml': 'ml-IN',
  'kn': 'kn-IN',
  'or': 'or-IN'
};

// Voice mapping for Azure Speech Service
const AZURE_VOICE_MAP: Record<string, string> = {
  'en': 'en-US-AriaNeural',
  'hi': 'hi-IN-SwaraNeural',
  'gu': 'gu-IN-DhwaniNeural',
  'pa': 'pa-IN-HarmanNeural',
  'bn': 'bn-IN-BashkarNeural',
  'te': 'te-IN-ShrutiNeural',
  'ta': 'ta-IN-PallaviNeural',
  'ml': 'ml-IN-SobhanaNeural',
  'kn': 'kn-IN-SapnaNeural',
  'or': 'or-IN-SubhasiniNeural'
};

export interface TTSResult {
  status: string;
  translated_text?: string;
  audio_path?: string;
  error_message?: string;
}

export async function generateSpeechFile(text: string, targetLanguage: string): Promise<TTSResult> {
  try {
    logger.debug(`TTS request for language: ${targetLanguage}, text length: ${text.length}`);
    
    const speechKey = process.env.AZURE_TTS_KEY;
    const speechRegion = process.env.AZURE_TTS_REGION;

    if (!speechKey || !speechRegion) {
      logger.error('Azure TTS Service not configured');
      return {
        status: 'error',
        error_message: 'Azure TTS Service not configured'
      };
    }

    // Get Azure language and voice
    const azureLanguage = AZURE_LANGUAGE_MAP[targetLanguage] || 'en-US';
    const azureVoice = AZURE_VOICE_MAP[targetLanguage] || 'en-US-AriaNeural';

    // Create speech config
    const speechConfig = sdk.SpeechConfig.fromSubscription(speechKey, speechRegion);
    speechConfig.speechSynthesisVoiceName = azureVoice;
    speechConfig.speechSynthesisOutputFormat = sdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3;

    // Create output file path
    const audioDir = path.join(process.cwd(), 'public', 'audio');
    if (!fs.existsSync(audioDir)) {
      fs.mkdirSync(audioDir, { recursive: true });
    }

    const filename = `tts_${uuidv4()}.mp3`;
    const filePath = path.join(audioDir, filename);

    // Create audio config
    const audioConfig = sdk.AudioConfig.fromAudioFileOutput(filePath);

    // Create synthesizer
    const synthesizer = new sdk.SpeechSynthesizer(speechConfig, audioConfig);

    return new Promise((resolve) => {
      synthesizer.speakTextAsync(
        text,
        (result) => {
          if (result.reason === sdk.ResultReason.SynthesizingAudioCompleted) {
            synthesizer.close();
            resolve({
              status: 'success',
              translated_text: text,
              audio_path: `/audio/${filename}`
            });
          } else {
            synthesizer.close();
            resolve({
              status: 'error',
              error_message: `Speech synthesis failed: ${result.errorDetails}`
            });
          }
        },
        (error) => {
          synthesizer.close();
          resolve({
            status: 'error',
            error_message: `Speech synthesis error: ${error}`
          });
        }
      );
    });

  } catch (error) {
    return {
      status: 'error',
      error_message: `Azure TTS error: ${error instanceof Error ? error.message : 'Unknown error'}`
    };
  }
}
