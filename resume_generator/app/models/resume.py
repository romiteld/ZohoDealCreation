from pydantic import BaseModel
from typing import List, Optional

class JobExperience(BaseModel):
    title: str
    company: str
    location: Optional[str] = ""
    dates: str
    bullets: List[str]

class Education(BaseModel):
    school: str
    degree: str
    major: Optional[str] = ""
    year: str

class LinkedInData(BaseModel):
    name: str
    jobs: List[JobExperience]
    skills: List[str]
    education: List[Education]

class ResumeData(BaseModel):
    candidate_name: str
    email: Optional[str] = ""
    phone: Optional[str] = ""
    city_state: Optional[str] = ""
    linkedin_url: Optional[str] = ""
    executive_summary: str
    experience: List[JobExperience]
    skills: List[str]
    education: List[Education]

class ResumeResponse(BaseModel):
    success: bool
    html_preview: str
    resume_data: ResumeData
    fits_one_page: bool

class GenerateResumeResponse(BaseModel):
    """Response from generate_resume endpoint"""
    candidate_id: str
    candidate_name: str
    html_preview: str
    resume_data: dict
    was_compressed: bool

class SummaryRequest(BaseModel):
    interview_notes: str
    candidate_name: str
    target_role: str

class SummaryResponse(BaseModel):
    summary: str
    tokens: int
    cost: float

class CompressionRequest(BaseModel):
    job_description: str
    target_length: int

class PDFRequest(BaseModel):
    html_content: str
    candidate_name: str

class AttachmentRequest(BaseModel):
    candidate_id: str
    pdf_data: str
    filename: str
