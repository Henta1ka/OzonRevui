"""YandexGPT API integration service for draft generation"""
import logging
import asyncio
import httpx
from typing import Optional, List, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)


class YandexGPTService:
    """Service for generating response drafts using YandexGPT"""
    
    # Yandex Cloud chat models (technical ids)
    # Docs: https://cloud.yandex.ru/docs/ai/yandexgpt/api-ref/Completion
    AVAILABLE_MODELS = [
        "yandexgpt",
        "yandexgpt-lite",
        "yandexgpt-pro"
    ]
    # REST endpoint for chat-style completion
    API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    
    SENTIMENT_PROMPT = """Проанализируй тональность отзыва и ответь ТОЛЬКО одним словом: положительная, нейтральная или отрицательная.
Отзыв: {review_text}"""
    
    CATEGORY_PROMPT = """Категоризируй основную тему отзыва. Ответь ТОЛЬКО одной категорией: качество, доставка, упаковка, сервис, другое.
Отзыв: {review_text}"""
    
    RESPONSE_PROMPT = """Сгенерируй помощный ответ продавца на отзыв клиента для маркетплейса.
Требования:
- Будь вежлив и эмпатичен
- Будь кратким (максимум 2-3 предложения)
- Не запрашивай личную информацию
- Не спорь и не делай оправдания
- Тон: {tone}
- Включи подпись если предоставлена

Отзыв: {review_text}
Подпись: {signature}

Вариант ответа #{variant}:"""
    
    def __init__(self, api_key: Optional[str] = None, folder_id: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.yandex_api_key
        self.folder_id = folder_id or settings.yandex_folder_id
        self.model = model or settings.yandex_model
        self.quota_exceeded = False
        
        # Debug logging
        logger.info(f"YandexGPT init: api_key={'SET' if self.api_key else 'EMPTY'}, folder_id={self.folder_id}, model={self.model}")

    def _has_credentials(self) -> bool:
        """Check if credentials are configured"""
        # Consider credentials set if non-empty
        has_creds = bool(self.api_key and self.folder_id)
        logger.info(f"_has_credentials check: api_key={'SET' if self.api_key else 'EMPTY'}, folder_id={self.folder_id}, result={has_creds}")
        return has_creds

    def _safe_details(self, resp: httpx.Response) -> str:
        """Return trimmed response body for diagnostics"""
        try:
            text = resp.text or ""
            if len(text) > 1500:
                text = text[:1500] + "...(truncated)"
            return text
        except Exception:
            return ""

    def _auth_hint(self, resp: httpx.Response) -> str:
        """Provide hints for 401/403"""
        body = self._safe_details(resp)
        hint = (
            "Check:\n"
            "1) Api-Key is SECRET (not key id).\n"
            "2) Header: Authorization: Api-Key <SECRET>.\n"
            "3) Model must be yandexgpt / yandexgpt-lite / yandexgpt-pro.\n"
            "4) modelUri: gpt://<folder_id>/<model>.\n"
            "5) Service account has ai.languageModels.user on the folder."
        )
        return hint + (f"\nAPI response:\n{body}" if body else "")
    
    def set_model(self, model: str) -> bool:
        """Change the model to use"""
        if model not in self.AVAILABLE_MODELS:
            logger.warning(f"Model {model} not in available models. Using {self.model}")
            return False
        self.model = model
        logger.info(f"YandexGPT model changed to {model}")
        return True
    
    async def check_api_health(self) -> Dict[str, Any]:
        """Health check using completion endpoint."""
        if not self.api_key:
            return {
                "available": False,
                "credentials_set": False,
                "model": self.model,
                "error": "Missing API key",
                "details": "Укажите секретный Api-Key (не ID ключа)"
            }
        if not self.folder_id:
            return {
                "available": False,
                "credentials_set": True,
                "model": self.model,
                "error": "Missing Folder ID",
                "details": "Укажите Folder ID (b1...)"
            }

        # Yandex requires /latest suffix on model URI
        model_uri = f"gpt://{self.folder_id}/{self.model}/latest"
        payload = {
            "modelUri": model_uri,
            "completionOptions": {
                "stream": False,
                "temperature": 0.0,
                "maxTokens": 5
            },
            "messages": [{"role": "user", "text": "ping"}]
        }

        try:
            timeout = httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self.API_URL,
                    headers={
                        "Authorization": f"Api-Key {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )

            if response.status_code == 200:
                return {
                    "available": True,
                    "credentials_set": True,
                    "model": self.model,
                    "model_uri": model_uri,
                    "quota_exceeded": False,
                    "status_code": response.status_code,
                }

            if response.status_code == 429:
                return {
                    "available": False,
                    "credentials_set": True,
                    "model": self.model,
                    "model_uri": model_uri,
                    "quota_exceeded": True,
                    "status_code": response.status_code,
                    "error": "Rate limit / quota exceeded (429)",
                    "details": self._safe_details(response),
                }

            if response.status_code in (401, 403):
                return {
                    "available": False,
                    "credentials_set": True,
                    "model": self.model,
                    "model_uri": model_uri,
                    "quota_exceeded": False,
                    "status_code": response.status_code,
                    "error": "Authentication/authorization failed (401/403)",
                    "details": self._auth_hint(response),
                }

            if response.status_code == 404:
                return {
                    "available": False,
                    "credentials_set": True,
                    "model": self.model,
                    "model_uri": model_uri,
                    "quota_exceeded": False,
                    "status_code": response.status_code,
                    "error": "Endpoint or model not found (404)",
                    "details": "Ensure URL /foundationModels/v1/completion and modelUri gpt://<folder>/<model>." + (f"\nAPI response: {self._safe_details(response)}"),
                }

            return {
                "available": False,
                "credentials_set": True,
                "model": self.model,
                "model_uri": model_uri,
                "quota_exceeded": False,
                "status_code": response.status_code,
                "error": f"API error: HTTP {response.status_code}",
                "details": self._safe_details(response),
            }

        except httpx.ConnectError as e:
            return {
                "available": False,
                "credentials_set": True,
                "model": self.model,
                "model_uri": model_uri,
                "error": "Network connect error to Yandex LLM API.",
                "details": str(e),
            }
        except httpx.ReadTimeout as e:
            return {
                "available": False,
                "credentials_set": True,
                "model": self.model,
                "model_uri": model_uri,
                "error": "Timeout while calling Yandex LLM API.",
                "details": str(e),
            }
        except Exception as e:
            return {
                "available": False,
                "credentials_set": True,
                "model": self.model,
                "model_uri": model_uri,
                "error": "Unexpected error while checking YandexGPT.",
                "details": str(e),
            }
    
    async def _call_api(self, prompt: str, temperature: float = 0.7) -> Optional[str]:
        """Make a call to YandexGPT chat API"""
        if not self._has_credentials():
            logger.error("YandexGPT credentials not set")
            return None
        
        payload = {
            "modelUri": f"gpt://{self.folder_id}/{self.model}/latest",
            "completionOptions": {
                "stream": False,
                "temperature": temperature,
                "maxTokens": 200
            },
            "messages": [{"role": "user", "text": prompt}]
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.API_URL,
                    headers={
                        "Authorization": f"Api-Key {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    result = data.get("result", {})
                    choices = result.get("alternatives", [])
                    if choices:
                        return choices[0].get("message", {}).get("text", "").strip()
                elif response.status_code == 429:
                    self.quota_exceeded = True
                    logger.error("YandexGPT quota exceeded")
                    return None
                else:
                    logger.warning(f"YandexGPT API error: {response.status_code} - {response.text}")
                    return None
        except asyncio.TimeoutError:
            logger.error("YandexGPT API timeout")
            return None
        except Exception as e:
            logger.error(f"YandexGPT API call failed: {e}")
            return None
    
    async def analyze_sentiment(self, review_text: str) -> str:
        """Analyze sentiment of a review"""
        if self.quota_exceeded or not self._has_credentials():
            return "neutral"
        
        prompt = self.SENTIMENT_PROMPT.format(review_text=review_text)
        result = await self._call_api(prompt, temperature=0.1)
        
        if result:
            sentiment = result.lower()
            for word in ["положительная", "positive", "хорошо", "good"]:
                if word in sentiment:
                    return "positive"
            for word in ["отрицательная", "negative", "плохо", "bad"]:
                if word in sentiment:
                    return "negative"
        
        return "neutral"
    
    async def categorize_review(self, review_text: str) -> str:
        """Categorize the main topic of a review"""
        if self.quota_exceeded or not self._has_credentials():
            return "other"
        
        prompt = self.CATEGORY_PROMPT.format(review_text=review_text)
        result = await self._call_api(prompt, temperature=0.1)
        
        if result:
            category = result.lower()
            categories = {
                "качество": "quality",
                "quality": "quality",
                "доставка": "delivery",
                "delivery": "delivery",
                "упаковка": "packaging",
                "packaging": "packaging",
                "сервис": "service",
                "service": "service"
            }
            for key, val in categories.items():
                if key in category:
                    return val
        
        return "other"
    
    async def generate_response_drafts(
        self,
        review_text: str,
        num_variants: int = 3,
        tone: Optional[str] = None,
        signature: Optional[str] = None,
        custom_prompt: Optional[str] = None
    ) -> List[str]:
        """Generate response draft variants"""
        if self.quota_exceeded or not self._has_credentials():
            logger.warning("YandexGPT not available for draft generation")
            return []
        
        tone = tone or settings.response_tone
        signature = signature or settings.response_signature
        
        drafts = []
        for variant in range(1, num_variants + 1):
            if custom_prompt:
                # Use custom prompt if provided
                prompt = custom_prompt.format(
                    review_text=review_text,
                    tone=tone,
                    signature=signature,
                    variant=variant
                )
            else:
                prompt = self.RESPONSE_PROMPT.format(
                    review_text=review_text,
                    tone=tone,
                    signature=signature,
                    variant=variant
                )
            
            result = await self._call_api(prompt, temperature=0.7)
            if result:
                drafts.append(result)
            else:
                # If API fails, add a fallback response
                drafts.append(f"Спасибо за ваш отзыв! {signature}")
        
        return drafts
