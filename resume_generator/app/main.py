from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
import os

app = FastAPI(
    title="Well Resume Generator API",
    version="1.0.0",
    description="Automatic white-labeled resume generation for Zoho CRM candidates"
)

# Mount static files (for logo and other assets)
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "resume-generator",
        "version": "1.0.0"
    }

# Include API routers
from app.api.generate import router as generate_router
from app.api.save import router as save_router
from app.api.progress import router as progress_router

app.include_router(generate_router, prefix="/api/resume", tags=["Resume Generation"])
app.include_router(save_router, prefix="/api/resume", tags=["Resume Save"])
app.include_router(progress_router, prefix="/api/resume", tags=["Progress Tracking"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )
