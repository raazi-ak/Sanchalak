'use client';

import { Language } from '@/types';
import { SUPPORTED_LANGUAGES } from '@/lib/constants';

interface LanguageSelectorProps {
  selectedLanguage: Language;
  onLanguageChange: (language: Language) => void;
}

export default function LanguageSelector({ 
  selectedLanguage, 
  onLanguageChange 
}: LanguageSelectorProps) {
  return (
    <div className="relative">
      <select
        value={selectedLanguage.code}
        onChange={(e) => {
          const language = SUPPORTED_LANGUAGES.find(lang => lang.code === e.target.value);
          if (language) onLanguageChange(language);
        }}
        className="appearance-none bg-white border-2 border-green-300 rounded-lg px-4 py-2 pr-8 
                   text-green-800 font-medium shadow-sm hover:border-green-400 
                   focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent
                   transition-all duration-200"
      >
        {SUPPORTED_LANGUAGES.map((language) => (
          <option key={language.code} value={language.code}>
            {language.nativeName}
          </option>
        ))}
      </select>
      <div className="absolute inset-y-0 right-0 flex items-center px-2 pointer-events-none">
        <svg 
          className="w-4 h-4 text-green-600" 
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path 
            strokeLinecap="round" 
            strokeLinejoin="round" 
            strokeWidth={2} 
            d="M19 9l-7 7-7-7" 
          />
        </svg>
      </div>
    </div>
  );
}
