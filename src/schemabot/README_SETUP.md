# Sanchalak Setup Guide

## Overview
Sanchalak is a Government Scheme Eligibility Bot with enhanced canonical model integration. It now uses LM Studio with Gemma3 for improved performance and accuracy.

## Prerequisites

1. **Python 3.8+**
2. **LM Studio** (for LLM inference)
3. **Redis** (for caching)
4. **Gemma3 model** loaded in LM Studio

## Quick Start

### 1. Install Dependencies
```bash
cd src/schemabot
pip install -r requirements.txt
```

### 2. Start LM Studio
1. Download and install LM Studio from https://lmstudio.ai/
2. Load the Gemma3 model (google/gemma-3-4b)
3. Start the local server on port 1234
4. Verify it's running: http://localhost:1234/v1/models

### 3. Start Redis (if not running)
```bash
# macOS
brew services start redis

# Ubuntu/Debian
sudo systemctl start redis

# Or using Docker
docker run -d -p 6379:6379 redis:alpine
```

### 4. Launch Sanchalak
```bash
cd src/schemabot
python run_server.py
```

## Configuration

The application uses environment variables for configuration. Create a `.env` file in the `src/schemabot` directory:

```env
# LLM Configuration
SANCHALAK_LLM__USE_LM_STUDIO=true
SANCHALAK_LLM__LM_STUDIO_URL=http://localhost:1234
SANCHALAK_LLM__MODEL_NAME=google/gemma-3-4b

# Redis Configuration
SANCHALAK_REDIS__URL=redis://localhost:6379/0

# Application Settings
SANCHALAK_ENVIRONMENT=development
SANCHALAK_DEBUG=true
```

## Enhanced Features

### Canonical Model Integration
- **Rich Data Model**: Comprehensive field definitions with validation
- **Special Region Support**: Handles Manipur, Nagaland, Jharkhand, and North East states
- **Conditional Fields**: Dynamic field requirements based on user responses
- **LLM Extraction Prompts**: Optimized prompts for data extraction

### PM-KISAN Scheme
The enhanced PM-KISAN scheme includes:
- **18 Essential Fields**: All required for eligibility
- **Special Provisions**: Region-specific certificate handling
- **Validation Rules**: Comprehensive data validation
- **Extraction Prompts**: Bilingual (Hindi/English) prompts

## API Endpoints

- **Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health
- **Schemes**: http://localhost:8000/api/schemes
- **Conversations**: http://localhost:8000/api/conversations
- **Eligibility**: http://localhost:8000/api/eligibility
- **Metrics**: http://localhost:8000/metrics

## Testing the Enhanced Model

### 1. Check Health
```bash
curl http://localhost:8000/api/health
```

### 2. List Schemes
```bash
curl http://localhost:8000/api/schemes
```

### 3. Test PM-KISAN Eligibility
```bash
curl -X POST http://localhost:8000/api/eligibility/check \
  -H "Content-Type: application/json" \
  -d '{
    "scheme_code": "PMKISAN",
    "farmer_data": {
      "name": "Ram Singh",
      "age": 45,
      "state": "Manipur",
      "land_size_acres": 3.5,
      "land_ownership": "owned"
    }
  }'
```

## Troubleshooting

### LM Studio Connection Issues
- Ensure LM Studio is running on port 1234
- Check if the model is loaded: http://localhost:1234/v1/models
- Verify the model name matches your loaded model

### Redis Connection Issues
- Ensure Redis is running on port 6379
- Test connection: `redis-cli ping`

### Scheme Loading Issues
- Verify `schemas/schemes_registry.yaml` exists
- Check that `schemas/pm_kisan_enhanced.yaml` is present
- Review logs for parsing errors

## Development

### Running Tests
```bash
cd src/schemabot
python -m pytest tests/
```

### Adding New Schemes
1. Create scheme YAML file in `schemas/`
2. Add entry to `schemas/schemes_registry.yaml`
3. Test with the API

### Modifying Prompts
Edit `core/prompts/templates.py` for conversation flow changes.

## Architecture

```
schemabot/
├── app/                    # FastAPI application
├── api/                    # API routes
├── core/                   # Core functionality
│   ├── llm/               # LLM clients (LM Studio, Gemma)
│   ├── prompts/           # Prompt templates
│   └── scheme/            # Scheme parsing and validation
├── schemas/               # Scheme definitions
│   ├── schemes_registry.yaml
│   └── pm_kisan_enhanced.yaml
└── tests/                 # Test suite
```

## Performance

- **LM Studio**: Faster inference with GPU acceleration
- **Redis Caching**: Reduces response times for repeated queries
- **Structured Logging**: Better observability and debugging
- **Metrics**: Prometheus metrics for monitoring 