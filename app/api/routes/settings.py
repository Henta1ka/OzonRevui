"""Settings endpoints"""
import logging
import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.schemas.settings import SettingsSchema
from app.models.settings import Settings
from app.services.ai_service import AIService
from app.services.auto_response_service import AutoResponseService
from app.config import settings
from openai import OpenAI, AuthenticationError, RateLimitError, APIError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["settings"])


class OzonCredentials(BaseModel):
    """Ozon API credentials payload"""
    client_id: str
    api_key: str


class OpenAICredentials(BaseModel):
    """OpenAI API credentials payload"""
    api_key: str
    model: str = "gpt-3.5-turbo"


@router.get("/{key}", response_model=SettingsSchema)
def get_setting(key: str, db: Session = Depends(get_db)):
    """Get a setting by key"""
    setting = db.query(Settings).filter(Settings.key == key).first()
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")
    return setting


@router.put("/{key}", response_model=SettingsSchema)
def update_setting(
    key: str,
    data: SettingsSchema,
    db: Session = Depends(get_db)
):
    """Update a setting"""
    setting = db.query(Settings).filter(Settings.key == key).first()
    if not setting:
        setting = Settings(key=key, value=data.value)
        db.add(setting)
    else:
        setting.value = data.value
    db.commit()
    db.refresh(setting)
    return setting


@router.get("")
def get_all_settings(db: Session = Depends(get_db)):
    """Get all settings"""
    all_settings = db.query(Settings).all()
    return {s.key: s.value for s in all_settings}


@router.get("/health/models", tags=["health"])
async def check_ai_health():
    """
    Check OpenAI API health and available models
    
    Returns:
    {
        "available": bool,
        "api_key_set": bool,
        "current_model": str,
        "supported_models": [str],
        "quota_exceeded": bool,
        "error": str or null,
        "ai_enabled": bool
    }
    """
    ai_service = AIService()
    health = await ai_service.check_api_health()
    health["ai_enabled"] = settings.ai_enabled
    return health


@router.get("/ozon/credentials")
def get_ozon_credentials():
    """Return current Ozon credentials (from environment/config)."""
    return {
        "client_id": settings.ozon_client_id,
        "api_key": settings.ozon_api_key
    }


@router.post("/ozon/credentials")
def set_ozon_credentials(payload: OzonCredentials):
    """Update Ozon credentials in runtime config and persist to .env."""
    settings.ozon_client_id = payload.client_id.strip()
    settings.ozon_api_key = payload.api_key.strip()

    env_file = ".env"
    lines = []
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

    def upsert(lines: list[str], key: str, value: str) -> list[str]:
        updated = []
        found = False
        for line in lines:
            if line.startswith(f"{key}="):
                updated.append(f"{key}={value}\n")
                found = True
            else:
                updated.append(line)
        if not found:
            updated.append(f"{key}={value}\n")
        return updated

    lines = upsert(lines, "OZON_CLIENT_ID", settings.ozon_client_id)
    lines = upsert(lines, "OZON_API_KEY", settings.ozon_api_key)

    with open(env_file, "w", encoding="utf-8") as f:
        f.writelines(lines)

    logger.info("Ozon credentials updated via API")
    return {"status": "ok"}


@router.post("/models/{model}", tags=["settings"])
def switch_model(model: str):
    """
    Switch to a different model
    
    Args:
        model: One of [gpt-3.5-turbo, gpt-4, gpt-4-turbo]
    """
    ai_service = AIService()
    if ai_service.set_model(model):
        # Update in config for persistence
        import os
        env_file = ".env"
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                lines = f.readlines()
            with open(env_file, 'w') as f:
                found = False
                for line in lines:
                    if line.startswith("OPENAI_MODEL="):
                        f.write(f"OPENAI_MODEL={model}\n")
                        found = True
                    else:
                        f.write(line)
                if not found:
                    f.write(f"OPENAI_MODEL={model}\n")
        return {"status": "ok", "model": model}
    else:
        raise HTTPException(status_code=400, detail=f"Model {model} not supported")


@router.get("/openai/credentials")
def get_openai_credentials():
    """Return current OpenAI credentials (from environment/config)."""
    return {
        "api_key": settings.openai_api_key,
        "model": settings.openai_model
    }


