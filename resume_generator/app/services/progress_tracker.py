"""
Simple in-memory progress tracker for resume generation.
Stores progress updates that can be polled by the Deluge function.
"""
from typing import Dict, Optional
from datetime import datetime, timedelta
import asyncio

class ProgressTracker:
    def __init__(self):
        self._progress: Dict[str, dict] = {}
        self._cleanup_interval = 300  # 5 minutes
    
    def update(self, candidate_id: str, step: str, message: str, progress: int):
        """
        Update progress for a candidate resume generation.
        
        Args:
            candidate_id: Zoho candidate ID
            step: Current step name
            message: User-friendly message
            progress: Percentage complete (0-100)
        """
        self._progress[candidate_id] = {
            "step": step,
            "message": message,
            "progress": progress,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "in_progress" if progress < 100 else "completed"
        }
    
    def get(self, candidate_id: str) -> Optional[dict]:
        """Get current progress for a candidate."""
        return self._progress.get(candidate_id)
    
    def complete(self, candidate_id: str, success: bool = True, error: str = None):
        """Mark generation as complete."""
        if candidate_id in self._progress:
            self._progress[candidate_id].update({
                "progress": 100,
                "status": "completed" if success else "failed",
                "message": "Resume generated successfully!" if success else f"Error: {error}",
                "timestamp": datetime.utcnow().isoformat()
            })
    
    def cleanup_old(self):
        """Remove progress entries older than cleanup interval."""
        cutoff = datetime.utcnow() - timedelta(seconds=self._cleanup_interval)
        self._progress = {
            k: v for k, v in self._progress.items()
            if datetime.fromisoformat(v["timestamp"]) > cutoff
        }

# Global instance
progress_tracker = ProgressTracker()
