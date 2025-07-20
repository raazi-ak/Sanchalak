'use client';

import { useState, useRef, useEffect } from 'react';
import { ChatMessage, Language, ConversationProgress } from '@/types';
import { getTranslation } from '@/lib/constants';
import VoiceRecorder from './VoiceRecorder';
import ChatMessageComponent from './ChatMessage';
import ProgressTracker from './ProgressTracker';

interface ChatInterfaceProps {
  messages: ChatMessage[];
  onSendMessage: (message: string) => void;
  onSendVoice: (audioBlob: Blob) => void;
  language: Language;
  isLoading?: boolean;
  progress?: ConversationProgress;
}

export default function ChatInterface({
  messages,
  onSendMessage,
  onSendVoice,
  language,
  isLoading = false,
  progress
}: ChatInterfaceProps) {
  const [inputValue, setInputValue] = useState('');
  const [currentAudio, setCurrentAudio] = useState<HTMLAudioElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputValue.trim() && !isLoading) {
      onSendMessage(inputValue.trim());
      setInputValue('');
      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value);
    
    // Auto-resize textarea
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + 'px';
    }
  };

  const handleVoiceRecording = (audioBlob: Blob) => {
    onSendVoice(audioBlob);
  };

  const handlePlayAudio = (audioUrl: string) => {
    // Stop current audio if playing
    if (currentAudio) {
      currentAudio.pause();
      currentAudio.currentTime = 0;
    }

    // Create and play new audio
    const audio = new Audio(audioUrl);
    setCurrentAudio(audio);
    
    audio.play().catch(error => {
      console.error('Error playing audio:', error);
      alert(getTranslation(language.code, 'errorPlayback'));
    });

    audio.onended = () => {
      setCurrentAudio(null);
    };
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-xl shadow-lg border border-green-200">
      {/* Chat Header */}
      <div className="agricultural-gradient p-4 rounded-t-xl border-b border-green-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-green-600 rounded-full flex items-center justify-center">
              <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
              </svg>
            </div>
            <div>
              <h2 className="text-lg font-bold text-green-800">
                {getTranslation(language.code, 'title')}
              </h2>
              <p className="text-sm text-green-600">
                {getTranslation(language.code, 'subtitle')}
              </p>
            </div>
          </div>
          
          {isLoading && (
            <div className="flex items-center space-x-2 text-green-700">
              <svg className="spin-fast w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 2v4l3-3h4v4l-3-3v10l3-3v4h-4l3-3H8l3 3V5l-3 3V2h4z"/>
              </svg>
              <span className="text-sm">{getTranslation(language.code, 'processingText')}</span>
            </div>
          )}
        </div>
      </div>

      {/* Progress Tracker */}
      {progress && <ProgressTracker progress={progress} />}

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center text-gray-500 max-w-md">
              <svg className="w-16 h-16 mx-auto mb-4 text-green-400" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
              </svg>
              <p className="text-lg font-medium mb-2">
                {getTranslation(language.code, 'welcomeMessage')}
              </p>
              <p className="text-sm">
                Start by typing a message or recording your voice
              </p>
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <ChatMessageComponent
                key={message.id}
                message={message}
                language={language}
                onPlayAudio={handlePlayAudio}
              />
            ))}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 border-t border-green-200 bg-gradient-to-r from-green-50 to-green-100">
        <form onSubmit={handleSubmit} className="flex items-end space-x-3">
          <div className="flex-1">
            <textarea
              ref={textareaRef}
              value={inputValue}
              onChange={handleInputChange}
              onKeyPress={handleKeyPress}
              placeholder={getTranslation(language.code, 'placeholderText')}
              className="w-full px-4 py-3 border-2 border-green-300 rounded-xl 
                         focus:ring-2 focus:ring-green-500 focus:border-transparent
                         resize-none transition-all duration-200 text-gray-800
                         min-h-[50px] max-h-[120px]"
              rows={1}
              disabled={isLoading}
            />
          </div>
          
          <div className="flex items-center space-x-2">
            <VoiceRecorder
              onRecordingComplete={handleVoiceRecording}
              language={language}
              disabled={isLoading}
            />
            
            <button
              type="submit"
              disabled={!inputValue.trim() || isLoading}
              className={`
                control-btn send-btn
                ${(!inputValue.trim() || isLoading) ? 'opacity-50 cursor-not-allowed' : 'hover:scale-105'}
              `}
              title={getTranslation(language.code, 'sendButton')}
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
