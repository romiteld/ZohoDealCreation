import os
import json
from openai import AzureOpenAI
from pypdf import PdfReader
from io import BytesIO
from app.config import settings

class OpenAIService:
    def __init__(self):
        self.client = AzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION
        )
        self.deployment = settings.AZURE_OPENAI_DEPLOYMENT  # "gpt-5-mini"

    async def extract_linkedin_data(self, pdf_bytes: bytes):
        """
        Extract structured data from LinkedIn PDF.
        Uses GPT-5-mini with Structured Output (JSON mode).
        Temperature: 1.0 (REQUIRED for GPT-5 per CLAUDE.md)
        """
        # Extract text from PDF
        reader = PdfReader(BytesIO(pdf_bytes))
        text = "\n".join([page.extract_text() for page in reader.pages])

        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {
                    "role": "system",
                    "content": """Extract structured data from resume/LinkedIn profile. Return JSON with this exact structure:
{
    "name": "Full Name",
    "email": "email@example.com",
    "phone": "(555) 123-4567",
    "linkedin_url": "https://linkedin.com/in/profile",
    "experience": [
        {
            "title": "Job Title",
            "company": "Company Name",
            "location": "City, State",
            "dates": "Start - End (or Present)",
            "bullets": ["Achievement with quantifiable metrics", "Key responsibility with impact"]
        }
    ],
    "skills": ["Skill 1", "Skill 2", "Skill 3"],
    "education": [
        {
            "school": "University Name",
            "degree": "Degree Type (e.g., Bachelor of Science)",
            "major": "Field of Study",
            "year": "Graduation Year"
        }
    ]
}

Focus on:
- Quantifiable achievements (numbers, percentages, dollar amounts)
- Keep bullets concise (one line each)
- Most recent 3-4 jobs
- Top 12 skills
- Extract dates in format "Month YYYY - Month YYYY" or "Month YYYY - Present"
- Include contact information if available
"""
                },
                {
                    "role": "user",
                    "content": f"Resume/LinkedIn Profile:\n\n{text}"
                }
            ],
            temperature=1.0,  # REQUIRED for GPT-5
            max_completion_tokens=2000,  # GPT-5 uses max_completion_tokens not max_tokens
            response_format={"type": "json_object"}
        )

        return json.loads(response.choices[0].message.content)

    async def generate_executive_summary(
        self,
        interview_notes: str,
        candidate_name: str,
        target_role: str
    ) -> str:
        """
        Generate custom Executive Summary from interview notes.
        Brandon's requirement: "our summary" - NOT from the resume.
        From first paragraph of interview notes.
        """
        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {
                    "role": "system",
                    "content": """Generate a professional 3-4 sentence Executive Summary for a white-labeled resume.

Write in third person. Focus on:
- Key achievements and measurable impact
- Relevant experience for the target role
- Unique strengths and leadership qualities
- Professional brand and value proposition

Be concise and impactful. This is the first thing hiring managers see.
Use strong action verbs and avoid generic phrases."""
                },
                {
                    "role": "user",
                    "content": f"""Candidate: {candidate_name}
Target Role: {target_role}

Interview Notes:
{interview_notes}

Generate Executive Summary (3-4 sentences):"""
                }
            ],
            temperature=1.0,  # REQUIRED for GPT-5
            max_completion_tokens=200  # GPT-5 uses max_completion_tokens not max_tokens
        )

        return response.choices[0].message.content
