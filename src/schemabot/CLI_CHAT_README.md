# 🚀 Sanchalak CLI Chat Interface

A command-line interface for testing the EFR-integrated government scheme eligibility assistant powered by LM Studio.

## 🎯 Features

- **EFR Integration**: Uses enhanced canonical YAML from EFR database as source of truth
- **LM Studio Backend**: Leverages LM Studio for high-quality LLM responses
- **Real-time Chat**: Interactive conversation with context management
- **Scheme Support**: Currently supports PM-KISAN with extensible architecture
- **Session Management**: Track conversation progress and statistics
- **Enhanced Prompts**: Uses scheme-specific prompts and data models

## 📋 Prerequisites

### 1. **LM Studio**
- Download and install [LM Studio](https://lmstudio.ai/)
- Load a compatible model (recommended: Gemma-2, Llama-3, or similar)
- Start the local server on port 1234
- Verify: http://localhost:1234/v1/models

### 2. **EFR Database**
- Ensure EFR database is running on port 8001
- Start with: `cd src/efr_database && python -m uvicorn main:app --port 8001`
- Verify: http://localhost:8001/health

### 3. **Python Dependencies**
```bash
pip install requests aiohttp pydantic fastapi
```

## 🚀 Quick Start

### Option 1: Using the Launcher (Recommended)
```bash
cd src/schemabot
python run_chat.py
```

The launcher will:
- Check all prerequisites
- Verify service availability
- Launch the chat interface

### Option 2: Direct Launch
```bash
cd src/schemabot
python cli_chat.py
```

## 💬 Usage

### Starting a Conversation
```
/start pm-kisan
```

### Available Commands
- `/start <scheme>` - Start a new conversation for a scheme
- `/stats` - Show session statistics
- `/schemes` - List available schemes
- `/clear` - Clear the screen
- `/help` - Show help information
- `/quit` or `/exit` - Exit the application

### Example Session
```
🚀 Sanchalak CLI Chat Interface
   Government Scheme Eligibility Assistant
   Powered by EFR Database + LM Studio
================================================================================

You: /start pm-kisan

🔗 Initializing chat session for scheme: pm-kisan
✅ LM Studio connected. Available models: ['gemma-2-9b-it']
✅ EFR Database connected: EFR database is reachable
✅ Chat session initialized successfully

🎯 Ready to chat about pm-kisan!
==================================================
🤖 Assistant: नमस्ते! मैं PM-KISAN योजना के लिए आपकी सहायता करने वाला सहायक हूं।

PM-KISAN is a Central Sector Scheme providing income support to all landholding farmers' families...

[pm-kisan] You: मेरा नाम राज कुमार है और मैं बिहार से हूं

⏱️  Response time: 1.23s
🤖 Assistant: धन्यवाद राज कुमार जी! खुशी है कि आप बिहार से हैं। PM-KISAN योजना के लिए मुझे आपकी कुछ जानकारी चाहिए...
```

## 🏗️ Architecture

### Components
1. **LMStudioClient**: Handles communication with LM Studio API
2. **ChatSession**: Manages conversation context and state
3. **EnhancedPromptEngine**: Uses EFR database for scheme-specific prompts
4. **EFRSchemeClient**: Connects to EFR database for canonical data
5. **ChatCLI**: Main CLI interface and command handling

### Integration Flow
```
User Input → CLI → ChatSession → EnhancedPromptEngine → EFR Database
                                      ↓
                   LM Studio ← ChatSession ← Contextual Prompt
```

## 🔧 Configuration

### LM Studio Settings
- **URL**: http://localhost:1234/v1
- **Temperature**: 0.7 (configurable)
- **Max Tokens**: 512 (configurable)
- **Timeout**: 30 seconds

### EFR Database Settings
- **URL**: http://localhost:8001
- **Health Check**: /health endpoint
- **Schemes**: /api/schemes/{scheme_code}

## 📊 Session Statistics

The CLI tracks:
- Session duration
- Message count
- Token usage (estimated)
- Conversation stage
- Collected data fields
- Required fields progress

View with `/stats` command.

## 🐛 Troubleshooting

### LM Studio Issues
```bash
❌ Cannot connect to LM Studio
```
**Solution**: 
1. Ensure LM Studio is running
2. Check if a model is loaded
3. Verify server is on port 1234

### EFR Database Issues
```bash
❌ EFR Database not accessible
```
**Solution**:
1. Start EFR database: `cd src/efr_database && python -m uvicorn main:app --port 8001`
2. Check MongoDB is running
3. Verify health endpoint: http://localhost:8001/health

### Import Errors
```bash
❌ Missing required module
```
**Solution**:
```bash
pip install requests aiohttp pydantic fastapi
```

## 🎛️ Advanced Usage

### Custom EFR URL
```python
# In cli_chat.py, modify:
ChatSession(scheme_code, efr_api_url="http://custom-efr:8001")
```

### Custom LM Studio URL
```python
# In cli_chat.py, modify:
LMStudioClient(base_url="http://custom-lmstudio:1234/v1")
```

### Adding New Schemes
1. Add scheme to EFR database
2. Update `available_schemes` in `ChatCLI` class
3. Test with `/start <new-scheme>`

## 📈 Performance Tips

1. **Use GPU acceleration** in LM Studio for faster responses
2. **Keep EFR database warm** by making occasional requests
3. **Use smaller models** for faster iteration during development
4. **Monitor token usage** with `/stats` to optimize prompts

## 🔮 Future Enhancements

- [ ] Multi-language support
- [ ] Voice input/output
- [ ] Conversation export
- [ ] Custom prompt templates
- [ ] Batch conversation testing
- [ ] Integration with other LLM providers

## 🤝 Contributing

To add new features:
1. Fork the repository
2. Create a feature branch
3. Test with existing schemes
4. Submit a pull request

---

Happy chatting! 🎉 