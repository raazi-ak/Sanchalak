import { transcribeAudioFile } from '../services/transcriber';
import { generateSpeechFile } from '../services/azure';
import { translateText, detectLanguage } from '../services/translator';
import { logger } from '../services/logger';
import { Upload } from 'graphql-upload';
import fs from 'fs';
import path from 'path';
import { v4 as uuidv4 } from 'uuid';

interface UploadFile {
  filename: string;
  mimetype: string;
  encoding: string;
  createReadStream: () => NodeJS.ReadableStream;
}

export const resolvers = {
  Query: {
    healthCheck: () => "Backend is running!"
  },

  Mutation: {
    transcribeAudio: async (_: any, { file }: { file: Promise<UploadFile> }) => {
      try {
        logger.info('Starting audio transcription...');
        const { createReadStream, filename, mimetype } = await file;
        
        logger.debug(`File details: ${filename}, ${mimetype}`);
        
        // Validate file type - now supporting multiple audio formats
        const supportedMimeTypes = [
          'audio/wav', 'audio/wave',
          'audio/mp3', 'audio/mpeg',
          'audio/mp4', 'audio/m4a',
          'audio/ogg', 'audio/opus',
          'audio/webm'
        ];
        
        if (!supportedMimeTypes.some(type => mimetype.includes(type.split('/')[1]))) {
          logger.warn(`Unsupported audio format: ${mimetype}`);
          return {
            status: 'error',
            error_details: `Invalid file type: ${mimetype}. Supported formats: wav, mp3, m4a, ogg, opus, webm`
          };
        }

        // Create temporary file
        const tempDir = path.join(process.cwd(), 'temp');
        if (!fs.existsSync(tempDir)) {
          fs.mkdirSync(tempDir, { recursive: true });
        }

        const tempFilePath = path.join(tempDir, `${uuidv4()}_${filename}`);
        const stream = createReadStream();
        const writeStream = fs.createWriteStream(tempFilePath);

        // Save uploaded file
        await new Promise((resolve, reject) => {
          stream.pipe(writeStream);
          stream.on('end', resolve);
          stream.on('error', reject);
        });

        // Transcribe audio
        logger.debug(`Transcribing audio file: ${tempFilePath}`);
        const result = await transcribeAudioFile(tempFilePath);

        // Clean up temporary file
        fs.unlinkSync(tempFilePath);
        logger.debug('Temporary file cleaned up');

        logger.info(`Transcription completed with status: ${result.status}`);
        return result;

      } catch (error) {
        logger.error('Transcription error:', error);
        return {
          status: 'error',
          error_details: `Transcription failed: ${error instanceof Error ? error.message : 'Unknown error'}`
        };
      }
    },

    generateSpeech: async (_: any, { text, targetLanguage }: { text: string; targetLanguage: string }) => {
      try {
        logger.info(`Starting TTS generation for language: ${targetLanguage}`);
        logger.debug(`Text length: ${text.length} characters`);
        
        if (!text.trim()) {
          logger.warn('Empty text provided for TTS');
          return {
            status: 'error',
            error_message: 'Text cannot be empty'
          };
        }

        const result = await generateSpeechFile(text, targetLanguage);
        logger.info(`TTS generation completed with status: ${result.status}`);
        return result;

      } catch (error) {
        logger.error('TTS error:', error);
        return {
          status: 'error',
          error_message: `Speech generation failed: ${error instanceof Error ? error.message : 'Unknown error'}`
        };
      }
    },

    translateText: async (_: any, { text, targetLanguage, sourceLanguage }: { text: string; targetLanguage: string; sourceLanguage?: string }) => {
      try {
        logger.info(`Starting text translation: ${sourceLanguage || 'auto'} -> ${targetLanguage}`);
        logger.debug(`Text length: ${text.length} characters`);

        if (!text.trim()) {
          logger.warn('Empty text provided for translation');
          return {
            status: 'error',
            error_message: 'Text cannot be empty'
          };
        }

        let detectedSourceLanguage = sourceLanguage;
        if (!sourceLanguage) {
          logger.debug('Detecting source language...');
          const detectionResult = await detectLanguage(text);
          if (detectionResult.status !== 'success') {
            logger.warn('Language detection failed');
            return {
              status: 'error',
              error_message: 'Could not detect source language'
            };
          }
          detectedSourceLanguage = detectionResult.detected_language;
          logger.info(`Detected source language: ${detectedSourceLanguage}`);
        }

        const result = await translateText(text, targetLanguage, detectedSourceLanguage);
        logger.info(`Translation completed with status: ${result.status}`);
        return result;

      } catch (error) {
        logger.error('Translation error:', error);
        return {
          status: 'error',
          error_message: `Translation failed: ${error instanceof Error ? error.message : 'Unknown error'}`
        };
      }
    },

    detectLanguage: async (_: any, { text }: { text: string }) => {
      try {
        logger.info('Starting language detection...');
        logger.debug(`Text length: ${text.length} characters`);

        if (!text.trim()) {
          logger.warn('Empty text provided for language detection');
          return {
            status: 'error',
            error_message: 'Text cannot be empty'
          };
        }

        const result = await detectLanguage(text);
        logger.info(`Language detection completed with status: ${result.status}`);
        return result;

      } catch (error) {
        logger.error('Language detection error:', error);
        return {
          status: 'error',
          error_message: `Language detection failed: ${error instanceof Error ? error.message : 'Unknown error'}`
        };
      }
    }
  }
};
