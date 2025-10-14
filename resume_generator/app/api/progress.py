from fastapi import APIRouter, HTTPException
from typing import Optional
from pydantic import BaseModel

from app.services.progress_tracker import progress_tracker

router = APIRouter()


class ProgressResponse(BaseModel):
    candidate_id: str
    step: Optional[str] = None
    message: str
    progress: int
    status: str
    timestamp: str


@router.get("/progress/{candidate_id}", response_model=ProgressResponse)
async def get_progress(candidate_id: str):
    """
    Get current progress for resume generation.
    
    This endpoint can be polled by the Deluge function to show
    real-time progress to the user.
    """
    progress = progress_tracker.get(candidate_id)
    
    if not progress:
        raise HTTPException(
            status_code=404,
            detail="No resume generation in progress for this candidate"
        )
    
    return ProgressResponse(
        candidate_id=candidate_id,
        **progress
    )
