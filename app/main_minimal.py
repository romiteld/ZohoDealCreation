"""
Minimal FastAPI app for testing Azure deployment
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
import os

app = FastAPI(
    title="Well Intake API - Minimal",
    version="2.0.0-minimal"
)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Well Intake API",
        "version": "2.0.0-minimal",
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": os.getenv("ENVIRONMENT", "production"),
        "database_configured": bool(os.getenv("DATABASE_URL")),
        "openai_configured": bool(os.getenv("OPENAI_API_KEY"))
    }

@app.get("/test/kevin-sullivan")
async def test_kevin_sullivan():
    """Test endpoint - minimal version"""
    return {
        "success": True,
        "message": "Minimal test endpoint - full processing disabled",
        "extracted_data": {
            "candidate_name": "Kevin Sullivan",
            "job_title": "Senior Financial Advisor",
            "location": "Fort Wayne",
            "company_name": "Test Company",
            "referrer_name": "John Referrer"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)