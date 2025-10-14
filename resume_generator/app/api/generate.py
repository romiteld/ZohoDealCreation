from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from jinja2 import Template
import os
import io
import base64

from app.services.zoho_service import ZohoService
from app.services.openai_service import OpenAIService
from app.services.location_enrichment import LocationEnrichmentService

router = APIRouter()

# Template will be loaded on first use
RESUME_TEMPLATE = None
LOGO_BASE64 = None

def get_logo_base64():
    """Load and cache the logo as base64 data URI for embedding in <img> tags"""
    global LOGO_BASE64
    if LOGO_BASE64 is None:
        # Read the pre-generated logo CSS which contains base64 data URI
        logo_css_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "logo-css.txt"
        )
        if os.path.exists(logo_css_path):
            with open(logo_css_path, "r") as f:
                css_content = f.read().strip()
                # Extract the data URI from: background-image: url(data:image/png;base64,...)
                if "url(" in css_content and ")" in css_content:
                    start = css_content.find("url(") + 4
                    end = css_content.rfind(")")
                    LOGO_BASE64 = css_content[start:end]
                else:
                    LOGO_BASE64 = ""
        else:
            # Fallback to empty string if file not found
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
    location_service = LocationEnrichmentService()

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

        # Step 4: Generate executive summary from extracted resume data
        print(f"[Resume Editor] Generating executive summary...")
        try:
            # Use extracted experience and skills to generate summary
            experience_summary = extracted_data.get("jobs", extracted_data.get("experience", []))
            skills = extracted_data.get("skills", [])

            # Build comprehensive context for summary generation
            context_parts = []

            # Add interview notes if available (highest priority - contains key achievements)
            if candidate.interview_notes and candidate.interview_notes.strip():
                context_parts.append(f"Interview Notes:\n{candidate.interview_notes}")

            # Add ALL experience with FULL details (not just 2 jobs)
            if experience_summary and len(experience_summary) > 0:
                context_parts.append("\nProfessional Experience:")
                for job in experience_summary:
                    company = job.get("company", "Unknown")
                    title = job.get("title", "Unknown")
                    dates = job.get("dates", "")
                    bullets = job.get("bullets", [])

                    job_text = f"• {title} at {company}"
                    if dates:
                        job_text += f" ({dates})"

                    # Include ALL bullets (not just first 2)
                    if bullets:
                        job_text += "\n  - " + "\n  - ".join(bullets)

                    context_parts.append(job_text)

            # Add ALL skills (not just 8)
            if skills:
                context_parts.append(f"\nKey Skills: {', '.join(skills)}")

            # Generate summary using GPT-5
            combined_context = "\n".join(context_parts)
            print(f"[Resume Editor] Context for summary (length: {len(combined_context)}): {combined_context[:200]}")
            executive_summary = await openai_service.generate_executive_summary(
                interview_notes=combined_context,
                candidate_name=candidate.full_name,
                target_role=candidate.target_role or "leadership position"
            )
            print(f"[Resume Editor] Generated executive summary (length: {len(executive_summary)}): {executive_summary}")
        except Exception as e:
            print(f"[Resume Editor] ERROR generating summary: {e}")
            executive_summary = "Results-driven professional with extensive experience in financial services."

        # Step 5: Enrich missing job locations using Azure Maps
        print(f"[Resume Editor] Enriching missing job locations...")
        experience_data = extracted_data.get("jobs", extracted_data.get("experience", []))
        enriched_experience = await location_service.enrich_job_locations(experience_data)

        # Step 6: Determine candidate's current location (3-tier priority)
        # Priority 1: Current_Location from Zoho (highest priority)
        city_state = candidate.current_location or ""

        # Priority 2: Fallback to city/state fields if Current_Location is empty
        if not city_state:
            city_state = f"{candidate.city or ''}, {candidate.state or ''}".strip(", ")

        print(f"[Resume Editor] Using candidate location: {city_state}")

        # Step 7: Build resume data structure
        resume_data = {
            "candidate_id": candidate_id,
            "candidate_name": candidate.full_name,
            "email": candidate.email or extracted_data.get("email", ""),
            "phone": candidate.phone or extracted_data.get("phone", ""),
            "city_state": city_state,
            "linkedin_url": candidate.linkedin_url or extracted_data.get("linkedin_url", ""),
            "executive_summary": executive_summary,
            "experience": enriched_experience,
            "education": extracted_data.get("education", []),
            "skills": extracted_data.get("skills", []),
            "logo_base64": get_logo_base64(),
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
        # Add logo base64 data URI to resume data
        resume_data['logo_base64'] = get_logo_base64()

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