@router.post("/openai/credentials")
def set_openai_credentials(payload: OpenAICredentials):
    """Update OpenAI credentials in runtime config and persist to .env."""
    settings.openai_api_key = payload.api_key.strip()
    settings.openai_model = payload.model.strip()

    env_file = ".env"
    lines = []
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

    def upsert(lines: list[str], key: str, value: str) -> list[str]:
        updated = []
        found = False
        for line in lines:
            if line.startswith(f"{key}="):
                updated.append(f"{key}={value}\n")
                found = True
            else:
                updated.append(line)
        if not found:
            updated.append(f"{key}={value}\n")
        return updated

    lines = upsert(lines, "OPENAI_API_KEY", settings.openai_api_key)
    lines = upsert(lines, "OPENAI_MODEL", settings.openai_model)

    with open(env_file, "w", encoding="utf-8") as f:
        f.writelines(lines)

    logger.info("OpenAI credentials updated via API")
    return {"status": "ok"}


@router.post("/ai/toggle", tags=["settings"])
def toggle_ai(enabled: bool):
    """Enable or disable AI features"""
    settings.ai_enabled = enabled
    logger.info(f"AI features {'enabled' if enabled else 'disabled'}")
    return {"ai_enabled": enabled}


class KeyCheckRequest(BaseModel):
    """Request for checking API key"""
    api_key: str
    model: str = "gpt-3.5-turbo"


@router.post("/openai/check-key")
def check_openai_key(payload: KeyCheckRequest):
    """
    Detailed check of OpenAI API key and diagnosis of issues
    
    Returns:
    {
        "status": "success" | "auth_error" | "quota_error" | "model_error" | "unknown_error",
        "is_valid": bool,
        "message": str,
        "details": str or null,
        "model": str or null,
        "tokens_used": int or null
    }
    """
    api_key = payload.api_key.strip()
    
    if not api_key:
        return {
            "status": "auth_error",
            "is_valid": False,
            "message": "API ключ не установлен",
            "details": "Установите OPENAI_API_KEY в файле .env или введите его здесь"
        }
    
    # Check key format
    if not api_key.startswith("sk-proj-"):
        logger.warning(f"API key with non-standard format: {api_key[:20]}...")
    
    client = OpenAI(api_key=api_key)
    
    try:
        logger.info("Testing OpenAI API key...")
        response = client.chat.completions.create(
            model=payload.model,
            messages=[{'role': 'user', 'content': 'test'}],
            max_tokens=5
        )
        
        logger.info(f"✅ OpenAI API key is valid! Model: {response.model}")
        return {
            "status": "success",
            "is_valid": True,
            "message": "✅ API ключ работает!",
            "model": response.model,
            "tokens_used": response.usage.total_tokens
        }
    
    except AuthenticationError as e:
        logger.warning(f"OpenAI auth error: {str(e)}")
        return {
            "status": "auth_error",
            "is_valid": False,
            "message": "❌ Ошибка аутентификации (401)",
            "details": "Ключ неправильный, был удален или скопирован неполностью. Проверьте ключ на https://platform.openai.com/account/api-keys"
        }
    
    except RateLimitError as e:
        logger.warning(f"OpenAI rate limit error: {str(e)}")
        error_str = str(e).lower()
        if "insufficient_quota" in error_str or "quota" in error_str:
            return {
                "status": "quota_error",
                "is_valid": False,
                "message": "❌ Ошибка квоты (429)",
                "details": "На аккаунте нет денег или исчерпана квота. Пополните баланс на https://platform.openai.com/account/billing/overview"
            }
        else:
            return {
                "status": "quota_error",
                "is_valid": False,
                "message": "❌ Ошибка Rate Limit (429)",
                "details": "Слишком много запросов за короткое время. Подождите несколько минут и попробуйте снова."
            }
    
    except APIError as e:
        logger.warning(f"OpenAI API error: {str(e)}")
        error_str = str(e).lower()
        
        if "model" in error_str and "not found" in error_str:
            return {
                "status": "model_error",
                "is_valid": False,
                "message": "❌ Модель не найдена",
                "details": f"Модель '{payload.model}' недоступна для этого ключа. Попробуйте 'gpt-3.5-turbo' или 'gpt-4'."
            }
        else:
            return {
                "status": "unknown_error",
                "is_valid": False,
                "message": f"❌ Ошибка API: {type(e).__name__}",
                "details": str(e)[:200]
            }
    
    except Exception as e:
        logger.error(f"Unknown error checking OpenAI key: {str(e)}")
        return {
            "status": "unknown_error",
            "is_valid": False,
            "message": "❌ Неизвестная ошибка",
            "details": str(e)[:200]
        }


