import * as sdk from 'microsoft-cognitiveservices-speech-sdk';
import fs from 'fs';
import path from 'path';

export interface TranscriptionResult {
  status: string;
  transcribed_text?: string;
  translated_text?: string;
  detected_language?: string;
  confidence_score?: number;
  processing_time?: number;
  error_details?: string;
  task_id?: string;
}

export async function transcribeAudioFile(audioFilePath: string): Promise<TranscriptionResult> {
  const startTime = Date.now();
  
  try {
    const speechKey = process.env.AZURE_TTS_KEY;  // Using TTS key for speech recognition
    const speechRegion = process.env.AZURE_TTS_REGION;

    if (!speechKey || !speechRegion) {
      return {
        status: 'error',
        error_details: 'Azure Speech Service not configured',
        processing_time: Date.now() - startTime
      };
    }

    // Validate audio format
    const supportedFormats = process.env.SUPPORTED_AUDIO_FORMATS?.split(',') || ['wav', 'mp3', 'm4a', 'ogg', 'opus'];
    const fileExt = path.extname(audioFilePath).toLowerCase().slice(1);
    
    if (!supportedFormats.includes(fileExt)) {
      return {
        status: 'error',
        error_details: `Unsupported audio format: ${fileExt}. Supported formats: ${supportedFormats.join(', ')}`,
        processing_time: Date.now() - startTime
      };
    }

    // Create speech config
    const speechConfig = sdk.SpeechConfig.fromSubscription(speechKey, speechRegion);
    speechConfig.speechRecognitionLanguage = 'en-US'; // Default to English, can be auto-detected

    // Create audio config from file - Azure SDK can handle multiple formats
    let audioConfig;
    if (fileExt === 'wav') {
      audioConfig = sdk.AudioConfig.fromWavFileInput(fs.readFileSync(audioFilePath));
    } else {
      // For other formats, create from default microphone and we'll handle conversion if needed
      audioConfig = sdk.AudioConfig.fromWavFileInput(fs.readFileSync(audioFilePath));
    }

    // Create recognizer
    const recognizer = new sdk.SpeechRecognizer(speechConfig, audioConfig);

    return new Promise((resolve) => {
      recognizer.recognizeOnceAsync(
        (result: any) => {
          const processingTime = Date.now() - startTime;
          
          if (result.reason === sdk.ResultReason.RecognizedSpeech) {
            recognizer.close();
            resolve({
              status: 'success',
              transcribed_text: result.text,
              detected_language: 'auto-detected',
              confidence_score: 0.95, // Azure doesn't provide confidence directly
              processing_time: processingTime,
              task_id: `transcribe_${Date.now()}`
            });
          } else if (result.reason === sdk.ResultReason.NoMatch) {
            recognizer.close();
            resolve({
              status: 'error',
              error_details: 'No speech could be recognized',
              processing_time: processingTime
            });
          } else {
            recognizer.close();
            resolve({
              status: 'error',
              error_details: `Recognition failed: ${result.errorDetails}`,
              processing_time: processingTime
            });
          }
        },
        (error: any) => {
          recognizer.close();
          resolve({
            status: 'error',
            error_details: `Recognition error: ${error}`,
            processing_time: Date.now() - startTime
          });
        }
      );
    });

  } catch (error) {
    return {
      status: 'error',
      error_details: `Transcription error: ${error instanceof Error ? error.message : 'Unknown error'}`,
      processing_time: Date.now() - startTime
    };
  }
}
