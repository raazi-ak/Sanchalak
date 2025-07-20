export interface Language {
  code: string;
  name: string;
  nativeName: string;
}

export interface ChatMessage {
  id: string;
  type: 'user' | 'bot' | 'system';
  content: string;
  timestamp: Date;
  audioUrl?: string;
  isPlaying?: boolean;
}

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

export interface TTSResult {
  status: string;
  translated_text?: string;
  audio_path?: string;
  error_message?: string;
}

export interface RecordingState {
  isRecording: boolean;
  isProcessing: boolean;
  audioBlob?: Blob;
  mediaRecorder?: MediaRecorder;
  recordingTime: number;
}

export interface VoiceInputProps {
  onTranscription: (text: string) => void;
  language: Language;
  disabled?: boolean;
}

export interface StageProgress {
  collected: number;
  total: number;
  percentage: number;
  isComplete: boolean;
}

export interface ConversationProgress {
  basicInfo: StageProgress;
  familyMembers: StageProgress;
  exclusionCriteria: StageProgress;
  specialProvisions: StageProgress;
  overallPercentage: number;
}

export interface ChatInterfaceProps {
  messages: ChatMessage[];
  onSendMessage: (message: string) => void;
  onSendVoice: (audioBlob: Blob) => void;
  language: Language;
  isLoading?: boolean;
  progress?: ConversationProgress;
}
