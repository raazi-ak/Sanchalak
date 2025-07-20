<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

# Sanchalak Frontend - GitHub Copilot Instructions

This is a Next.js TypeScript frontend for the Sanchalak government scheme assistant application.

## Project Context
- **Application**: Government scheme eligibility checker for farmers
- **Theme**: Agricultural government theme with green, blue, and earth tones
- **Backend**: GraphQL API with mutations for `transcribeAudio` and `generateSpeech`
- **Languages**: Supports 10 Indian languages (English, Hindi, Gujarati, Punjabi, Bengali, Telugu, Tamil, Malayalam, Kannada, Odia)

## Key Features
- Multilingual chat interface
- Voice recording and playback
- GraphQL integration for TTS and transcription
- Agricultural theme matching the original Streamlit interface
- Real-time conversation flow

## Technical Stack
- Next.js 14 with App Router
- TypeScript
- Tailwind CSS
- Apollo Client for GraphQL
- Web Audio API for voice recording

## Code Style Guidelines
- Use TypeScript for all components
- Follow React functional component patterns with hooks
- Use Tailwind CSS for styling with custom agricultural color palette
- Implement proper error handling for API calls
- Use proper accessibility practices for voice interfaces

## GraphQL Schema
- Mutation: `transcribeAudio(file: Upload!): TranscriptionResult`
- Mutation: `generateSpeech(text: String!, targetLanguage: String!): TTSResult`

## Important Notes
- The backend GraphQL server runs on the port specified in the backend configuration
- Voice recording should provide visual feedback during recording
- All UI text should be internationalized based on selected language
- Audio files should be handled as File/Blob objects for GraphQL upload
