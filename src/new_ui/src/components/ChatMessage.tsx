'use client';

import { ChatMessage, Language } from '@/types';
import { getTranslation } from '@/lib/constants';
import { useState } from 'react';

interface ChatMessageProps {
  message: ChatMessage;
  language: Language;
  onPlayAudio?: (audioUrl: string) => void;
}

export default function ChatMessageComponent({ 
  message, 
  language, 
  onPlayAudio 
}: ChatMessageProps) {
  const [isPlaying, setIsPlaying] = useState(false);

  const handlePlayAudio = () => {
    if (message.audioUrl && onPlayAudio) {
      setIsPlaying(true);
      onPlayAudio(message.audioUrl);
      // Reset playing state after a delay (you might want to use actual audio duration)
      setTimeout(() => setIsPlaying(false), 3000);
    }
  };

  const formatTime = (date: Date): string => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const getMessageIcon = (type: string) => {
    switch (type) {
      case 'user':
        return (
          <svg className="w-5 h-5 text-blue-600" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
          </svg>
        );
      case 'bot':
        return (
          <svg className="w-5 h-5 text-green-600" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
          </svg>
        );
      case 'system':
        return (
          <svg className="w-5 h-5 text-yellow-600" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
          </svg>
        );
      default:
        return null;
    }
  };

  return (
    <div 
      className={`
        chat-message message-enter
        ${message.type === 'user' ? 'user-message' : ''}
        ${message.type === 'bot' ? 'bot-message' : ''}
        ${message.type === 'system' ? 'system-message' : ''}
      `}
    >
      <div className="flex items-start space-x-3">
        <div className="flex-shrink-0 mt-1">
          {getMessageIcon(message.type)}
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-2">
              <span className="font-semibold text-sm capitalize text-gray-700">
                {message.type === 'user' ? 'You' : 
                 message.type === 'bot' ? 'Sanchalak' : 'System'}
              </span>
              <span className="text-xs text-gray-500">
                {formatTime(message.timestamp)}
              </span>
            </div>
            
            {message.audioUrl && (
              <button
                onClick={handlePlayAudio}
                disabled={isPlaying}
                className={`
                  flex items-center space-x-1 px-2 py-1 rounded-lg text-xs
                  transition-all duration-200
                  ${isPlaying 
                    ? 'bg-yellow-100 text-yellow-700 cursor-not-allowed' 
                    : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
                  }
                `}
                title={isPlaying ? getTranslation(language.code, 'speaking') : 'Play Audio'}
              >
                {isPlaying ? (
                  <>
                    <svg className="w-3 h-3 spin-fast" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M12 2v4l3-3h4v4l-3-3v10l3-3v4h-4l3-3H8l3 3V5l-3 3V2h4z"/>
                    </svg>
                    <span>{getTranslation(language.code, 'speaking')}</span>
                  </>
                ) : (
                  <>
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M8 5v14l11-7z"/>
                    </svg>
                    <span>🔊</span>
                  </>
                )}
              </button>
            )}
          </div>
          
          <div className="text-gray-800 leading-relaxed whitespace-pre-wrap">
            {message.content}
          </div>
        </div>
      </div>
    </div>
  );
}
