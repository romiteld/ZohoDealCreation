"""
Teams Bot Service - FastAPI application.

Handles Microsoft Teams Bot Framework webhooks and provides
REST API for bot functionality.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import Teams Bot routes
from app.api.teams.routes import router as teams_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - startup and shutdown."""
    logger.info("Teams Bot service starting up...")

    # NOTE: Database and cache connections are managed by the routes themselves
    # No need to initialize them here - they're imported from well_shared as needed

    yield

    # Cleanup
    logger.info("Teams Bot service shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Teams Bot Service",
    description="Microsoft Teams integration for Well Intake API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on environment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Teams Bot routes (router already has /api/teams prefix)
app.include_router(teams_router)


@app.get("/health")
async def health_check():
    """Health check endpoint for Azure Container Apps."""
    return {
        "status": "healthy",
        "service": "teams-bot",
        "version": "1.0.0"
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "teams-bot",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "teams_webhook": "/api/teams/webhook",
            "admin": "/api/teams/admin"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
