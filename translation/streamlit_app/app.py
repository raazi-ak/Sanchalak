import streamlit as st
import io
import base64
import json
import uuid
from streamlit.components.v1 import html
from utils import transcribe_audio, tts_response, audio_to_bytesio, autoplay_audio
import requests
import tempfile
import os
import time

# Configuration
SANCHALAK_API_BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Initialize session state variables
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid.uuid4())

if "conversation_stage" not in st.session_state:
    st.session_state.conversation_stage = "greeting"

if "farmer_data" not in st.session_state:
    st.session_state.farmer_data = {}

if "first_visit" not in st.session_state:
    st.session_state.first_visit = True

if "selected_language" not in st.session_state:
    st.session_state.selected_language = "English"

# Page Configuration
st.set_page_config(
    page_title="Sanchalak - Government Scheme Eligibility Checker",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Language options
language_options = {
    "English": "en",
    "Hindi (हिन्दी)": "hi",
    "Gujarati (ગુજરાતી)": "gu", 
    "Punjabi (ਪੰਜਾਬੀ)": "pa",
    "Bengali (বাংলা)": "bn",
    "Telugu (తెలుగు)": "te",
    "Tamil (தமிழ்)": "ta",
    "Malayalam (മലയാളം)": "ml",
    "Kannada (ಕನ್ನಡ)": "kn",
    "Odia (ଓଡ଼ିଆ)": "or"
}

# Multilingual content for government scheme checker
language_content = {
    "en": {
        "app_title": "🏛️ Sanchalak - Government Scheme Eligibility Checker",
        "app_subtitle": "Your Digital Assistant for Agricultural Government Schemes",
        "language_header": "🌐 Choose Your Language",
        "language_help": "Select your preferred language:",
        "chat_header": "💬 Scheme Eligibility Conversation",
        "input_placeholder": "Type your message here or use voice recording...",
        "record_btn": "🎙️ Record Voice",
        "send_btn": "📤 Send",
        "clear_btn": "🧹 Clear Chat",
        "you_label": "👨‍🌾 You:",
        "bot_label": "🏛️ Sanchalak:",
        "processing": "🔄 Processing your request...",
        "footer_text": "Supported Languages: English, Hindi, Gujarati, Punjabi, Bengali, Telugu, Tamil, Malayalam, Kannada, Odia",
        "system_greeting": "🙏 Namaste! I am Sanchalak, your government scheme assistant. I help farmers check eligibility for various agricultural schemes like PM-KISAN, Soil Health Card, Pradhan Mantri Fasal Bima Yojana, and more.\n\nTo get started, please tell me:\n1. Your name\n2. Your state and district\n3. Your farming details (land size, crops grown)\n\nYou can speak in your regional language or type your response."
    },
    "hi": {
        "app_title": "🏛️ संचालक - सरकारी योजना पात्रता जांचकर्ता",
        "app_subtitle": "कृषि सरकारी योजनाओं के लिए आपका डिजिटल सहायक",
        "language_header": "🌐 अपनी भाषा चुनें",
        "language_help": "अपनी पसंदीदा भाषा चुनें:",
        "chat_header": "💬 योजना पात्रता बातचीत",
        "input_placeholder": "यहाँ अपना संदेश टाइप करें या आवाज़ रिकॉर्डिंग का उपयोग करें...",
        "record_btn": "🎙️ आवाज़ रिकॉर्ड करें",
        "send_btn": "📤 भेजें",
        "clear_btn": "🧹 चैट साफ़ करें",
        "you_label": "👨‍🌾 आप:",
        "bot_label": "🏛️ संचालक:",
        "processing": "🔄 आपके अनुरोध को संसाधित कर रहे हैं...",
        "footer_text": "समर्थित भाषाएं: अंग्रेजी, हिंदी, गुजराती, पंजाबी, बंगाली, तेलुगु, तमिल, मलयालम, कन्नड़, उड़िया",
        "system_greeting": "🙏 नमस्ते! मैं संचालक हूँ, आपका सरकारी योजना सहायक। मैं किसानों को विभिन्न कृषि योजनाओं जैसे पीएम-किसान, मृदा स्वास्थ्य कार्ड, प्रधानमंत्री फसल बीमा योजना आदि के लिए पात्रता जांचने में मदद करता हूँ।\n\nशुरू करने के लिए, कृपया मुझे बताएं:\n1. आपका नाम\n2. आपका राज्य और जिला\n3. आपकी खेती का विवरण (भूमि का आकार, उगाई जाने वाली फसलें)\n\nआप अपनी क्षेत्रीय भाषा में बोल सकते हैं या अपना उत्तर टाइप कर सकते हैं।"
    },
    "gu": {
        "app_title": "🏛️ સંચાલક - સરકારી યોજના પાત્રતા તપાસકર્તા",
        "app_subtitle": "કૃષિ સરકારી યોજનાઓ માટે તમારો ડિજિટલ સહાયક",
        "language_header": "🌐 તમારી ભાષા પસંદ કરો",
        "language_help": "તમારી પસંદીદા ભાષા પસંદ કરો:",
        "chat_header": "💬 યોજના પાત્રતા વાતચીત",
        "input_placeholder": "અહીં તમારો સંદેશ ટાઇપ કરો અથવા વૉઇસ રેકોર્ડિંગનો ઉપયોગ કરો...",
        "record_btn": "🎙️ અવાજ રેકોર્ડ કરો",
        "send_btn": "📤 મોકલો",
        "clear_btn": "🧹 ચેટ સાફ કરો",
        "you_label": "👨‍🌾 તમે:",
        "bot_label": "🏛️ સંચાલક:",
        "processing": "🔄 તમારી વિનંતી પર કામ કરી રહ્યા છીએ...",
        "footer_text": "સપોર્ટેડ ભાષાઓ: અંગ્રેજી, હિન્દી, ગુજરાતી, પંજાબી, બંગાળી, તેલુગુ, તમિલ, મલયાલમ, કન્નડ, ઓડિયા",
        "system_greeting": "🙏 નમસ્તે! હું સંચાલક છું, તમારો સરકારી યોજના સહાયક. હું ખેડૂતોને PM-KISAN, માટી આરોગ્ય કાર્ડ, પ્રધાનમંત્રી ફસલ વીમા યોજના જેવી વિવિધ કૃષિ યોજનાઓ માટે પાત્રતા તપાસવામાં મદદ કરું છું.\n\nશરૂ કરવા માટે, કૃપા કરીને મને કહો:\n1. તમારું નામ\n2. તમારું રાજ્ય અને જિલ્લો\n3. તમારી ખેતીની વિગતો (જમીનનું કદ, ઉગાડેલા પાકો)\n\nતમે તમારી પ્રાદેશિક ભાષામાં બોલી શકો છો અથવા તમારો જવાબ ટાઇપ કરી શકો છો."
    }
}

# Enhanced Agricultural Theme CSS
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');
    
    /* Root variables for agricultural government theme */
    :root {
        --primary-green: #2E7D32;
        --secondary-green: #4CAF50;
        --accent-green: #66BB6A;
        --light-green: #C8E6C9;
        --government-blue: #1976D2;
        --scheme-gold: #FFB300;
        --earth-brown: #8D6E63;
        --official-red: #D32F2F;
    }
    
    /* Main app styling */
    .main {
        padding: 1rem;
        background: linear-gradient(135deg, #E8F5E8 0%, #F1F8E9 50%, #E3F2FD 100%);
        min-height: 100vh;
        font-family: 'Poppins', sans-serif;
    }
    
    .stApp {
        background: linear-gradient(135deg, #E8F5E8 0%, #F1F8E9 50%, #E3F2FD 100%);
        font-family: 'Poppins', sans-serif;
    }
    
    /* Header styling */
    .header-container {
        background: linear-gradient(135deg, var(--government-blue) 0%, var(--primary-green) 100%);
        color: white;
        padding: 2.5rem;
        border-radius: 20px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 10px 30px rgba(25, 118, 210, 0.4);
        position: relative;
        overflow: hidden;
    }
    
    .header-title {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    
    .header-subtitle {
        font-size: 1.2rem;
        opacity: 0.95;
        font-weight: 300;
    }
    
    /* Chat container */
    .chat-container {
        background: white;
        border-radius: 20px;
        padding: 1.5rem;
        margin: 1.5rem 0;
        box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        border: 2px solid var(--light-green);
        max-height: 500px;
        overflow-y: auto;
    }
    
    /* Chat messages */
    .chat-message {
        margin: 1rem 0;
        padding: 1rem;
        border-radius: 15px;
        animation: slideIn 0.3s ease-out;
    }
    
    @keyframes slideIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .user-message {
        background: linear-gradient(135deg, #E3F2FD 0%, #BBDEFB 100%);
        border-left: 4px solid var(--government-blue);
        margin-left: 2rem;
    }
    
    .bot-message {
        background: linear-gradient(135deg, #F1F8E9 0%, #DCEDC8 100%);
        border-left: 4px solid var(--secondary-green);
        margin-right: 2rem;
    }
    
    .system-message {
        background: linear-gradient(135deg, #FFF8E1 0%, #FFECB3 100%);
        border-left: 4px solid var(--scheme-gold);
        text-align: center;
        margin: 1rem 0;
    }
    
    /* Input area */
    .input-container {
        background: white;
        border-radius: 25px;
        padding: 1rem;
        margin: 1rem 0;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        border: 2px solid var(--light-green);
        display: flex;
        gap: 1rem;
        align-items: center;
    }
    
    .chat-input {
        flex: 1;
        border: none;
        outline: none;
        font-size: 1rem;
        padding: 0.5rem;
        font-family: 'Poppins', sans-serif;
    }
    
    .input-controls {
        display: flex;
        gap: 0.5rem;
        align-items: center;
    }
    
    .control-btn {
        background: linear-gradient(135deg, var(--secondary-green) 0%, var(--accent-green) 100%);
        border: none;
        border-radius: 50%;
        width: 45px;
        height: 45px;
        color: white;
        font-size: 1.1rem;
        cursor: pointer;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(76, 175, 80, 0.3);
    }
    
    .control-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(76, 175, 80, 0.4);
    }
    
    .recording-btn {
        background: linear-gradient(135deg, #E53935 0%, #C62828 100%) !important;
        animation: recordingPulse 1.5s ease-in-out infinite;
    }
    
    @keyframes recordingPulse {
        0%, 100% { box-shadow: 0 4px 15px rgba(229, 57, 53, 0.3); }
        50% { box-shadow: 0 4px 25px rgba(229, 57, 53, 0.6); }
    }
    
    .processing-btn {
        background: linear-gradient(135deg, var(--scheme-gold) 0%, #FF8F00 100%) !important;
        animation: processingRotate 2s linear infinite;
    }
    
    @keyframes processingRotate {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    
    /* Language selection */
    .language-selection {
        background: white;
        border-radius: 15px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        border: 2px solid var(--light-green);
    }
    
    /* Section headers */
    .section-header {
        background: linear-gradient(135deg, var(--secondary-green) 0%, var(--accent-green) 100%);
        color: white;
        padding: 1rem;
        border-radius: 15px;
        font-size: 1.3rem;
        font-weight: 600;
        text-align: center;
        margin: 1rem 0;
        box-shadow: 0 6px 20px rgba(76, 175, 80, 0.3);
    }
    
    /* Footer */
    .footer {
        background: linear-gradient(135deg, var(--primary-green) 0%, var(--government-blue) 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 15px;
        text-align: center;
        margin-top: 2rem;
        font-size: 0.9rem;
        opacity: 0.9;
    }
    
    /* Buttons */
    .stButton > button {
        width: 100%;
        background: linear-gradient(135deg, var(--secondary-green) 0%, var(--accent-green) 100%);
        color: white;
        border: none;
        border-radius: 15px;
        padding: 0.8rem;
        font-weight: 600;
        font-size: 1rem;
        transition: all 0.3s ease;
        font-family: 'Poppins', sans-serif;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(76, 175, 80, 0.4);
    }
    
    /* Hide Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Recording status */
    .recording-status {
        background: linear-gradient(135deg, #FFEBEE 0%, #FFCDD2 100%);
        color: #C62828;
        padding: 0.8rem;
        border-radius: 10px;
        text-align: center;
        margin: 0.5rem 0;
        border: 2px solid #E57373;
        animation: statusGlow 2s ease-in-out infinite;
    }
    
    @keyframes statusGlow {
        0%, 100% { box-shadow: 0 0 10px rgba(229, 57, 53, 0.2); }
        50% { box-shadow: 0 0 20px rgba(229, 57, 53, 0.4); }
    }
    </style>
""", unsafe_allow_html=True)

# Voice recorder with better error handling
def voice_recorder_component():
    return """
    <div id="voiceRecorder" style="display: flex; align-items: center; justify-content: center; height: 45px;">
        <button id="recordButton" onclick="toggleRecording()" 
                style="background: linear-gradient(135deg, #4CAF50 0%, #66BB6A 100%); 
                       color: white; border: none; border-radius: 50%; 
                       width: 45px; height: 45px; font-size: 1.2rem; 
                       cursor: pointer; box-shadow: 0 4px 15px rgba(76, 175, 80, 0.3);
                       transition: all 0.3s ease; display: flex; align-items: center; justify-content: center;">
            🎙️
        </button>
    </div>
    
    <script>
    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;
    let recordingTimer;
    let recordingSeconds = 0;
    
    function updateStatus(message, isRecording = false) {
        const button = document.getElementById('recordButton');
        
        if (isRecording) {
            button.style.background = 'linear-gradient(135deg, #E53935 0%, #C62828 100%)';
            button.style.animation = 'recordingPulse 1.5s ease-in-out infinite';
            button.textContent = '⏹️';
        } else {
            button.style.background = 'linear-gradient(135deg, #4CAF50 0%, #66BB6A 100%)';
            button.style.animation = 'none';
            button.textContent = '🎙️';
        }
    }
    
    // Add CSS animation
    if (!document.getElementById('recordingStyles')) {
        const style = document.createElement('style');
        style.id = 'recordingStyles';
        style.textContent = `
            @keyframes recordingPulse {
                0%, 100% { box-shadow: 0 4px 15px rgba(229, 57, 53, 0.3); }
                50% { box-shadow: 0 4px 25px rgba(229, 57, 53, 0.6); }
            }
        `;
        document.head.appendChild(style);
    }
    
    async function startRecording() {
        try {
            if (isRecording) return;
            
            const stream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    sampleRate: 16000
                } 
            });
            
            // Check for supported MIME types
            let mimeType = 'audio/webm;codecs=opus';
            if (!MediaRecorder.isTypeSupported(mimeType)) {
                mimeType = 'audio/webm';
                if (!MediaRecorder.isTypeSupported(mimeType)) {
                    mimeType = 'audio/mp4';
                    if (!MediaRecorder.isTypeSupported(mimeType)) {
                        mimeType = '';
                    }
                }
            }
            
            const options = mimeType ? { mimeType } : {};
            mediaRecorder = new MediaRecorder(stream, options);
            
            audioChunks = [];
            isRecording = true;
            recordingSeconds = 0;
            
            // Start timer
            recordingTimer = setInterval(() => {
                recordingSeconds++;
            }, 1000);
            
            updateStatus('', true);
            
            mediaRecorder.ondataavailable = event => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            };
            
            mediaRecorder.onstop = async () => {
                clearInterval(recordingTimer);
                
                const blob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
                const arrayBuffer = await blob.arrayBuffer();
                const base64 = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)));
                
                // Send to Streamlit using the component API
                Streamlit.setComponentValue({
                    audio_data: base64,
                    action: 'audio_recorded',
                    duration: recordingSeconds,
                    mimeType: mediaRecorder.mimeType
                });
                
                // Stop all tracks
                stream.getTracks().forEach(track => track.stop());
                isRecording = false;
                updateStatus('', false);
            };
            
            mediaRecorder.onerror = (event) => {
                console.error('MediaRecorder error:', event.error);
                updateStatus('❌ Recording error', false);
                stopRecording();
            };
            
            mediaRecorder.start();
            
            // Auto-stop after 60 seconds
            setTimeout(() => {
                if (mediaRecorder && mediaRecorder.state === 'recording') {
                    stopRecording();
                }
            }, 60000);
            
        } catch (error) {
            console.error('Recording error:', error);
            isRecording = false;
            updateStatus('', false);
        }
    }
    
    function stopRecording() {
        if (mediaRecorder && isRecording && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
        }
    }
    
    function toggleRecording() {
        if (isRecording) {
            stopRecording();
        } else {
            startRecording();
        }
    }
    
    // Expose to global scope for external access
    window.startRecording = startRecording;
    window.stopRecording = stopRecording;
    window.toggleRecording = toggleRecording;
    </script>
    """

# Get current language content
selected_lang_code = language_options[st.session_state.selected_language]
current_content = language_content.get(selected_lang_code, language_content["en"])

# Header
st.markdown(f"""
    <div class="header-container">
        <div class="header-title">{current_content["app_title"]}</div>
        <p class="header-subtitle">{current_content["app_subtitle"]}</p>
    </div>
""", unsafe_allow_html=True)

# Language Selection
with st.container():
    st.markdown('<div class="language-selection">', unsafe_allow_html=True)
    st.markdown(f'<div class="section-header">{current_content["language_header"]}</div>', unsafe_allow_html=True)
    
    language_label = st.selectbox(
        current_content["language_help"],
        list(language_options.keys()),
        index=list(language_options.keys()).index(st.session_state.selected_language),
        key="language_selector"
    )
    
    # Update selected language and reset chat if changed
    if language_label != st.session_state.selected_language:
        st.session_state.selected_language = language_label
        st.session_state.chat_history = []
        st.session_state.conversation_stage = "greeting"
        st.session_state.farmer_data = {}
        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

# Update current content after language change
selected_lang_code = language_options[st.session_state.selected_language]
current_content = language_content.get(selected_lang_code, language_content["en"])

# Initialize conversation with system greeting - always show in current language
if not st.session_state.chat_history:
    st.session_state.chat_history.append(("system", current_content["system_greeting"]))
elif st.session_state.chat_history and st.session_state.chat_history[0][0] == "system":
    # Update the first system message with current language
    st.session_state.chat_history[0] = ("system", current_content["system_greeting"])

# Chat Display
if st.session_state.chat_history:
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    st.markdown(f'<div class="section-header">{current_content["chat_header"]}</div>', unsafe_allow_html=True)
    
    for sender, message in st.session_state.chat_history:
        if sender == "user":
            st.markdown(f"""
                <div class="chat-message user-message">
                    <strong>{current_content["you_label"]}</strong> {message}
                </div>
            """, unsafe_allow_html=True)
        elif sender == "system":
            st.markdown(f"""
                <div class="chat-message system-message">
                    <strong>{current_content["bot_label"]}</strong> {message}
                </div>
            """, unsafe_allow_html=True)
        else:  # bot
            if message.startswith("AUDIO::"):
                parts = message.split("::")
                audio_path = parts[1] if len(parts) > 1 else ""
                response_text = parts[2] if len(parts) > 2 else "Audio response"
                
                st.markdown(f"""
                    <div class="chat-message bot-message">
                        <strong>{current_content["bot_label"]}</strong> {response_text}
                    </div>
                """, unsafe_allow_html=True)
                
                if audio_path:
                    audio_html = autoplay_audio(audio_path)
                    st.markdown(audio_html, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                    <div class="chat-message bot-message">
                        <strong>{current_content["bot_label"]}</strong> {message}
                    </div>
                """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# Input Area
st.markdown('<div class="input-container">', unsafe_allow_html=True)

# Create columns for input
col1, col2, col3 = st.columns([7, 1, 1])

with col1:
    user_input = st.text_input(
        "Input Message",
        placeholder=current_content["input_placeholder"],
        key="user_text_input",
        label_visibility="collapsed"
    )

with col2:
    # Combined voice recorder and button
    recorder_component = html(voice_recorder_component(), height=50)
    
    # Handle audio data from recorder component
    if recorder_component and isinstance(recorder_component, dict):
        if recorder_component.get("action") == "audio_recorded":
            audio_data = recorder_component.get("audio_data")
            if audio_data:
                try:
                    # Decode base64 audio data
                    audio_bytes = base64.b64decode(audio_data)
                    audio_io = io.BytesIO(audio_bytes)
                    
                    with st.spinner(current_content["processing"]):
                        # Convert to proper format
                        processed_audio = audio_to_bytesio(audio_io)
                        
                        if processed_audio:
                            # Transcribe audio
                            transcription_result = transcribe_audio(processed_audio)
                            
                            if transcription_result.get("status") == "COMPLETED":
                                transcribed_text = transcription_result.get("transcribed_text", "")
                                
                                # Add to chat history
                                st.session_state.chat_history.append(("user", f"🎵 {transcribed_text}"))
                                
                                # Process the transcribed message
                                response = process_user_message(transcribed_text, selected_lang_code)
                                
                                # Generate TTS response
                                tts_result = tts_response(response, selected_lang_code)
                                
                                if tts_result.get("status") == "COMPLETED":
                                    audio_filename = tts_result.get("audio_path", "")
                                    st.session_state.chat_history.append(("bot", f"AUDIO::{audio_filename}::{response}"))
                                else:
                                    st.session_state.chat_history.append(("bot", response))
                                
                                st.rerun()
                            else:
                                st.error("Failed to transcribe audio. Please try again.")
                        else:
                            st.error("Failed to process audio. Please try again.")
                            
                except Exception as e:
                    st.error(f"Error processing voice recording: {str(e)}")

with col3:
    # Combined Send and Clear buttons
    send_clicked = st.button("📤", key="send_btn", help=current_content["send_btn"])
    
    if st.button("🧹", key="clear_btn", help=current_content["clear_btn"]):
        st.session_state.chat_history = []
        st.session_state.conversation_stage = "greeting"
        st.session_state.farmer_data = {}
        st.session_state.chat_history.append(("system", current_content["system_greeting"]))
        st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# Conversation flow logic
def process_user_message(message, language_code):
    """Process user message and generate appropriate response based on conversation stage"""
    
    # Simple keyword-based processing for demonstration
    # In production, this would integrate with your backend API
    
    stage = st.session_state.conversation_stage
    farmer_data = st.session_state.farmer_data
    
    if stage == "greeting" or "name" not in farmer_data:
        # Extract name
        if any(word in message.lower() for word in ["my name is", "i am", "naam", "मेरा नाम", "મારું નામ"]):
            # Extract name (simplified)
            name = message.split()[-1] if message.split() else "Farmer"
            farmer_data["name"] = name
            st.session_state.conversation_stage = "location"
            
            if language_code == "hi":
                return f"धन्यवाद {name} जी! अब कृपया मुझे अपना राज्य और जिला बताएं। उदाहरण: मैं गुजरात के अहमदाबाद जिले से हूं।"
            elif language_code == "gu":
                return f"આભાર {name} જી! હવે કૃપા કરીને મને તમારું રાજ્ય અને જિલ્લો કહો। ઉદાહરણ: હું ગુજરાતના અમદાવાદ જિલ્લાથી છું।"
            else:
                return f"Thank you {name}! Now please tell me your state and district. For example: I am from Ahmedabad district in Gujarat."
        else:
            if language_code == "hi":
                return "कृपया अपना नाम बताएं। उदाहरण: मेरा नाम राम है।"
            elif language_code == "gu":
                return "કૃપા કરીને તમારું નામ કહો. ઉદાહરણ: મારું નામ રામ છે."
            else:
                return "Please tell me your name. For example: My name is Ram."
    
    elif stage == "location":
        # Extract location
        farmer_data["location"] = message
        st.session_state.conversation_stage = "farming_details"
        
        if language_code == "hi":
            return f"बहुत अच्छा! अब कृपया अपनी खेती के बारे में बताएं:\n• आपके पास कितनी जमीन है?\n• आप कौन सी फसलें उगाते हैं?\n• क्या आप किसान हैं या खेतिहर मजदूर?"
        elif language_code == "gu":
            return f"ખૂબ સરસ! હવે કૃપા કરીને તમારી ખેતી વિશે કહો:\n• તમારી પાસે કેટલી જમીન છે?\n• તમે કયા પાકો ઉગાડો છો?\n• શું તમે ખેડૂત છો કે ખેતી મજૂર?"
        else:
            return f"Great! Now please tell me about your farming:\n• How much land do you own?\n• What crops do you grow?\n• Are you a farmer or agricultural laborer?"
    
    elif stage == "farming_details":
        # Extract farming details
        farmer_data["farming_details"] = message
        st.session_state.conversation_stage = "eligibility_check"
        
        # Generate scheme eligibility based on collected data
        eligible_schemes = []
        
        # Simple eligibility logic (in production, this would be more sophisticated)
        if "land" in message.lower() or "acre" in message.lower() or "hectare" in message.lower():
            eligible_schemes.extend(["PM-KISAN", "Soil Health Card"])
        
        if "crop" in message.lower() or "farming" in message.lower():
            eligible_schemes.extend(["Pradhan Mantri Fasal Bima Yojana", "Kisan Credit Card"])
        
        if not eligible_schemes:
            eligible_schemes = ["PM-KISAN", "Soil Health Card"]  # Default schemes
        
        farmer_data["eligible_schemes"] = eligible_schemes
        
        if language_code == "hi":
            schemes_text = ", ".join(eligible_schemes)
            return f"आपकी जानकारी के आधार पर, आप निम्नलिखित योजनाओं के लिए पात्र हो सकते हैं:\n\n🌾 {schemes_text}\n\nक्या आप किसी विशेष योजना के बारे में और जानना चाहते हैं?"
        elif language_code == "gu":
            schemes_text = ", ".join(eligible_schemes)
            return f"તમારી માહિતીના આધારે, તમે નીચેની યોજનાઓ માટે પાત્ર હોઈ શકો છો:\n\n🌾 {schemes_text}\n\nશું તમે કોઈ ખાસ યોજના વિશે વધુ જાણવા માંગો છો?"
        else:
            schemes_text = ", ".join(eligible_schemes)
            return f"Based on your information, you may be eligible for the following schemes:\n\n🌾 {schemes_text}\n\nWould you like to know more about any specific scheme?"
    
    else:
        # General conversation
        if language_code == "hi":
            return "मैं आपकी मदद करने के लिए यहाँ हूँ। क्या आप किसी विशेष योजना के बारे में जानना चाहते हैं या नई जानकारी देना चाहते हैं?"
        elif language_code == "gu":
            return "હું તમારી મદદ કરવા માટે અહીં છું. શું તમે કોઈ ખાસ યોજના વિશે જાણવા માંગો છો કે નવી માહિતી આપવા માંગો છો?"
        else:
            return "I'm here to help you. Would you like to know about any specific scheme or provide new information?"

# Handle text input
if send_clicked and user_input.strip():
    # Add user message to chat
    st.session_state.chat_history.append(("user", user_input))
    
    # Process the message with conversation flow
    response = process_user_message(user_input, selected_lang_code)
    
    # Generate TTS response if backend is available
    tts_result = tts_response(response, selected_lang_code)
    
    if tts_result.get("status") == "COMPLETED":
        audio_filename = tts_result.get("audio_path", "")
        st.session_state.chat_history.append(("bot", f"AUDIO::{audio_filename}::{response}"))
    else:
        st.session_state.chat_history.append(("bot", response))
    
    # Clear input and rerun
    st.rerun()

# Handle audio recording (this would be triggered by the JavaScript component)
# The component will send audio data that can be processed here

# Process uploaded audio files
uploaded_audio = st.file_uploader(
    "Or upload an audio file:",
    type=['wav', 'mp3', 'm4a', 'webm'],
    key="audio_uploader",
    help="Upload an audio file instead of recording"
)

if uploaded_audio:
    with st.spinner(current_content["processing"]):
        # Convert audio to BytesIO
        audio_data = audio_to_bytesio(uploaded_audio)
        
        if audio_data:
            # Transcribe audio
            transcription_result = transcribe_audio(audio_data)
            
            if transcription_result.get("status") == "COMPLETED":
                transcribed_text = transcription_result.get("transcribed_text", "")
                
                # Add to chat history
                st.session_state.chat_history.append(("user", f"🎵 Audio: {transcribed_text}"))
                
                # Generate response (this would be your scheme checking logic)
                response = f"I heard: '{transcribed_text}'. Processing for scheme eligibility..."
                
                # Generate TTS response
                tts_result = tts_response(response, selected_lang_code)
                
                if tts_result.get("status") == "COMPLETED":
                    audio_filename = tts_result.get("audio_path", "")
                    st.session_state.chat_history.append(("bot", f"AUDIO::{audio_filename}::{response}"))
                else:
                    st.session_state.chat_history.append(("bot", response))
                
                st.rerun()
            else:
                st.error("Failed to transcribe audio. Please try again.")

# Footer with comprehensive information
footer_content = {
    "en": {
        "title": "🏛️ Sanchalak - Government Scheme Eligibility Checker",
        "description": "Empowering farmers with easy access to agricultural government schemes",
        "schemes": "Supported Schemes: PM-KISAN, Soil Health Card, Pradhan Mantri Fasal Bima Yojana, Kisan Credit Card",
        "languages": "Supported Languages: English, Hindi, Gujarati, Punjabi, Bengali, Telugu, Tamil, Malayalam, Kannada, Odia",
        "disclaimer": "This is a demo application. For official scheme applications, please visit your nearest agricultural office or official government websites.",
        "privacy": "Your conversations are not stored permanently. Voice data is processed securely."
    },
    "hi": {
        "title": "🏛️ संचालक - सरकारी योजना पात्रता जांचकर्ता",
        "description": "किसानों को कृषि सरकारी योजनाओं तक आसान पहुंच प्रदान करना",
        "schemes": "समर्थित योजनाएं: पीएम-किसान, मृदा स्वास्थ्य कार्ड, प्रधानमंत्री फसल बीमा योजना, किसान क्रेडिट कार्ड",
        "languages": "समर्थित भाषाएं: अंग्रेजी, हिंदी, गुजराती, पंजाबी, बंगाली, तेलुगु, तमिल, मलयालम, कन्नड़, उड़िया",
        "disclaimer": "यह एक डेमो एप्लिकेशन है। आधिकारिक योजना आवेदन के लिए, कृपया अपने निकटतम कृषि कार्यालय या आधिकारिक सरकारी वेबसाइटों पर जाएं।",
        "privacy": "आपकी बातचीत स्थायी रूप से संग्रहीत नहीं होती। वॉयस डेटा सुरक्षित रूप से संसाधित होता है।"
    },
    "gu": {
        "title": "🏛️ સંચાલક - સરકારી યોજના પાત્રતા તપાસકર્તા",
        "description": "ખેડૂતોને કૃષિ સરકારી યોજનાઓની સરળ પહોંચ પ્રદાન કરવી",
        "schemes": "સપોર્ટેડ યોજનાઓ: PM-KISAN, માટી આરોગ્ય કાર્ડ, પ્રધાનમંત્રી ફસલ વીમા યોજના, કિસાન ક્રેડિટ કાર્ડ",
        "languages": "સપોર્ટેડ ભાષાઓ: અંગ્રેજી, હિન્દી, ગુજરાતી, પંજાબી, બંગાળી, તેલુગુ, તમિલ, મલયાલમ, કન્નડ, ઓડિયા",
        "disclaimer": "આ એક ડેમો એપ્લિકેશન છે. સત્તાવાર યોજના અરજી માટે, કૃપા કરીને તમારી નજીકની કૃષિ ઓફિસ અથવા સત્તાવાર સરકારી વેબસાઇટ્સની મુલાકાત લો।",
        "privacy": "તમારી વાતચીતો કાયમી રૂપે સંગ્રહિત થતી નથી. વૉઇસ ડેટા સુરક્ષિત રીતે પ્રક્રિયા કરવામાં આવે છે।"
    }
}

current_footer = footer_content.get(selected_lang_code, footer_content["en"])

st.markdown(f"""
    <div class="footer">
        <h4 style="margin-bottom: 1rem; color: white;">{current_footer["title"]}</h4>
        <p style="margin-bottom: 0.8rem; font-size: 1rem;">{current_footer["description"]}</p>
        <p style="margin-bottom: 0.8rem; font-size: 0.9rem;"><strong>{current_footer["schemes"]}</strong></p>
        <p style="margin-bottom: 0.8rem; font-size: 0.9rem;">{current_footer["languages"]}</p>
        <hr style="margin: 1rem 0; border: 1px solid rgba(255,255,255,0.3);">
        <p style="margin-bottom: 0.5rem; font-size: 0.8rem; font-style: italic;">{current_footer["disclaimer"]}</p>
        <p style="margin-bottom: 0; font-size: 0.8rem; font-style: italic;">{current_footer["privacy"]}</p>
    </div>
""", unsafe_allow_html=True)