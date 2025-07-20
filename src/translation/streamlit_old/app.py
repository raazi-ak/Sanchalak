#trans\streamlit_app\app.py

import streamlit as st
import io
import base64
from streamlit.components.v1 import html
from utils import transcribe_audio, tts_response, audio_to_bytesio, autoplay_audio
from streamlit_webrtc import webrtc_streamer, AudioProcessorBase, WebRtcMode
import av
import requests
import tempfile
import os


SANCHALAK_API_BASE_URL=http://localhost:8000


# Initialize session state variables if not already present
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

if "selected_scheme_code" not in st.session_state:
    st.session_state.selected_scheme_code = "PMKISAN"  # Default scheme (or update later via dropdown)


# Page Configuration
st.set_page_config(
    page_title="Sanchalak - कृषि संवाद",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Web Audio Recorder HTML+JS
def voice_recorder_html():
    return """
    <script>
    let mediaRecorder;
    let audioChunks = [];

    async function startRecording() {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = event => {
            if (event.data.size > 0) audioChunks.push(event.data);
        };

        mediaRecorder.onstop = async () => {
            const blob = new Blob(audioChunks, { type: 'audio/webm' });
            const arrayBuffer = await blob.arrayBuffer();
            const base64 = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)));
            window.parent.postMessage({ isStreamlitMessage: true, type: 'streamlit:setComponentValue', value: base64 }, '*');
        };

        mediaRecorder.start();
        document.getElementById("recordingStatus").innerText = "🎙️ Recording...";
    }

    function stopRecording() {
        if (mediaRecorder) {
            mediaRecorder.stop();
            document.getElementById("recordingStatus").innerText = "⏹️ Stopped. Processing...";
        }
    }
    </script>
    <div style="text-align:center;">
        <button onclick="startRecording()" style="padding:10px 20px; background:#E53935; color:white; border:none; border-radius:8px;">🔴 Start</button>
        <button onclick="stopRecording()" style="padding:10px 20px; background:#43A047; color:white; border:none; border-radius:8px; margin-left:10px;">⏹️ Stop</button>
        <p id="recordingStatus" style="margin-top:1rem;"></p>
    </div>
    """


# Enhanced CSS with agriculture theme
st.markdown("""
    <style>
    .main {
        padding: 1rem;
        background: linear-gradient(135deg, #E8F5E8 0%, #F1F8E9 100%);
    }
    
    .stApp {
        background: linear-gradient(135deg, #E8F5E8 0%, #F1F8E9 100%);
    }
    
    .header-container {
        background: linear-gradient(135deg, #2E7D32 0%, #4CAF50 100%);
        color: white;
        padding: 2rem;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 8px 25px rgba(46, 125, 50, 0.3);
    }
    
    .header-title {
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    
    .header-subtitle {
        font-size: 1.2rem;
        opacity: 0.9;
        margin-bottom: 0;
    }
    
    .section-header {
        background: linear-gradient(135deg, #4CAF50 0%, #66BB6A 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        font-size: 1.3rem;
        font-weight: bold;
        margin: 1.5rem 0 1rem 0;
        text-align: center;
        box-shadow: 0 4px 15px rgba(76, 175, 80, 0.3);
    }
    
    .chat-container {
        background: white;
        border-radius: 15px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        border: 2px solid #C8E6C9;
    }
    
    .chat-message {
        margin: 1rem 0;
        padding: 1rem;
        border-radius: 10px;
        position: relative;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    
    .user-message {
        background: linear-gradient(135deg, #E3F2FD 0%, #BBDEFB 100%);
        border-left: 4px solid #2196F3;
        margin-left: 2rem;
    }
    
    .bot-message {
        background: linear-gradient(135deg, #F1F8E9 0%, #DCEDC8 100%);
        border-left: 4px solid #4CAF50;
        margin-right: 2rem;
    }
    
    .message-icon {
        font-size: 1.2rem;
        margin-right: 0.5rem;
    }
    
    .audio-column {
        background: white;
        border-radius: 15px;
        padding: 1.5rem;
        margin: 0.5rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        border: 2px solid #C8E6C9;
        height: 250px;
    }
    
    .stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #FF5722 0%, #D84315 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.75rem;
        font-weight: bold;
        font-size: 1rem;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #E64A19 0%, #BF360C 100%);
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.3);
    }
    </style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
    <div class="header-container">
        <div class="header-title">🌾 Sanchalak - कृषि संवाद</div>
        <p class="header-subtitle">Your Digital Agricultural Assistant | आपका डिजिटल कृषि सहायक</p>
    </div>
""", unsafe_allow_html=True)

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

# Multilingual content
language_content = {
    "en": {
        "greeting": "🙏 Hello! I am Sanchalak, your digital agricultural assistant. Please record your audio message below to share your name, district, and farming information.",
        "language_header": "🌐 Select Your Language",
        "language_help": "Choose your preferred language:",
        "audio_header": "🎙️ Record Your Voice Message",
        "upload_text": "**Alternative:** Upload an audio file if recording doesn't work",
        "upload_help": "Supported formats: WAV, MP3, M4A, WebM",
        "choose_file": "📁 Choose an audio file",
        "conversation_header": "💬 Conversation",
        "you_label": "🧑‍🌾 You:",
        "bot_label": "🤖 Sanchalak:",
        "bot_replied": "🤖 Sanchalak replied:",
        "processing": "🧠 Processing your voice message...",
        "upload_processing": "🧠 Processing uploaded audio...",
        "record_voice": "🎙️ Voice Recording",
        "upload_audio": "📁 Upload Audio File"
    },
    "hi": {
        "greeting": "🙏 नमस्ते! मैं संचालक हूँ, आपका डिजिटल कृषि सहायक। कृपया अपना नाम, जिला और खेती की जानकारी देने के लिए नीचे दिए गए बटन से ऑडियो रिकॉर्ड करें।",
        "language_header": "🌐 अपनी भाषा चुनें",
        "language_help": "अपनी पसंदीदा भाषा चुनें:",
        "audio_header": "🎙️ अपना आवाज़ संदेश रिकॉर्ड करें",
        "upload_text": "**वैकल्पिक:** यदि रिकॉर्डिंग काम नहीं कर रही है तो ऑडियो फ़ाइल अपलोड करें",
        "upload_help": "समर्थित प्रारूप: WAV, MP3, M4A, WebM",
        "choose_file": "📁 ऑडियो फ़ाइल चुनें",
        "conversation_header": "💬 बातचीत",
        "you_label": "🧑‍🌾 आप:",
        "bot_label": "🤖 संचालक:",
        "bot_replied": "🤖 संचालक ने जवाब दिया:",
        "processing": "🧠 आपके आवाज़ संदेश को प्रोसेस कर रहे हैं...",
        "upload_processing": "🧠 अपलोड की गई ऑडियो को प्रोसेस कर रहे हैं...",
        "record_voice": "🎙️ आवाज़ रिकॉर्डिंग",
        "upload_audio": "📁 ऑडियो फ़ाइल अपलोड करें"
    }
}

# Initialize session state for language
if "selected_language" not in st.session_state:
    st.session_state.selected_language = "English"

selected_lang_code = language_options[st.session_state.selected_language]
current_content = language_content.get(selected_lang_code, language_content["en"])

# Language Selection
st.markdown('<div class="language-selection">', unsafe_allow_html=True)
st.markdown(f'<div class="section-header">{current_content["language_header"]}</div>', unsafe_allow_html=True)

language_label = st.selectbox(
    current_content["language_help"],
    list(language_options.keys()),
    index=list(language_options.keys()).index(st.session_state.selected_language),
    key="language_selector"
)

# Update selected language in session state
if language_label != st.session_state.selected_language:
    st.session_state.selected_language = language_label
    # Reset chat history when language changes
    if "chat_history" in st.session_state:
        st.session_state.chat_history = []
    st.rerun()

selected_lang_code = language_options[language_label]
current_content = language_content.get(selected_lang_code, language_content["en"])
st.markdown('</div>', unsafe_allow_html=True)

# Initialize chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Chat History Display (moved up)
if st.session_state.chat_history:
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    st.markdown(f'<div class="section-header">{current_content["conversation_header"]}</div>', unsafe_allow_html=True)
    
    for sender, message in st.session_state.chat_history:
        if sender == "user":
            st.markdown(f"""
                <div class="chat-message user-message">
                    <span class="message-icon">🧑‍🌾</span>
                    <strong>{current_content["you_label"]}</strong> {message}
                </div>
            """, unsafe_allow_html=True)
        else:
            if message.startswith("AUDIO::"):
                parts = message.split("::")
                audio_path = parts[1] if len(parts) > 1 else ""
                response_text = parts[2] if len(parts) > 2 else "Audio response"
                
                st.markdown(f"""
                    <div class="chat-message bot-message">
                        <span class="message-icon">🤖</span>
                        <strong>{current_content["bot_replied"]}</strong>
                    </div>
                """, unsafe_allow_html=True)
                
                if audio_path:
                    audio_html = autoplay_audio(audio_path)
                    st.markdown(audio_html, unsafe_allow_html=True)
                
                if response_text != "Audio response":
                    st.markdown(f"""
                        <div class="chat-message bot-message" style="margin-top: 0.5rem; font-style: italic;">
                            📝 {response_text}
                        </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                    <div class="chat-message bot-message">
                        <span class="message-icon">🤖</span>
                        <strong>{current_content["bot_label"]}</strong> {message}
                    </div>
                """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Clear chat button
    if st.button("🗑️ Clear Conversation", help="Clear all conversation history"):
        st.session_state.chat_history = []
        st.rerun()

# Show greeting when no chat history
else:
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    st.markdown(f'<div class="section-header">{current_content["conversation_header"]}</div>', unsafe_allow_html=True)
    st.markdown(f"""
        <div class="chat-message bot-message">
            <span class="message-icon">🤖</span>
            <strong>{current_content["bot_label"]}</strong> {current_content["greeting"]}
        </div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# Audio Input Section (side by side layout)
st.markdown(f'<div class="section-header">{current_content["audio_header"]}</div>', unsafe_allow_html=True)

# Create two columns for proper side-by-side layout
col1, col2 = st.columns(2, gap="medium")

# Column 1: Voice Recording
with col1:
    st.markdown(f"**{current_content['record_voice']}**")
    st.info("🎤 Click below and speak your message")

    class AudioProcessor(AudioProcessorBase):
        def __init__(self) -> None:
            self.frames = []

        def recv_queued(self, frames):
            self.frames.extend(frames)
            return frames[-1]

        def get_wav_bytes(self):
            if not self.frames:
                return None
            pcm = b""
            for f in self.frames:
                pcm += f.to_ndarray().tobytes()


            temp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            temp_wav.write(pcm)
            temp_wav.close()
            return temp_wav.name

    ctx = webrtc_streamer(
        key="audio-recorder",
        mode=WebRtcMode.SENDRECV,
        audio_receiver_size=4096,
        media_stream_constraints={"video": False, "audio": True},
        async_processing=True,
        audio_processor_factory=AudioProcessor
    )
    st.write("🎤 Audio Processor:", bool(ctx.audio_processor))
    st.write("🎯 WebRTC Status:", ctx.state)
    if ctx.audio_processor:
        st.write("📦 Audio frames:", len(ctx.audio_processor.frames))
    else:
        st.write("⚠️ No audio processor initialized")


    if st.button("🛑 Stop and Transcribe"):
        if ctx and ctx.audio_processor:
            wav_path = ctx.audio_processor.get_wav_bytes()
            if wav_path:
                st.success("✅ Audio captured! Transcribing...")

                with open(wav_path, "rb") as f:
                    files = {"file": f}
                    try:
                        response = requests.post("http://127.0.0.1:8000/transcribe/", files=files, timeout=60)
                        if response.status_code == 200:
                            data = response.json()
                            user_text = data.get("transcribed_text")
                            st.session_state.chat_history.append(("user", user_text))

                            # 🔄 Sanchalak backend integration
                            # Step 1: Start conversation if first time
                            if "conversation_id" not in st.session_state:
                                scheme_code = "PMKISAN"  # You can make this dynamic via dropdown
                                start_resp = requests.post("http://127.0.0.1:8000/conversations/", json={
                                    "scheme_code": scheme_code,
                                    "language": selected_lang_code
                                })
                                if start_resp.status_code == 200:
                                    st.session_state.conversation_id = start_resp.json().get("conversation_id")
                                else:
                                    st.session_state.chat_history.append(("bot", "⚠️ Failed to start conversation"))
                                    st.rerun()

                            # Step 2: Send message to Sanchalak backend
                            msg_resp = requests.post(
                                f"http://127.0.0.1:8000/conversations/{st.session_state.conversation_id}/messages",
                                json={"role": "user", "content": user_text}
                            )

                            if msg_resp.status_code == 200:
                                bot_text = msg_resp.json().get("content", "👋")
                            else:
                                bot_text = "⚠️ Could not reach backend."

                            # Step 3: Send backend reply to TTS
                            tts_result = tts_response(bot_text, selected_lang_code)
                            if tts_result and tts_result.get("status") == "COMPLETED":
                                audio_path = tts_result["audio_path"]
                                st.session_state.chat_history.append(("bot", f"AUDIO::{audio_path}::{bot_text}"))
                            else:
                                st.session_state.chat_history.append(("bot", "⚠️ Sorry, I couldn't generate a response."))
                            st.rerun()
                        else:
                            st.error(f"Backend error: {response.status_code}")
                    except Exception as e:
                        st.error(f"Failed to connect to backend: {e}")
                os.remove(wav_path)
            else:
                st.warning("⚠️ No audio captured yet.")


# Column 2: File Upload
with col2:
    st.markdown('<div class="audio-column">', unsafe_allow_html=True)
    st.markdown(f"**{current_content['upload_audio']}**")
    st.markdown(current_content["upload_text"])
    
    uploaded_file = st.file_uploader(
        current_content["choose_file"], 
        type=["wav", "mp3", "m4a", "webm"],
        help=current_content["upload_help"],
        key="audio_uploader"
    )
    
    if uploaded_file is not None:
        with st.spinner(current_content["upload_processing"]):
            try:
                audio_io = audio_to_bytesio(uploaded_file)
                if not audio_io:
                    st.session_state.chat_history.append(("bot", "🚫 Failed to process audio file. Please upload a valid MP3/WAV file under 10MB."))
                    st.rerun()
                if audio_io:
                    transcription_result = transcribe_audio(audio_io)
                    st.write("🔍 Transcription Result:", transcription_result)

                    
                    if not transcription_result:
                        st.session_state.chat_history.append(("bot", "🚫 No response from backend."))
                    elif transcription_result.get("status") == "COMPLETED":
                        user_text = transcription_result["transcribed_text"]
                        st.session_state.chat_history.append(("user", user_text))
                        
                        # Generate TTS response
                        tts_result = tts_response(user_text, selected_lang_code)
                        
                        if tts_result and tts_result.get("status") == "COMPLETED":
                            audio_path = tts_result["audio_path"]
                            bot_response = tts_result.get("response_text", "Audio response generated")
                            st.session_state.chat_history.append(("bot", f"AUDIO::{audio_path}::{bot_response}"))
                        else:
                            st.session_state.chat_history.append(("bot", "⚠️ Sorry, I couldn't generate a response. Please try again."))
                    else:
                        error = transcription_result.get("error", "Unknown error")
                        st.session_state.chat_history.append(("bot", f"⚠️ Couldn't transcribe your audio. Error: {error}"))
                    
                    st.rerun()
                    
            except Exception as e:
                st.session_state.chat_history.append(("bot", f"🚫 Error processing uploaded file: {str(e)}"))
                st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown("""
    <div style="text-align: center; padding: 2rem; color: #666; background: #F5F5F5; border-radius: 10px; margin-top: 2rem;">
        <p><strong>🌾 Sanchalak - Your Digital Agricultural Assistant</strong></p>
        <p>Empowering farmers with technology | प्रौद्योगिकी के साथ किसानों को सशक्त बनाना</p>
        <p style="font-size: 0.9rem; margin-top: 1rem;">
            Supported Languages: English, Hindi, Gujarati, Punjabi, Bengali, Telugu, Tamil, Malayalam, Kannada, Odia
        </p>
    </div>
""", unsafe_allow_html=True)