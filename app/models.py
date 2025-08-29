from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# --- API Data Contracts ---

class AttachmentPayload(BaseModel):
    filename: str
    content_base64: str
    content_type: str

class EmailPayload(BaseModel):
    sender_name: Optional[str] = None
    sender_email: str
    subject: str
    body: str
    attachments: List[AttachmentPayload] = []
    raw_email: Optional[str] = Field(None, description="Raw email content for metadata extraction")
    reply_to: Optional[str] = Field(None, description="Reply-To header if different from sender")
    user_corrections: Optional[Dict[str, Any]] = Field(None, description="User corrections to AI extraction")
    ai_extraction: Optional[Dict[str, Any]] = Field(None, description="Original AI extraction for learning")

class ExtractedData(BaseModel):
    candidate_name: Optional[str] = Field(None, description="The full name of the candidate.")
    job_title: Optional[str] = Field(None, description="The job title being discussed (e.g., Advisor).")
    location: Optional[str] = Field(None, description="The location for the role (e.g., Fort Wayne, Indiana).")
    company_name: Optional[str] = Field(None, description="The official name of the candidate's firm.")
    referrer_name: Optional[str] = Field(None, description="The full name of the person who made the referral.")
    website: Optional[str] = Field(None, description="Company website URL.")
    phone: Optional[str] = Field(None, description="Contact phone number.")
    industry: Optional[str] = Field(None, description="Company industry or sector.")

class ProcessingResult(BaseModel):
    status: str
    message: str
    deal_id: Optional[str] = None
    account_id: Optional[str] = None
    contact_id: Optional[str] = None
    deal_name: Optional[str] = Field(None, description="The formatted deal name that was created")
    primary_email: Optional[str] = Field(None, description="The email address used (Reply-To or From)")

class HealthStatus(BaseModel):
    status: str
    version: str
    business_rules: str
    zoho_api: str
    services: dict = Field(default_factory=dict)