class ResponseConfig(BaseModel):
    """Response configuration"""
    tone: str
    signature: str
    polling_interval: int


@router.post("/response/config")
def set_response_config(payload: ResponseConfig):
    """Update response configuration."""
    # Update runtime config
    settings.polling_interval_minutes = payload.polling_interval
    
    env_file = ".env"
    lines = []
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

    def upsert(lines: list[str], key: str, value: str) -> list[str]:
        updated = []
        found = False
        for line in lines:
            if line.startswith(f"{key}="):
                updated.append(f"{key}={value}\n")
                found = True
            else:
                updated.append(line)
        if not found:
            updated.append(f"{key}={value}\n")
        return updated

    lines = upsert(lines, "RESPONSE_TONE", payload.tone)
    lines = upsert(lines, "RESPONSE_SIGNATURE", payload.signature)
    lines = upsert(lines, "POLLING_INTERVAL_MINUTES", str(payload.polling_interval))

    with open(env_file, "w", encoding="utf-8") as f:
        f.writelines(lines)

    logger.info(f"Response config updated: tone={payload.tone}, polling_interval={payload.polling_interval}")

    # Reschedule polling job if running
    try:
        from app.background_tasks import poller
        poller.reschedule(payload.polling_interval)
    except Exception as e:
        logger.warning(f"Could not reschedule poller: {e}")
    return {"status": "ok"}


class AutoResponseConfig(BaseModel):
    """Auto response configuration"""
    tone: str  # friendly, official, formal
    prompt_template: str
    signature: str
    auto_enabled: bool = False


@router.get("/auto-response/config")
def get_auto_response_config():
    """Get current auto response configuration."""
    return {
        "tone": getattr(settings, 'response_tone', 'friendly'),
        "prompt_template": getattr(settings, 'response_prompt', ''),
        "signature": getattr(settings, 'response_signature', ''),
        "auto_enabled": getattr(settings, 'auto_response_enabled', False)
    }


@router.post("/auto-response/config")
def set_auto_response_config(payload: AutoResponseConfig):
    """Update auto response configuration."""
    # Update runtime config
    settings.response_tone = payload.tone
    settings.response_prompt = payload.prompt_template
    settings.response_signature = payload.signature
    settings.auto_response_enabled = payload.auto_enabled
    
    # Persist to .env
    env_file = ".env"
    lines = []
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

    def upsert(lines: list[str], key: str, value: str) -> list[str]:
        updated = []
        found = False
        for line in lines:
            if line.startswith(f"{key}="):
                # For multiline values, we'll encode them
                updated.append(f"{key}={value}\n")
                found = True
            else:
                updated.append(line)
        if not found:
            updated.append(f"{key}={value}\n")
        return updated

    lines = upsert(lines, "RESPONSE_TONE", payload.tone)
    lines = upsert(lines, "RESPONSE_PROMPT", payload.prompt_template)
    lines = upsert(lines, "RESPONSE_SIGNATURE", payload.signature)
    lines = upsert(lines, "AUTO_RESPONSE_ENABLED", str(payload.auto_enabled))

    with open(env_file, "w", encoding="utf-8") as f:
        f.writelines(lines)

    logger.info(f"Auto response config updated: tone={payload.tone}")
    return {"status": "ok"}


class TestAutoResponseRequest(BaseModel):
    """Test auto response request"""
    review_text: str
    tone: str = None
    prompt_template: str = None
    signature: str = None


@router.post("/auto-response/test")
async def test_auto_response(payload: TestAutoResponseRequest):
    """
    Test auto response generation
    
    Returns:
    {
        "text": str,
        "is_generated": bool,
        "mode": "ai" | "fallback",
        "error": str or null
    }
    """
    if not payload.review_text or len(payload.review_text.strip()) < 3:
        raise HTTPException(status_code=400, detail="Review text too short")
    
    service = AutoResponseService()
    result = await service.generate_response(
        review_text=payload.review_text,
        tone=payload.tone,
        prompt_template=payload.prompt_template,
        signature=payload.signature
    )
    
    return result
