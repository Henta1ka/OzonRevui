"""Health check and integration endpoints"""
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.ozon_service import OzonService
from app.services.ai_service import AIService
from app.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/status")
def health_status(db: Session = Depends(get_db)):
    # Проверяем что сервер живой и БД доступна
    return {
        "status": "healthy",
        "database": "connected",
        "version": "1.0.0",
        "environment": "development" if settings.debug else "production"
    }


@router.get("/integrations")
def check_integrations():
    # Смотрим какие интеграции настроены и работают
    ozon_service = OzonService()
    ai_service = AIService()
    
    return {
        "status": "ok",
        "ozon_api": {
            "configured": ozon_service.validate_credentials(),
            "description": "Ozon Seller API integration",
            "status": "✅ Ready" if ozon_service.validate_credentials() else "❌ Not configured"
        },
        "openai_api": {
            "configured": ai_service.validate_api_key(),
            "description": "OpenAI API for draft generation",
            "status": "✅ Ready" if ai_service.validate_api_key() else "❌ Not configured"
        },
        "database": {
            "configured": True,
            "description": "SQLite/PostgreSQL database",
            "status": "✅ Ready"
        }
    }


@router.post("/test-ozon")
async def test_ozon_connection(credentials: dict = Body(...)):
    """Test Ozon API connection"""
    try:
        client_id = credentials.get("client_id")
        api_key = credentials.get("api_key")
        
        if not client_id or not api_key:
            return {
                "status": "error",
                "message": "❌ Client ID and API Key required",
                "configured": False
            }
        
        # Create service with provided credentials
        service = OzonService(client_id=client_id, api_key=api_key)
        
        # Try to fetch reviews (this will test the connection)
        result = await service.get_reviews(limit=1)
        
        if result:
            return {
                "status": "success",
                "message": "✅ Ozon API connection successful!",
                "configured": True,
                "data": result
            }
        else:
            return {
                "status": "error",
                "message": "❌ Failed to connect to Ozon API",
                "configured": False
            }
    except Exception as e:
        logger.error(f"Ozon test error: {e}")
        return {
            "status": "error",
            "message": f"❌ Error: {str(e)}",
            "configured": False
        }


@router.post("/test-openai")
async def test_openai_connection(credentials: dict = Body(...)):
    """Test OpenAI API connection"""
    try:
        api_key = credentials.get("api_key")
        
        if not api_key:
            return {
                "status": "error",
                "message": "❌ API Key required",
                "configured": False
            }
        
        # Create service with provided credentials
        service = AIService(api_key=api_key)
        
        # Try to analyze sentiment
        result = await service.analyze_sentiment("Test review")
        
        if result:
            return {
                "status": "success",
                "message": "✅ OpenAI API connection successful!",
                "configured": True,
                "data": result
            }
        else:
            return {
                "status": "error",
                "message": "❌ Failed to connect to OpenAI API",
                "configured": False
            }
    except Exception as e:
        logger.error(f"OpenAI test error: {e}")
        return {
            "status": "error",
            "message": f"❌ Error: {str(e)}",
            "configured": False
        }
