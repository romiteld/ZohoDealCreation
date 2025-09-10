"""
Authentication utilities
"""
from fastapi import Header, HTTPException, status
from typing import Optional
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.local")

API_KEY = os.getenv("API_KEY", "")

async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Verify API key from header"""
    if not API_KEY:
        # If no API key is configured, allow access (development mode)
        return True
    
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key"
        )
    return True