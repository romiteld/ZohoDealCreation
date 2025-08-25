# Well Intake API - Intelligent Email Processing System

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green.svg)](https://fastapi.tiangolo.com/)
[![Azure](https://img.shields.io/badge/Azure-Deployed-blue.svg)](https://azure.microsoft.com/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)]()

An intelligent email processing system that automatically converts recruitment emails into structured CRM records in Zoho. Powered by AI-driven data extraction using CrewAI and GPT-5-mini, this system eliminates manual data entry and ensures consistent, accurate record creation.

## 🎯 Key Features

- **🤖 AI-Powered Extraction**: Uses CrewAI with GPT-5-mini to intelligently extract candidate information from unstructured emails
- **📧 Outlook Integration**: Seamless integration via Outlook Add-in with "Send to Zoho" button
- **🔄 Automated CRM Creation**: Automatically creates Accounts, Contacts, and Deals in Zoho CRM
- **🚫 Duplicate Prevention**: Smart deduplication based on email and company matching
- **📎 Attachment Handling**: Automatic upload and storage of email attachments to Azure Blob Storage
- **🏢 Multi-User Support**: Configurable owner assignment for enterprise deployment
- **⚡ Performance Optimized**: Dual implementation with optimized versions for production use
- **🔍 Web Research**: Validates company information using Firecrawl API

## 🏗️ Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Outlook Email  │────▶│  Outlook Add-in  │────▶│   FastAPI App   │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                           │
                        ┌──────────────────────────────────┼──────────────────────────────────┐
                        │                                  │                                  │
                  ┌─────▼──────┐                    ┌─────▼──────┐                    ┌──────▼─────┐
                  │   CrewAI   │                    │ Azure Blob │                    │  Zoho CRM  │
                  │ GPT-5-mini │                    │   Storage  │                    │   API v8   │
                  └─────┬──────┘                    └────────────┘                    └──────┬─────┘
                        │                                                                     │
                  ┌─────▼──────┐                                                      ┌──────▼─────┐
                  │ PostgreSQL │                                                      │   OAuth    │
                  │  (Cosmos)  │                                                      │  Service   │
                  └────────────┘                                                      └────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Azure account with active subscription
- Zoho CRM account with API access
- OpenAI API key for GPT-5-mini
- Firecrawl API key for web research

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd outlook
```

2. **Set up virtual environment**
```bash
python -m venv zoho
source zoho/bin/activate  # Linux/Mac
# or
zoho\Scripts\activate  # Windows
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
Create a `.env.local` file in the root directory:
```env
# API Configuration
API_KEY=your-secure-api-key-here
ENVIRONMENT=development

# Azure Services
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
AZURE_STORAGE_CONTAINER_NAME=email-attachments
DATABASE_URL=postgresql://user:password@host:port/database

# AI Services
OPENAI_API_KEY=sk-...
FIRECRAWL_API_KEY=fc-...

# Zoho Integration
ZOHO_OAUTH_SERVICE_URL=https://well-zoho-oauth.azurewebsites.net
CLIENT_ID=1000.YOUR_CLIENT_ID
CLIENT_SECRET=your_client_secret
REDIRECT_URI=https://well-zoho-oauth.azurewebsites.net/callback
ZOHO_DEFAULT_OWNER_ID=owner_id_here  # Optional
ZOHO_DEFAULT_OWNER_EMAIL=owner@example.com  # Optional

# Monitoring (Optional)
LOG_ANALYTICS_WORKSPACE_ID=workspace-id
APPLICATION_INSIGHTS_KEY=ai-key
```

5. **Run the application**
```bash
# Quick start (handles everything automatically)
./startup.sh

# Or manually
uvicorn app.main:app --reload --port 8000
```

6. **Access the application**
- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- Test Endpoint: http://localhost:8000/test/kevin-sullivan

## 📋 API Endpoints

### Core Endpoints

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|----------------|
| POST | `/intake/email` | Process email and create Zoho records | API Key |
| GET | `/test/kevin-sullivan` | Test the full pipeline with sample data | API Key |
| GET | `/health` | Health check endpoint | None |
| GET | `/manifest.xml` | Outlook Add-in manifest | None |

### Request Format

```json
POST /intake/email
{
    "subject": "Email subject",
    "body": "Email body content",
    "sender": "sender@example.com",
    "attachments": [
        {
            "name": "resume.pdf",
            "content": "base64_encoded_content"
        }
    ]
}
```

### Response Format

```json
{
    "success": true,
    "message": "Email processed successfully",
    "data": {
        "account_id": "123456789",
        "contact_id": "987654321",
        "deal_id": "456789123",
        "attachments_uploaded": 1
    }
}
```

## 🧪 Testing

### Run All Tests
```bash
python test_all.py
```

### Run Specific Test Suites
```bash
# Test dependencies
python test_dependencies.py

# Test API endpoints
python test_api_endpoints.py

# Test integrations
python test_integrations.py

# Test with pytest
pytest app/test_business_rules.py -v
pytest --cov=app --cov-report=html
```

### Test the Kevin Sullivan Endpoint
```bash
curl -X GET "http://localhost:8000/test/kevin-sullivan" \
  -H "X-API-Key: your-secure-api-key-here" | python -m json.tool
```

## 🚢 Deployment

### Azure Deployment

1. **Prepare deployment package**
```bash
zip -r deploy.zip . -x "zoho/*" "*.pyc" "__pycache__/*" ".env*" "*.git*" "deploy.zip" "test_*.py" "server.log"
```

2. **Deploy to Azure**
```bash
az webapp deploy --resource-group TheWell-App-East \
  --name well-intake-api --src-path deploy.zip --type zip
```

3. **Configure startup command**
```bash
az webapp config set --resource-group TheWell-App-East --name well-intake-api \
  --startup-file "gunicorn --bind=0.0.0.0:8000 --timeout 600 --workers 2 --worker-class uvicorn.workers.UvicornWorker app.main:app"
```

4. **Monitor logs**
```bash
az webapp log tail --resource-group TheWell-App-East --name well-intake-api
```

### Outlook Add-in Installation

1. Navigate to Microsoft 365 Admin Center
2. Go to Integrated Apps → Upload custom apps → Office Add-in
3. Provide manifest URL: `https://well-intake-api.azurewebsites.net/manifest.xml`
4. Add authorized users
5. The "Send to Zoho" button will appear in Outlook

## 🔧 Configuration

### Business Rules

The system enforces the following business rules:

- **Deal Name Format**: `"[Job Title] ([Location]) - [Firm Name]"`
- **Source Determination Priority**:
  1. Referral (if referrer present)
  2. Reverse Recruiting (if TWAV/Advisor Vault mentioned)
  3. Website Inbound (if Calendly link present)
  4. Email Inbound (default)

### CrewAI Configuration

The system uses three sequential AI agents:

1. **Extraction Agent**: Extracts basic candidate information
2. **Enrichment Agent**: Validates and enriches company data
3. **Validation Agent**: Cleans and standardizes output

**Critical Settings**:
- Model: GPT-5-mini (DO NOT CHANGE)
- Temperature: 1 (required for GPT-5-mini)
- Memory: Disabled for performance
- Max Execution Time: 30 seconds

## 📁 Project Structure

```
outlook/
├── app/                      # Main application code
│   ├── main.py              # FastAPI application
│   ├── main_optimized.py    # Optimized version
│   ├── crewai_manager.py    # AI orchestration
│   ├── business_rules.py    # Business logic
│   ├── integrations.py      # External service integrations
│   ├── models.py            # Pydantic models
│   └── static_files.py      # Static file serving
├── addin/                    # Outlook Add-in files
│   ├── manifest.xml         # Add-in configuration
│   ├── commands.js          # JavaScript functionality
│   └── *.html               # UI components
├── test_*.py                 # Test files
├── requirements.txt          # Python dependencies
├── startup.sh               # Quick start script
├── .env.local               # Environment variables (create this)
└── CLAUDE.md                # AI assistant instructions
```

## 🐛 Troubleshooting

### Common Issues

#### CrewAI Timeout
- **Problem**: CrewAI takes >2 minutes or times out
- **Solution**: Ensure `memory=False` and `max_execution_time=30` in CrewAI configuration

#### GPT-5-mini Temperature Error
- **Problem**: "temperature must be 1 for GPT-5-mini"
- **Solution**: Always use `temperature=1`, never change to other values

#### Zoho Owner Field Errors
- **Problem**: 400 Bad Request when creating Deals
- **Solution**: Ensure `ZOHO_DEFAULT_OWNER_ID` or `ZOHO_DEFAULT_OWNER_EMAIL` is configured

#### API Key Authentication Failed
- **Problem**: 403 Invalid API Key
- **Solution**: Verify `.env.local` exists and is loaded with `load_dotenv('.env.local')`

## 📊 Performance Metrics

- **Average Processing Time**: 45-55 seconds per email
- **CrewAI Execution**: ~10 seconds (after optimizations)
- **Zoho API Operations**: ~20-30 seconds
- **Attachment Upload**: ~5-10 seconds per file

## 🔐 Security Considerations

- API key authentication required for all endpoints
- Environment variables for sensitive configuration
- No hardcoded credentials or owner IDs
- Secure OAuth2 flow for Zoho authentication
- Azure Blob Storage for attachment security

## 🤝 Contributing

This is a proprietary system for The Well Recruiting. For questions or issues, please contact the development team.

## 📄 License

Proprietary - All rights reserved by The Well Recruiting

## 🆘 Support

For support and questions:
- Check the `CLAUDE.md` file for development guidelines
- Review test files for usage examples
- Contact the development team for assistance

---

**Production URL**: https://well-intake-api.azurewebsites.net

**Last Updated**: August 2025