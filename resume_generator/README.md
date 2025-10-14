# Well Resume Generator

Automatic white-labeled resume generation for Zoho CRM candidates using Azure OpenAI GPT-5-mini.

## Overview

**Brandon's Requirements:**
- ✅ One-page PDF with Well branding
- ✅ Black letterhead background with gold circular decorations
- ✅ Executive summary generated from interview notes (NOT from resume)
- ✅ LinkedIn profile as primary data source
- ✅ Automatic extraction (no forced editing)
- ✅ Optional preview and edit before saving

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ Zoho CRM    │────▶│ Resume API   │────▶│ Azure GPT-5 │
│ Custom Btn  │     │ Port 8002    │     │ mini        │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    │  Playwright │
                    │  PDF Gen    │
                    └─────────────┘
```

### Services
- **OpenAI Service** - LinkedIn extraction, executive summary generation
- **Zoho Service** - Candidate fetch, LinkedIn PDF download, resume upload
- **Compression Service** - Smart one-page fitting (3 jobs, 3 bullets, 12 skills)
- **PDF Service** - Playwright-based PDF generation

### API Endpoints

#### `GET /api/resume/generate/{candidate_id}`
Generate resume HTML preview from Zoho candidate data.

**Response:**
```json
{
  "candidate_id": "123456",
  "candidate_name": "John Doe",
  "html_preview": "<html>...",
  "resume_data": {...},
  "was_compressed": false
}
```

#### `GET /api/resume/preview/{candidate_id}`
Get HTML preview directly (returns HTML, not JSON).

#### `POST /api/resume/save`
Save reviewed HTML as PDF attachment to Zoho.

**Request:**
```json
{
  "candidate_id": "123456",
  "html_content": "<html>...",
  "filename": "Resume_JohnDoe.pdf"
}
```

#### `POST /api/resume/save-direct/{candidate_id}`
Generate and save resume without preview (automated workflow).

## Quick Start

### 1. Setup Environment

```bash
# Copy environment variables
cp .env.template .env.local

# Edit with your credentials
# Copy values from: ../../../.env.local
nano .env.local
```

**Required Variables:**
```bash
AZURE_OPENAI_ENDPOINT=https://eastus2.api.cognitive.microsoft.com/
AZURE_OPENAI_KEY=your-key
AZURE_OPENAI_DEPLOYMENT=gpt-5-mini
AZURE_OPENAI_API_VERSION=2024-08-01-preview
ZOHO_OAUTH_SERVICE_URL=https://well-zoho-oauth-v2.azurewebsites.net
```

### 2. Start API

```bash
./start.sh
```

This will:
- Create virtual environment
- Install dependencies
- Install Playwright browsers
- Start API on port 8002

### 3. Test API

Visit: http://localhost:8002/docs

Try the `/health` endpoint first to verify everything is working.

## Development

### Manual Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
uvicorn app.main:app --reload --port 8002
```

### Testing

```bash
# Test candidate generation
curl http://localhost:8002/api/resume/generate/YOUR_CANDIDATE_ID

# Test HTML preview
curl http://localhost:8002/api/resume/preview/YOUR_CANDIDATE_ID

# Test direct save
curl -X POST http://localhost:8002/api/resume/save-direct/YOUR_CANDIDATE_ID
```

### Project Structure

```
resume_generator/
├── app/
│   ├── api/
│   │   ├── generate.py      # Resume generation endpoint
│   │   └── save.py           # PDF save endpoint
│   ├── models/
│   │   ├── candidate.py      # Zoho candidate models
│   │   └── resume.py         # Resume data models
│   ├── services/
│   │   ├── openai_service.py # GPT-5-mini extraction
│   │   ├── zoho_service.py   # Zoho CRM integration
│   │   ├── compression.py    # One-page fitting
│   │   └── pdf_service.py    # PDF generation
│   ├── templates/
│   │   └── resume_template.html  # Branded HTML template
│   ├── static/
│   │   ├── well-logo.png
│   │   └── well-favicon.png
│   ├── config.py            # Settings
│   └── main.py              # FastAPI app
├── requirements.txt
├── .env.template
└── start.sh
```

## Deployment

### Docker Build

```bash
docker build -t wellintakeacr0903.azurecr.io/resume-generator:latest .
docker push wellintakeacr0903.azurecr.io/resume-generator:latest
```

### Azure Container Apps

Deploy to `well-intake-env` environment alongside main API and teams bot.

```bash
az containerapp create \
  --name resume-generator \
  --resource-group TheWell-Infra-East \
  --environment well-intake-env \
  --image wellintakeacr0903.azurecr.io/resume-generator:latest \
  --target-port 8002 \
  --ingress external \
  --min-replicas 0 \
  --max-replicas 3
```

## Key Features

### 1. Automatic LinkedIn Extraction
- GPT-5-mini with temperature=1.0 (required for GPT-5)
- JSON mode for structured output
- Extracts: experience, education, skills, certifications

### 2. Executive Summary Generation
- Uses interview notes (NOT resume text)
- Tailored to target role
- 2-3 sentences, leadership-focused

### 3. Smart Compression
- Limits to 3 most recent jobs
- Max 3 bullets per job
- Top 12 skills only
- AI-powered bullet compression preserving metrics

### 4. One-Page Constraint
- 11 inches @ 96dpi = 1056px maximum height
- CSS: `page-break-inside: avoid` prevents card splitting
- Automatic compression if content exceeds limit

### 5. Well Branding
- Black header with gold (#C9B037) circular decorations
- Gold candidate name, white contact info
- Professional layout with section headings
- Well logo in header

## Configuration

### GPT-5 Requirements
- **Temperature**: MUST be 1.0 (enforced by Azure)
- **Deployment**: gpt-5-mini
- **API Version**: 2024-08-01-preview or later
- **JSON Mode**: `response_format={"type": "json_object"}`

### Zoho Integration
- Uses existing OAuth proxy (well-zoho-oauth-v2.azurewebsites.net)
- No direct API keys needed
- Fetches from Candidates module
- Uploads to Attachments

### PDF Generation
- Playwright Chromium browser
- US Letter size (8.5" x 11")
- Print background enabled (for black header)
- Zero margins (template handles spacing)

## Troubleshooting

### "temperature must be 1"
Always use `temperature=1.0` for all GPT-5 calls. This is enforced by Azure.

### "No LinkedIn PDF found"
Ensure candidate has LinkedIn PDF attachment in Zoho with correct filename pattern.

### "Content exceeds one page"
Compression service will automatically reduce content. Check compression logic if still failing.

### Playwright browser not found
Run: `playwright install chromium`

## Next Steps

1. ✅ Backend API complete
2. ⏳ Create React frontend for preview UI
3. ⏳ Create Dockerfile for deployment
4. ⏳ Deploy to Azure Container Apps
5. ⏳ Configure Zoho custom button
6. ⏳ End-to-end testing with real candidates

## Notes

- Port 8002 (main API on 8000, teams bot on 8001)
- All GPT-5 calls use temperature=1.0
- No hardcoded Zoho owner IDs (uses ZOHO_DEFAULT_OWNER_EMAIL)
- Compression preserves quantifiable metrics
- Executive summary from interview notes ONLY
