from fastapi import APIRouter, HTTPException, Body, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

from app.services.zoho_service import ZohoService
from app.services.pdf_service import PDFGenerator
from app.services.progress_tracker import progress_tracker

router = APIRouter()


class SaveResumeRequest(BaseModel):
    """Request to save resume as PDF attachment to Zoho."""
    candidate_id: str
    html_content: str
    filename: Optional[str] = None


class SaveResumeResponse(BaseModel):
    """Response after saving resume."""
    success: bool
    candidate_id: str
    attachment_id: Optional[str] = None
    message: str


@router.post("/save", response_model=SaveResumeResponse)
async def save_resume(request: SaveResumeRequest = Body(...)):
    """
    Generate PDF from HTML and save as attachment to Zoho candidate record.

    Flow:
    1. Generate PDF from HTML using Playwright
    2. Upload PDF to Zoho Candidates module
    3. Return success confirmation

    This is called AFTER user has reviewed and optionally edited the preview.
    """
    zoho_service = ZohoService()
    pdf_generator = PDFGenerator()

    try:
        # Step 1: Generate PDF from HTML
        pdf_bytes = await pdf_generator.generate_pdf(request.html_content)

        # Step 2: Upload to Zoho
        filename = request.filename or f"Resume_{request.candidate_id}.pdf"
        attachment_id = await zoho_service.upload_resume_pdf(
            candidate_id=request.candidate_id,
            pdf_bytes=pdf_bytes,
            filename=filename
        )

        return SaveResumeResponse(
            success=True,
            candidate_id=request.candidate_id,
            attachment_id=attachment_id,
            message=f"Resume saved successfully as {filename}"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save resume: {str(e)}"
        )


@router.post("/save-direct/{candidate_id}", response_model=SaveResumeResponse)
async def save_resume_direct(candidate_id: str, background_tasks: BackgroundTasks):
    """
    Generate and save resume directly without preview.

    This is a convenience endpoint for automated workflows where
    user doesn't need to review the generated resume.

    Flow:
    1. Fetch candidate from Zoho (15%)
    2. Download LinkedIn PDF (30%)
    3. Extract data with GPT-5 (50%)
    4. Generate executive summary (65%)
    5. Render HTML template (75%)
    6. Convert to PDF (85%)
    7. Upload to Zoho (100%)
    """
    from app.api.generate import generate_resume

    zoho_service = ZohoService()
    pdf_generator = PDFGenerator()

    try:
        # Initialize progress
        progress_tracker.update(candidate_id, "starting", "🚀 Starting resume generation...", 5)

        # Step 1: Fetch candidate (happens in generate_resume)
        progress_tracker.update(candidate_id, "fetching", "📋 Fetching candidate data from Zoho...", 15)

        # Step 2-5: Generate resume (internal progress tracked)
        progress_tracker.update(candidate_id, "processing", "🤖 Processing LinkedIn profile with AI...", 40)
        result = await generate_resume(candidate_id)

        progress_tracker.update(candidate_id, "summary", "✨ Generating executive summary...", 65)

        # Step 6: Convert to PDF
        progress_tracker.update(candidate_id, "pdf", "📄 Converting to branded PDF...", 80)
        pdf_bytes = await pdf_generator.generate_pdf(result.html_preview)

        # Step 7: Upload to Zoho
        progress_tracker.update(candidate_id, "uploading", "☁️ Uploading to Zoho CRM...", 90)
        filename = f"Resume_{candidate_id}.pdf"
        attachment_id = await zoho_service.upload_resume_pdf(
            candidate_id=candidate_id,
            pdf_bytes=pdf_bytes,
            filename=filename
        )

        # Complete
        progress_tracker.complete(candidate_id, success=True)

        # Schedule cleanup in background
        background_tasks.add_task(progress_tracker.cleanup_old)

        return SaveResumeResponse(
            success=True,
            candidate_id=candidate_id,
            attachment_id=attachment_id,
            message=f"✅ Resume generated successfully! PDF attached to candidate record."
        )

    except HTTPException:
        progress_tracker.complete(candidate_id, success=False, error="API error")
        raise
    except Exception as e:
        error_msg = str(e)
        progress_tracker.complete(candidate_id, success=False, error=error_msg)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate and save resume: {error_msg}"
        )
