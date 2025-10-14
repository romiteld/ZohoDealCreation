import os
import json
from openai import AzureOpenAI
import fitz  # PyMuPDF
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
        Uses PyMuPDF (fitz) for superior PDF text extraction (2025 best practice).
        """
        # Extract text from PDF using PyMuPDF
        print(f"[OpenAI Service] Extracting text from PDF ({len(pdf_bytes)} bytes) using PyMuPDF...")
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_count = len(doc)
        text = "\n".join([page.get_text() for page in doc])
        doc.close()

        print(f"[OpenAI Service] Extracted {len(text)} characters from {page_count} pages")

        if not text or len(text.strip()) < 50:
            raise ValueError(f"PDF text extraction failed or insufficient content (only {len(text)} chars)")

        print(f"[OpenAI Service] Calling GPT-5 for PDF data extraction...")
        print(f"[OpenAI Service] First 200 chars of text: {text[:200]}")

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

CRITICAL - Location Extraction:
- For each job experience, ALWAYS extract the location in "City, State" format
- Look for location in the resume (usually appears after company name)
- If only city is shown, include state if mentioned elsewhere
- If location is missing, leave the field empty (enrichment will handle it)
- Examples: "Seattle, WA" | "New York, NY" | "Austin, TX"

Focus on:
- Quantifiable achievements (numbers, percentages, dollar amounts)
- Keep bullets concise (one line each)
- Most recent 3-4 jobs
- Top 12 skills
- Extract dates in format "Month YYYY - Month YYYY" or "Month YYYY - Present"
- Include contact information if available
- ALWAYS prioritize extracting job locations from the resume text
"""
                },
                {
                    "role": "user",
                    "content": f"Resume/LinkedIn Profile:\n\n{text}"
                }
            ],
            temperature=1.0,  # REQUIRED for GPT-5
            max_completion_tokens=4000,  # Increased for comprehensive resume extraction with all jobs/skills/education
            response_format={"type": "json_object"}
        )

        print(f"[OpenAI Service] PDF extraction response ID: {response.id}")
        print(f"[OpenAI Service] PDF extraction finish reason: {response.choices[0].finish_reason}")

        content = response.choices[0].message.content
        print(f"[OpenAI Service] PDF extraction content length: {len(content) if content else 0}")

        if not content or not content.strip():
            raise ValueError("GPT-5 returned empty response for PDF extraction")

        print(f"[OpenAI Service] PDF extraction first 200 chars: {content[:200]}")

        try:
            parsed_data = json.loads(content)
            print(f"[OpenAI Service] Successfully parsed JSON with keys: {list(parsed_data.keys())}")
            return parsed_data
        except json.JSONDecodeError as e:
            print(f"[OpenAI Service] JSON parse error: {e}")
            print(f"[OpenAI Service] Raw content: {content}")
            raise ValueError(f"Failed to parse GPT-5 response as JSON: {e}")

    async def generate_executive_summary(
        self,
        interview_notes: str,
        candidate_name: str,
        target_role: str
    ) -> str:
        """
        Generate custom Executive Summary using structured outputs (JSON Schema).

        This ensures:
        - Exactly 2-4 sentences (enforced by schema)
        - Candidate-specific content (injected in system prompt)
        - Consistent format across all generations

        Uses Azure OpenAI GPT-5-mini with structured outputs for reliability.
        """
        import time
        max_retries = 3
        retry_delay = 2  # seconds

        # Define JSON schema for structured output
        # Note: Azure OpenAI strict mode doesn't support type: ["string", "null"]
        # So we make sentence_4 required but allow empty string
        json_schema = {
            "type": "object",
            "properties": {
                "sentence_1": {
                    "type": "string",
                    "description": "Overview sentence highlighting years of experience and key expertise area"
                },
                "sentence_2": {
                    "type": "string",
                    "description": "Major achievement sentence with specific metrics or numbers"
                },
                "sentence_3": {
                    "type": "string",
                    "description": "Additional achievement or leadership quality with impact"
                },
                "sentence_4": {
                    "type": "string",
                    "description": "Optional 4th sentence - return empty string if not needed"
                }
            },
            "required": ["sentence_1", "sentence_2", "sentence_3", "sentence_4"],
            "additionalProperties": False
        }

        for attempt in range(max_retries):
            try:
                print(f"[OpenAI Service] Calling GPT-5 with structured outputs (attempt {attempt + 1}/{max_retries})...")
                print(f"[OpenAI Service] Model: {self.deployment}")
                print(f"[OpenAI Service] Candidate: {candidate_name}")
                print(f"[OpenAI Service] Context length: {len(interview_notes)}")

                response = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=[
                        {
                            "role": "system",
                            "content": f"""You are an expert resume writer creating a CONCISE Executive Summary for {candidate_name}.

TARGET ROLE: {target_role}

CRITICAL REQUIREMENTS:
1. Extract ONLY the TOP 2-3 most impressive metrics and achievements
2. Be concise - prioritize quality over quantity of metrics
3. Focus on the BIGGEST numbers and most relevant accomplishments
4. Include years of experience and current/most recent role
5. NO generic phrases - every word must be specific to THIS candidate

STRUCTURE (JSON format):
- sentence_1: "{candidate_name} is a [specific role] with [X] years of experience at [company]..."
  Keep this sentence SHORT and focused on role + experience
- sentence_2: ONE major quantifiable achievement with the BIGGEST/BEST metrics
  Example: "Secured $80M+ in AUM and finished #1 nationally at Fidelity"
- sentence_3: ONE additional high-impact achievement with specific metrics
  Example: "Mentored associates to improve KPIs by 30% while maintaining 90%+ client satisfaction"
- sentence_4: ONLY include if there's a unique standout accomplishment (passed CFP, authored book, military service, etc.)
  Otherwise return empty string

CONCISENESS RULES:
- Prioritize the HIGHEST numbers and most impressive achievements
- Combine related metrics in one sentence when possible
- Avoid listing every single metric - focus on what makes them stand out
- Keep total summary under 500 characters if possible

EXAMPLES OF GOOD SENTENCES:
✅ "Secured $80M+ in AUM and finished #1 nationally across core metrics"
✅ "Mentored junior associates to improve KPIs by 30% while maintaining 90%+ satisfaction scores"
✅ "Passed CFP® exam and Series 7/66 on first attempt after leaving Fidelity"

EXAMPLES OF BAD SENTENCES (too long/unfocused):
❌ "At Fidelity he maintained client satisfaction scores above 90%, conducted deep-dive consultations for hundreds of plan participants, and mentored junior associates to improve their KPIs by 30%"

RULES:
- Use ONLY information from the candidate's background
- Pull the MOST IMPRESSIVE metrics from Interview Notes or job bullets
- Third person only
- Prioritize brevity and impact over comprehensive coverage"""
                        },
                        {
                            "role": "user",
                            "content": f"""Create a CONCISE Executive Summary for {candidate_name} using ONLY the specific information below.

Review all the information and select ONLY the TOP 2-3 most impressive achievements with the BIGGEST metrics:

{interview_notes}

Generate 2-3 sentences (4 ONLY if there's a truly unique standout like CFP/military/book).
Prioritize QUALITY over QUANTITY - use the highest numbers and most relevant accomplishments only.
Be concise and impactful."""
                        }
                    ],
                    temperature=1.0,  # REQUIRED for Azure OpenAI GPT-5
                    max_completion_tokens=3000,  # Significantly increased for comprehensive context + structured JSON output
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "executive_summary_response",
                            "strict": True,
                            "schema": json_schema
                        }
                    }
                )

                print(f"[OpenAI Service] Response ID: {response.id}")
                print(f"[OpenAI Service] Model used: {response.model}")
                print(f"[OpenAI Service] Finish reason: {response.choices[0].finish_reason}")

                content = response.choices[0].message.content
                print(f"[OpenAI Service] Raw JSON response: {content}")

                if not content or not content.strip():
                    print("[OpenAI Service] WARNING: Empty response from GPT-5")
                    raise ValueError("Empty response from GPT-5")

                # Parse JSON response
                summary_data = json.loads(content)

                # Combine sentences into final summary
                # Filter out empty strings and placeholder values
                sentences = []
                for i in range(1, 5):
                    sentence_key = f"sentence_{i}"
                    sentence = summary_data.get(sentence_key)
                    # Skip empty, whitespace-only, or placeholder values
                    if sentence and sentence.strip() and sentence.strip().lower() not in ["", "n/a", "none", "not applicable"]:
                        sentences.append(sentence.strip())

                if len(sentences) < 2:
                    print(f"[OpenAI Service] WARNING: Only {len(sentences)} sentences generated")
                    raise ValueError(f"Insufficient sentences: {len(sentences)}")

                final_summary = " ".join(sentences)
                print(f"[OpenAI Service] Final summary ({len(sentences)} sentences): {final_summary}")

                return final_summary

            except Exception as e:
                print(f"[OpenAI Service] ERROR on attempt {attempt + 1}: {type(e).__name__}: {e}")

                # If this is the last attempt, return fallback
                if attempt == max_retries - 1:
                    print(f"[OpenAI Service] All {max_retries} attempts failed, using fallback summary")
                    return f"{candidate_name} brings extensive experience in financial services with a proven track record of success."

                # Otherwise, wait and retry
                wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                print(f"[OpenAI Service] Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
