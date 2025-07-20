import { gql } from 'apollo-server-express';

export const typeDefs = gql`
  scalar Upload

  type AudioTranscriptionResult {
    status: String!
    transcribed_text: String
    error_details: String
  }

  type SpeechGenerationResult {
    status: String!
    audio_path: String
    error_message: String
  }

  type TranslationResult {
    status: String!
    translated_text: String
    detected_language: String
    error_message: String
  }

  type Mutation {
    transcribeAudio(file: Upload!): AudioTranscriptionResult!
    generateSpeech(text: String!, targetLanguage: String!): SpeechGenerationResult!
    translateText(text: String!, targetLanguage: String!, sourceLanguage: String): TranslationResult!
    detectLanguage(text: String!): TranslationResult!
  }

  type Query {
    healthCheck: String!
  }
`;
