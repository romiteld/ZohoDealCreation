from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from jinja2 import Template
import os
import io
import base64

from app.services.zoho_service import ZohoService
from app.services.openai_service import OpenAIService

router = APIRouter()

# Template will be loaded on first use
RESUME_TEMPLATE = None
LOGO_BASE64 = None

def get_logo_css():
    """Load and cache the logo CSS with base64 data URI"""
    global LOGO_BASE64
    if LOGO_BASE64 is None:
        # Read the pre-generated logo CSS
        logo_css_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "logo-css.txt"
        )
        if os.path.exists(logo_css_path):
            with open(logo_css_path, "r") as f:
                LOGO_BASE64 = f.read().strip()
        else:
            # Fallback to empty CSS if file not found
            LOGO_BASE64 = ""
    return LOGO_BASE64

def get_template():
    """Lazy-load the HTML template"""
    global RESUME_TEMPLATE
    if RESUME_TEMPLATE is None:
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "templates",
            "resume_template.html"
        )
        with open(template_path, "r") as f:
            RESUME_TEMPLATE = Template(f.read())
    return RESUME_TEMPLATE






@router.get("/editor/{candidate_id}", response_class=HTMLResponse)
async def resume_editor(candidate_id: str):
    """
    Open interactive resume editor with live preview.
    This replaces the two-button approach with a single-page web app.

    Features:
    - Left panel: Edit form (contact, summary, experience, skills, education)
    - Right panel: Live preview that updates as you type
    - Generate PDF button to download final resume
    - Reset button to restore original data
    """
    zoho_service = ZohoService()
    openai_service = OpenAIService()

    try:
        # Step 1: Fetch candidate from Zoho
        print(f"[Resume Editor] Fetching candidate {candidate_id} from Zoho...")
        try:
            candidate = await zoho_service.fetch_candidate(candidate_id)
            print(f"[Resume Editor] Successfully fetched candidate: {candidate.full_name}")
        except Exception as e:
            print(f"[Resume Editor] ERROR fetching candidate: {type(e).__name__}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch candidate from Zoho: {str(e)}"
            )

        # Step 2: Download BOTH resume PDF and LinkedIn PDF (if available)
        resume_pdf = None
        linkedin_pdf = None

        # Try to get the regular resume first (priority)
        print(f"[Resume Editor] Attempting to download resume PDF...")
        try:
            resume_pdf = await zoho_service.get_resume_attachment(candidate_id)
            print(f"[Resume Editor] Successfully downloaded resume PDF ({len(resume_pdf)} bytes)")
        except ValueError as e:
            print(f"[Resume Editor] No resume PDF found: {str(e)}")
        except Exception as e:
            print(f"[Resume Editor] ERROR downloading resume PDF: {type(e).__name__}: {str(e)}")

        # Try to get LinkedIn profile as fallback
        print(f"[Resume Editor] Attempting to download LinkedIn PDF...")
        try:
            linkedin_pdf = await zoho_service.download_linkedin_pdf(candidate_id)
            print(f"[Resume Editor] Successfully downloaded LinkedIn PDF ({len(linkedin_pdf)} bytes)")
        except ValueError as e:
            print(f"[Resume Editor] No LinkedIn PDF found: {str(e)}")
        except Exception as e:
            print(f"[Resume Editor] ERROR downloading LinkedIn PDF: {type(e).__name__}: {str(e)}")

        # Ensure we have at least one PDF
        if not resume_pdf and not linkedin_pdf:
            raise HTTPException(
                status_code=404,
                detail="No resume or LinkedIn PDF attachments found for this candidate"
            )

        # Step 3: Extract data from available PDFs using GPT-5-mini
        # Priority: Use resume PDF if available, fallback to LinkedIn
        primary_pdf = resume_pdf if resume_pdf else linkedin_pdf
        print(f"[Resume Editor] Extracting data from PDF using GPT-5-mini...")
        try:
            extracted_data = await openai_service.extract_linkedin_data(primary_pdf)
            print(f"[Resume Editor] Successfully extracted data: {len(extracted_data)} fields")
        except Exception as e:
            print(f"[Resume Editor] ERROR extracting data: {type(e).__name__}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to extract data from PDF: {str(e)}"
            )

        # Step 4: Generate executive summary from interview notes
        executive_summary = "No executive summary available"
        if candidate.interview_notes and candidate.interview_notes.strip():
            executive_summary = await openai_service.generate_executive_summary(
                interview_notes=candidate.interview_notes,
                candidate_name=candidate.full_name,
                target_role=candidate.target_role or "leadership position"
            )

        # Step 5: Build resume data structure
        resume_data = {
            "candidate_id": candidate_id,
            "candidate_name": candidate.full_name,
            "email": candidate.email or extracted_data.get("email", ""),
            "phone": candidate.phone or extracted_data.get("phone", ""),
            "city_state": f"{candidate.city or ''}, {candidate.state or ''}".strip(", "),
            "linkedin_url": candidate.linkedin_url or extracted_data.get("linkedin_url", ""),
            "executive_summary": executive_summary,
            "experience": extracted_data.get("jobs", extracted_data.get("experience", [])),
            "education": extracted_data.get("education", []),
            "skills": extracted_data.get("skills", []),
            "logo_css": get_logo_css(),
        }

        # Step 6: Render editor template
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "templates",
            "resume_editor.html"
        )
        with open(template_path, "r") as f:
            editor_template = Template(f.read())

        html_content = editor_template.render(**resume_data)
        return HTMLResponse(content=html_content)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load resume editor: {str(e)}"
        )


@router.post("/generate-pdf/{candidate_id}")
async def generate_pdf_from_editor(candidate_id: str, resume_data: dict):
    """
    Generate PDF from edited resume data.
    Receives edited data from the editor UI and generates a PDF.

    This endpoint:
    1. Generates PDF from edited data
    2. Uploads PDF to Zoho as attachment
    3. Downloads PDF to user's computer

    This endpoint is called by the "Generate PDF" button in the editor.
    """
    from playwright.async_api import async_playwright

    zoho_service = ZohoService()

    try:
        # Add logo CSS to resume data
        resume_data['logo_css'] = get_logo_css()

        # Render the edited data using the resume template
        html_content = get_template().render(**resume_data)

        # Generate PDF using Playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            await page.set_content(html_content)

            # Generate PDF with proper margins
            pdf_bytes = await page.pdf(
                format='Letter',
                print_background=True,
                margin={
                    'top': '0',
                    'right': '0',
                    'bottom': '0',
                    'left': '0'
                }
            )

            await browser.close()

        candidate_name = resume_data.get("candidate_name", "Resume").replace(" ", "_")
        filename = f"{candidate_name}_Resume_TheWell.pdf"

        # Upload PDF to Zoho CRM as attachment
        try:
            await zoho_service.upload_resume_pdf(
                candidate_id=candidate_id,
                pdf_bytes=pdf_bytes,
                filename=filename
            )
        except Exception as upload_error:
            # Log error but don't fail the download
            print(f"Warning: Failed to upload PDF to Zoho: {upload_error}")

        # Return PDF as downloadable file
        pdf_stream = io.BytesIO(pdf_bytes)

        return StreamingResponse(
            pdf_stream,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate PDF: {str(e)}"
        )
