"""Main FastAPI application"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import os
from app.database import Base, engine
from app.background_tasks import start_background_tasks, shutdown_background_tasks
from app.api.routes import reviews, responses, settings, integrations

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="Ozon Review Service",
    description="Service for managing Ozon marketplace reviews and responses",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(reviews.router)
app.include_router(responses.router)
app.include_router(settings.router)
app.include_router(integrations.router)

# Mount static files (frontend)
frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
try:
    if os.path.exists(frontend_path):
        app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")
    else:
        logger.warning(f"Frontend directory not found at {frontend_path}")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")


@app.on_event("startup")
async def startup_event():
    """Launch background schedulers."""
    await start_background_tasks()


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up background schedulers."""
    await shutdown_background_tasks()


if __name__ == "__main__":
    import uvicorn
    from app.config import settings
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
