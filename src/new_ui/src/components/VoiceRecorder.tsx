'use client';

import { useState, useRef, useCallback } from 'react';
import { RecordingState, Language } from '@/types';
import { getTranslation } from '@/lib/constants';

interface VoiceRecorderProps {
  onRecordingComplete: (audioBlob: Blob) => void;
  language: Language;
  disabled?: boolean;
}

export default function VoiceRecorder({ 
  onRecordingComplete, 
  language, 
  disabled = false 
}: VoiceRecorderProps) {
  const [recordingState, setRecordingState] = useState<RecordingState>({
    isRecording: false,
    isProcessing: false,
    recordingTime: 0,
  });

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const startRecording = useCallback(async () => {
    if (disabled || recordingState.isRecording) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 44100,
        }
      });

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported('audio/webm;codecs=opus') 
          ? 'audio/webm;codecs=opus' 
          : 'audio/webm'
      });

      chunksRef.current = [];
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(chunksRef.current, { 
          type: 'audio/webm' 
        });
        
        // Stop all tracks to release microphone
        stream.getTracks().forEach(track => track.stop());
        
        setRecordingState(prev => ({ 
          ...prev, 
          isRecording: false, 
          isProcessing: true 
        }));
        
        onRecordingComplete(audioBlob);
        
        setTimeout(() => {
          setRecordingState(prev => ({ 
            ...prev, 
            isProcessing: false, 
            recordingTime: 0 
          }));
        }, 1000);
      };

      mediaRecorder.start();
      setRecordingState(prev => ({ ...prev, isRecording: true }));

      // Start timer
      timerRef.current = setInterval(() => {
        setRecordingState(prev => ({ 
          ...prev, 
          recordingTime: prev.recordingTime + 1 
        }));
      }, 1000);

    } catch (error) {
      console.error('Error starting recording:', error);
      alert(getTranslation(language.code, 'noMicrophone'));
    }
  }, [disabled, recordingState.isRecording, onRecordingComplete, language.code]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && recordingState.isRecording) {
      mediaRecorderRef.current.stop();
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
  }, [recordingState.isRecording]);

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const handleClick = () => {
    if (recordingState.isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  return (
    <div className="flex flex-col items-center space-y-2">
      <button
        onClick={handleClick}
        disabled={disabled || recordingState.isProcessing}
        className={`
          control-btn
          ${recordingState.isRecording ? 'recording-btn animate-recording-pulse' : ''}
          ${recordingState.isProcessing ? 'processing-btn animate-processing-rotate' : ''}
          ${!recordingState.isRecording && !recordingState.isProcessing ? 'send-btn' : ''}
          ${disabled ? 'opacity-50 cursor-not-allowed' : 'hover:scale-105'}
        `}
        title={
          recordingState.isRecording 
            ? getTranslation(language.code, 'recordingText')
            : recordingState.isProcessing
            ? getTranslation(language.code, 'processingText')
            : getTranslation(language.code, 'recordButton')
        }
      >
        {recordingState.isRecording ? (
          <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
            <rect x="6" y="6" width="12" height="12" rx="2" />
          </svg>
        ) : recordingState.isProcessing ? (
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        ) : (
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
          </svg>
        )}
      </button>
      
      {recordingState.isRecording && (
        <div className="text-sm text-red-600 font-medium animate-pulse">
          🔴 {getTranslation(language.code, 'recordingText')} {formatTime(recordingState.recordingTime)}
        </div>
      )}
      
      {recordingState.isProcessing && (
        <div className="text-sm text-yellow-600 font-medium">
          ⚙️ {getTranslation(language.code, 'processingText')}
        </div>
      )}
    </div>
  );
}
