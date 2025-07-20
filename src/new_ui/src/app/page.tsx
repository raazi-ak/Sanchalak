'use client';

import { useState, useCallback, useEffect } from 'react';
import { useMutation, useSubscription, ApolloProvider } from '@apollo/client';
import { ChatMessage, Language, ConversationProgress } from '@/types';
import { SUPPORTED_LANGUAGES, getTranslation } from '@/lib/constants';
import { 
  TRANSCRIBE_AUDIO, 
  GENERATE_SPEECH, 
  START_CONVERSATION, 
  SEND_MESSAGE, 
  GET_CONVERSATION,
  MESSAGE_STREAM 
} from '@/lib/graphql';
import { apolloClient } from '@/lib/apollo';
import LanguageSelector from '@/components/LanguageSelector';
import ChatInterface from '@/components/ChatInterface';

function SanchalakApp() {
  const [selectedLanguage, setSelectedLanguage] = useState<Language>(SUPPORTED_LANGUAGES[0]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [conversationStarted, setConversationStarted] = useState(false);
  const [progress, setProgress] = useState<ConversationProgress | undefined>();

  const [transcribeAudio] = useMutation(TRANSCRIBE_AUDIO);
  const [generateSpeech] = useMutation(GENERATE_SPEECH);
  const [startConversation] = useMutation(START_CONVERSATION);
  const [sendMessage] = useMutation(SEND_MESSAGE);

  // Simple translation function (in production, use a proper translation service)
  const translateMessage = (message: string, fromLang: string, toLang: string) => {
    // For now, return the original message
    // In production, integrate with Google Translate, Azure Translator, or similar
    if (fromLang === toLang) return message;
    
    // Simple keyword translations for common phrases
    const translations: Record<string, Record<string, string>> = {
      'name': {
        'hi': 'नाम',
        'gu': 'નામ',
        'bn': 'নাম',
        'ta': 'பெயர்',
        'te': 'పేరు',
        'ml': 'പേര്',
        'kn': 'ಹೆಸರು',
        'or': 'ନାମ',
        'pa': 'ਨਾਮ'
      },
      'age': {
        'hi': 'उम्र',
        'gu': 'ઉંમર',
        'bn': 'বয়স',
        'ta': 'வயது',
        'te': 'వయస్సు',
        'ml': 'വയസ്സ്',
        'kn': 'ವಯಸ್ಸು',
        'or': 'ବୟସ',
        'pa': 'ਉਮਰ'
      }
    };
    
    // For now, return original message - implement proper translation later
    return message;
  };

  // Subscribe to real-time messages - DISABLED for now to prevent duplicates
  // const { data: subscriptionData } = useSubscription(MESSAGE_STREAM, {
  //   variables: { sessionId: sessionId || '' },
  //   skip: !sessionId,
  //   onData: ({ data }) => {
  //     if (data?.data?.messageStream) {
  //       const newMessage = data.data.messageStream;
  //       addMessage(newMessage.content, 'bot');
  //     }
  //   },
  // });

  // Add initial welcome message and start conversation
  const addWelcomeMessage = useCallback(() => {
    const welcomeMessage: ChatMessage = {
      id: 'welcome-' + Date.now(),
      type: 'system',
      content: getTranslation(selectedLanguage.code, 'welcomeMessage'),
      timestamp: new Date(),
    };
    setMessages([welcomeMessage]);
    
    // Automatically start conversation after welcome message
    setTimeout(() => {
      startNewConversation();
    }, 500);
  }, [selectedLanguage.code]);

  // Initialize with welcome message
  useEffect(() => {
    addWelcomeMessage();
  }, [addWelcomeMessage]);

  const handleLanguageChange = (language: Language) => {
    setSelectedLanguage(language);
    // Reset conversation when language changes
    setSessionId(null);
    setConversationStarted(false);
    setMessages([]);
    // Update welcome message with new language
    addWelcomeMessage();
  };

  const addMessage = (content: string, type: 'user' | 'bot' | 'system', audioUrl?: string) => {
    const newMessage: ChatMessage = {
      id: Date.now().toString(),
      type,
      content,
      timestamp: new Date(),
      audioUrl,
    };
    setMessages(prev => [...prev, newMessage]);
    return newMessage;
  };

  const startNewConversation = async () => {
    try {
      setIsLoading(true);
      
      const { data } = await startConversation({
        variables: {
          input: {
            schemeCode: "pm-kisan",
            language: selectedLanguage.code
          }
        }
      });

      if (data?.startConversation) {
        const conversation = data.startConversation;
        setSessionId(conversation.id);
        setConversationStarted(true);
        
        // Update progress if available
        if (conversation.progress) {
          setProgress(conversation.progress);
        }
        
        // Always trigger the first question from LangGraph
        setTimeout(async () => {
          try {
            const { data: responseData } = await sendMessage({
              variables: {
                input: {
                  sessionId: conversation.id,
                  content: ""
                }
              }
            });
            
            if (responseData?.sendMessage) {
              addMessage(responseData.sendMessage.content, 'bot');
              // Update progress from response if available
              if (responseData.sendMessage.progress) {
                setProgress(responseData.sendMessage.progress);
              }
            }
          } catch (error) {
            console.error('Error getting first question:', error);
            addMessage('Hello! I\'m here to help you with your PM-KISAN application. What\'s your name?', 'bot');
          }
        }, 100);
        
        console.log('Conversation started:', conversation.id);
      }
    } catch (error) {
      console.error('Error starting conversation:', error);
      addMessage('Sorry, I encountered an error starting the conversation. Please try again.', 'bot');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendMessage = async (message: string) => {
    if (!message.trim()) return;

    // Start conversation if not already started
    if (!conversationStarted || !sessionId) {
      await startNewConversation();
      // Wait a bit for conversation to start
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Check if session was created successfully
      if (!sessionId) {
        addMessage('Error: No active conversation session. Please try again.', 'bot');
        return;
      }
    }

    setIsLoading(true);
    
    // Add user message
    addMessage(message, 'user');

    try {
      // Send message to LangGraph engine
      const { data } = await sendMessage({
        variables: {
          input: {
            sessionId: sessionId,
            content: message
          }
        }
      });

      if (data?.sendMessage) {
        const botResponse = data.sendMessage.content;
        
        // Update progress from response if available
        if (data.sendMessage.progress) {
          setProgress(data.sendMessage.progress);
        }
        
        // Generate TTS for bot response
        generateSpeech({
          variables: {
            text: botResponse,
            targetLanguage: selectedLanguage.code
          }
        }).then(({ data: ttsData }) => {
          const audioUrl = ttsData?.generateSpeech?.audio_path 
            ? `${process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:3001'}${ttsData.generateSpeech.audio_path}`
            : undefined;
          
          addMessage(botResponse, 'bot', audioUrl);
        }).catch(error => {
          console.error('TTS Error:', error);
          addMessage(botResponse, 'bot');
        }).finally(() => {
          setIsLoading(false);
        });
      } else {
        addMessage('Sorry, I didn\'t receive a response. Please try again.', 'bot');
        setIsLoading(false);
      }

    } catch (error) {
      console.error('Error sending message:', error);
      addMessage('Sorry, I encountered an error. Please try again.', 'bot');
      setIsLoading(false);
    }
  };

  const handleSendVoice = async (audioBlob: Blob) => {
    setIsLoading(true);

    try {
      // Convert blob to file for GraphQL upload
      const audioFile = new File([audioBlob], 'recording.webm', { type: 'audio/webm' });

      const { data } = await transcribeAudio({
        variables: {
          file: audioFile
        }
      });

      if (data?.transcribeAudio?.status === 'success' && data.transcribeAudio.transcribed_text) {
        const transcribedText = data.transcribeAudio.transcribed_text;
        
        // Add transcribed message as user input
        addMessage(`🎤 ${transcribedText}`, 'user');
        
        // Process the transcribed text as a regular message
        setTimeout(() => {
          handleSendMessage(transcribedText);
        }, 500);
      } else {
        addMessage('Sorry, I could not understand your voice message. Please try again.', 'bot');
        setIsLoading(false);
      }

    } catch (error) {
      console.error('Error processing voice:', error);
      addMessage('Error processing voice input. Please try again.', 'bot');
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen p-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="agricultural-gradient rounded-xl p-6 mb-6 shadow-lg border border-green-200">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between space-y-4 lg:space-y-0">
            <div className="text-center lg:text-left">
              <h1 className="text-3xl lg:text-4xl font-bold text-green-800 mb-2">
                🏛️ {getTranslation(selectedLanguage.code, 'title')}
              </h1>
              <p className="text-lg text-green-700">
                {getTranslation(selectedLanguage.code, 'subtitle')}
              </p>
              {sessionId && (
                <p className="text-sm text-green-600 mt-2">
                  Session: {sessionId.substring(0, 8)}...
                </p>
              )}
            </div>
            
            <div className="flex flex-col items-center space-y-2">
              <label className="text-sm font-medium text-green-800">
                🌐 {getTranslation(selectedLanguage.code, 'languageLabel')}
              </label>
              <LanguageSelector
                selectedLanguage={selectedLanguage}
                onLanguageChange={handleLanguageChange}
              />
            </div>
          </div>
        </div>

        {/* Chat Interface */}
        <div className="h-[70vh] lg:h-[75vh]">
          <ChatInterface
            messages={messages}
            onSendMessage={handleSendMessage}
            onSendVoice={handleSendVoice}
            language={selectedLanguage}
            isLoading={isLoading}
            progress={progress}
          />
        </div>

        {/* Footer */}
        <div className="mt-6 text-center text-sm text-gray-600">
          <p>
            🌾 Built with Next.js, TypeScript, and GraphQL | 
            🗣️ Supports: {SUPPORTED_LANGUAGES.map(lang => lang.nativeName).join(', ')}
          </p>
        </div>
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <ApolloProvider client={apolloClient}>
      <SanchalakApp />
    </ApolloProvider>
  );
}
