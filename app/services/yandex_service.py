"""YandexGPT API integration service for draft generation"""
import logging
import asyncio
import httpx
from typing import Optional, List, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)


class YandexGPTService:
    """Service for generating response drafts using YandexGPT"""
    
    AVAILABLE_MODELS = ["yandexgpt-3", "yandexgpt-3-lite", "yandexgpt-4"]
    API_URL = "https://llm.api.cloud.yandex.net/llm/v1/completions"
    
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

    def _has_credentials(self) -> bool:
        """Check if credentials are configured"""
        if not self.api_key or not self.folder_id:
            return False
        placeholder_prefixes = ["your_", "AQV", "aqv"]
        return not any(self.api_key.lower().startswith(pref) for pref in placeholder_prefixes)
    
    def set_model(self, model: str) -> bool:
        """Change the model to use"""
        if model not in self.AVAILABLE_MODELS:
            logger.warning(f"Model {model} not in available models. Using {self.model}")
            return False
        self.model = model
        logger.info(f"YandexGPT model changed to {model}")
        return True
    
    async def check_api_health(self) -> Dict[str, Any]:
        """Check YandexGPT API health"""
        if not self._has_credentials():
            return {
                "available": False,
                "credentials_set": False,
                "error": "YandexGPT credentials not configured"
            }
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    self.API_URL,
                    headers={
                        "Authorization": f"Api-Key {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model_uri": f"gpt://{self.folder_id}/{self.model}",
                        "completion_options": {"stream": False, "temperature": 0.3, "max_tokens": 50},
                        "messages": [{"role": "user", "content": "test"}]
                    }
                )
                
                if response.status_code == 200:
                    logger.info("✅ YandexGPT API is healthy")
                    return {
                        "available": True,
                        "credentials_set": True,
                        "model": self.model,
                        "quota_exceeded": False
                    }
                else:
                    logger.warning(f"YandexGPT API error: {response.status_code}")
                    return {
                        "available": False,
                        "credentials_set": True,
                        "error": f"API error: {response.status_code}",
                        "quota_exceeded": response.status_code == 429
                    }
        except Exception as e:
            logger.error(f"YandexGPT health check failed: {e}")
            return {
                "available": False,
                "credentials_set": True,
                "error": str(e)
            }
    
    async def _call_api(self, prompt: str, temperature: float = 0.7) -> Optional[str]:
        """Make a call to YandexGPT API"""
        if not self._has_credentials():
            logger.error("YandexGPT credentials not set")
            return None
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.API_URL,
                    headers={
                        "Authorization": f"Api-Key {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model_uri": f"gpt://{self.folder_id}/{self.model}",
                        "completion_options": {
                            "stream": False,
                            "temperature": temperature,
                            "max_tokens": 200
                        },
                        "messages": [{"role": "user", "content": prompt}]
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    result = data.get("result", {})
                    choices = result.get("alternatives", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "").strip()
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
