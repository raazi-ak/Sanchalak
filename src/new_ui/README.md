# Sanchalak - Government Scheme Assistant (Monorepo)

A complete full-stack application for the Sanchalak government scheme assistant. This monorepo contains both the Next.js frontend and Node.js GraphQL backend, providing a multilingual chat experience with voice input/output capabilities for helping farmers with government schemes.

## 🏗️ Project Structure

```
sanchalak-monorepo/
├── frontend (root)          # Next.js frontend application
│   ├── src/
│   │   ├── app/            # Next.js App Router
│   │   ├── components/     # React components  
│   │   ├── lib/           # Utilities & GraphQL
│   │   └── types/         # TypeScript types
│   ├── package.json       # Frontend dependencies
│   └── ...
├── backend/                # Node.js GraphQL backend
│   ├── src/
│   │   ├── graphql/       # GraphQL schema & resolvers
│   │   ├── services/      # Azure Speech & Transcription
│   │   └── index.ts       # Server entry point
│   ├── public/audio/      # Generated audio files
│   ├── package.json       # Backend dependencies
│   └── .env              # Backend configuration
└── setup.bat/setup.sh     # Setup scripts
```

## Features

- 🗣️ **Multilingual Support**: 10 Indian languages (English, Hindi, Gujarati, Punjabi, Bengali, Telugu, Tamil, Malayalam, Kannada, Odia)
- 🎤 **Voice Input**: Record voice messages for hands-free interaction
- 🔊 **Text-to-Speech**: Automatic audio playback of bot responses
- 💬 **Real-time Chat**: Modern chat interface with message history
- 🌾 **Agricultural Theme**: Government scheme focused design
- 📱 **Responsive Design**: Works on desktop and mobile devices

## Tech Stack

- **Framework**: Next.js 14 with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **GraphQL**: Apollo Client
- **Audio**: Web Audio API for recording
- **Deployment**: Vercel-ready

## GraphQL Integration

The frontend integrates with a GraphQL backend providing:

- `transcribeAudio(file: Upload!)`: Convert audio to text
- `generateSpeech(text: String!, targetLanguage: String!)`: Convert text to speech

## 🚀 Quick Start

### Automatic Setup (Recommended)

**Windows:**
```cmd
setup.bat
```

**Linux/macOS:**
```bash
chmod +x setup.sh
./setup.sh
```

### Manual Setup

1. **Install dependencies:**
```bash
npm install                    # Frontend dependencies
cd backend && npm install      # Backend dependencies
```

2. **Configure environment variables:**

Frontend (`.env.local`):
```env
NEXT_PUBLIC_GRAPHQL_URL=http://localhost:3001/graphql
NEXT_PUBLIC_BACKEND_URL=http://localhost:3001
```

Backend (`backend/.env`):
```env
# Azure Speech Service Configuration
AZURE_SPEECH_KEY=your-azure-speech-key
AZURE_SPEECH_REGION=your-azure-region

# Server Configuration
PORT=3001
NODE_ENV=development
CORS_ORIGIN=http://localhost:3000
```

3. **Start the application:**
```bash
npm run dev:all               # Start both frontend and backend
# OR
npm run dev                   # Frontend only (port 3000)
npm run dev:backend          # Backend only (port 3001)
```

4. **Open your browser:**
- Frontend: http://localhost:3000
- GraphQL Playground: http://localhost:3001/graphql

## Project Structure

```
src/
├── app/                 # Next.js App Router
│   ├── layout.tsx      # Root layout
│   ├── page.tsx        # Home page
│   └── globals.css     # Global styles
├── components/         # React components
│   ├── ChatInterface.tsx
│   ├── ChatMessage.tsx
│   ├── LanguageSelector.tsx
│   └── VoiceRecorder.tsx
├── lib/               # Utilities
│   ├── apollo.ts      # GraphQL client
│   ├── constants.ts   # Language constants
│   └── graphql.ts     # GraphQL queries
└── types/             # TypeScript types
    └── index.ts
```

## 📚 Available Scripts

### Monorepo Commands
- `npm run dev:all` - Start both frontend and backend in development mode
- `npm run build:all` - Build both frontend and backend for production
- `npm run start:all` - Start both in production mode
- `npm run install:all` - Install dependencies for both projects

### Frontend Commands  
- `npm run dev` - Start Next.js development server (port 3000)
- `npm run build` - Build frontend for production
- `npm run start` - Start frontend production server
- `npm run lint` - Run ESLint on frontend code

### Backend Commands
- `npm run dev:backend` - Start GraphQL server in development mode (port 3001)  
- `npm run build:backend` - Build backend for production
- `npm run start:backend` - Start backend production server

## 🔧 Technology Stack

### Frontend
- **Framework**: Next.js 14 with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **GraphQL**: Apollo Client
- **Audio**: Web Audio API for recording

### Backend  
- **Runtime**: Node.js with Express
- **GraphQL**: Apollo Server
- **Speech Services**: Azure Cognitive Services
- **File Upload**: GraphQL Upload
- **Language**: TypeScript

## Customization

### Adding Languages
1. Add language to `SUPPORTED_LANGUAGES` in `src/lib/constants.ts`
2. Add translations to `TRANSLATIONS` object
3. Update GraphQL backend language support

### Styling
- Modify Tailwind config in `tailwind.config.ts`
- Update CSS variables in `globals.css`
- Customize component styles with Tailwind classes

### Backend Integration
- Update GraphQL schema in `src/lib/graphql.ts`
- Modify Apollo Client config in `src/lib/apollo.ts`
- Add new mutations/queries as needed

## Integration with Backend

This frontend is designed to work with the GraphQL backend located in the `../backend` directory. Make sure the backend is running before starting the frontend.

## Deployment

### Vercel
```bash
npm install -g vercel
vercel
```

### Docker
```bash
docker build -t sanchalak-frontend .
docker run -p 3000:3000 sanchalak-frontend
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is part of the Sanchalak government scheme assistant system.
