from pydantic import BaseModel
from typing import Optional, List

class CandidateResponse(BaseModel):
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    linkedin_url: Optional[str] = None
    interview_notes: Optional[str] = None
    target_role: Optional[str] = None
