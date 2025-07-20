import axios from 'axios';
import { logger } from './logger';

// Language mapping for Azure Translator
const AZURE_LANGUAGE_MAP: Record<string, string> = {
  'en': 'en',
  'hi': 'hi',
  'gu': 'gu',
  'pa': 'pa',
  'bn': 'bn',
  'te': 'te',
  'ta': 'ta',
  'ml': 'ml',
  'kn': 'kn',
  'or': 'or'
};

export interface TranslationResult {
  status: string;
  translated_text?: string;
  detected_language?: string;
  error_message?: string;
}

export async function translateText(text: string, targetLanguage: string, sourceLanguage?: string): Promise<TranslationResult> {
  try {
    logger.debug(`Translation request: ${sourceLanguage || 'auto'} -> ${targetLanguage}, text length: ${text.length}`);
    
    const translatorKey = process.env.AZURE_TRANSLATOR_KEY;
    const translatorRegion = process.env.AZURE_TRANSLATOR_REGION;
    const translatorEndpoint = process.env.AZURE_TRANSLATOR_ENDPOINT;

    if (!translatorKey || !translatorRegion || !translatorEndpoint) {
      logger.error('Azure Translator Service not configured');
      return {
        status: 'error',
        error_message: 'Azure Translator Service not configured'
      };
    }

    // Get Azure language code
    const azureTargetLang = AZURE_LANGUAGE_MAP[targetLanguage] || 'en';
    const azureSourceLang = sourceLanguage ? AZURE_LANGUAGE_MAP[sourceLanguage] : undefined;

    // Build URL
    let url = `${translatorEndpoint}/translate?api-version=3.0&to=${azureTargetLang}`;
    if (azureSourceLang) {
      url += `&from=${azureSourceLang}`;
    }

    const headers = {
      'Ocp-Apim-Subscription-Key': translatorKey,
      'Ocp-Apim-Subscription-Region': translatorRegion,
      'Content-Type': 'application/json'
    };

    const body = [{ Text: text }];

    const response = await axios.post(url, body, { headers });
    
    if (response.data && response.data[0] && response.data[0].translations) {
      const translatedText = response.data[0].translations[0].text;
      const detectedLanguage = response.data[0].detectedLanguage?.language || sourceLanguage || 'unknown';
      
      logger.debug(`Translation successful: ${detectedLanguage} -> ${targetLanguage}`);
      
      return {
        status: 'success',
        translated_text: translatedText,
        detected_language: detectedLanguage
      };
    } else {
      throw new Error('Invalid response format from Azure Translator');
    }

  } catch (error) {
    logger.error('Translation error:', error);
    return {
      status: 'error',
      error_message: `Translation failed: ${error instanceof Error ? error.message : 'Unknown error'}`
    };
  }
}

export async function detectLanguage(text: string): Promise<TranslationResult> {
  try {
    logger.debug(`Language detection request for text length: ${text.length}`);
    
    const translatorKey = process.env.AZURE_TRANSLATOR_KEY;
    const translatorRegion = process.env.AZURE_TRANSLATOR_REGION;
    const translatorEndpoint = process.env.AZURE_TRANSLATOR_ENDPOINT;

    if (!translatorKey || !translatorRegion || !translatorEndpoint) {
      logger.error('Azure Translator Service not configured');
      return {
        status: 'error',
        error_message: 'Azure Translator Service not configured'
      };
    }

    const url = `${translatorEndpoint}/detect?api-version=3.0`;

    const headers = {
      'Ocp-Apim-Subscription-Key': translatorKey,
      'Ocp-Apim-Subscription-Region': translatorRegion,
      'Content-Type': 'application/json'
    };

    const body = [{ Text: text }];

    const response = await axios.post(url, body, { headers });
    
    if (response.data && response.data[0]) {
      const detectedLanguage = response.data[0].language;
      const confidence = response.data[0].score;
      
      logger.debug(`Language detected: ${detectedLanguage} (confidence: ${confidence})`);
      
      return {
        status: 'success',
        detected_language: detectedLanguage
      };
    } else {
      throw new Error('Invalid response format from Azure Translator');
    }

  } catch (error) {
    logger.error('Language detection error:', error);
    return {
      status: 'error',
      error_message: `Language detection failed: ${error instanceof Error ? error.message : 'Unknown error'}`
    };
  }
} 