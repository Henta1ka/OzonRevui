"""OpenAI API integration service for draft generation"""
import logging
import asyncio
from typing import Optional, List, Dict, Any
from openai import AsyncOpenAI, APIError, RateLimitError
try:  # Optional: older versions may not expose AuthenticationError
    from openai import AuthenticationError
except Exception:  # pragma: no cover
    AuthenticationError = Exception
from app.config import settings

logger = logging.getLogger(__name__)


class AIService:
    """Service for generating response drafts using OpenAI with model selection and graceful fallback"""
    
    # Supported models
    AVAILABLE_MODELS = ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"]
    
    # Token costs for rate limiting detection (roughly)
    MODEL_COSTS = {
        "gpt-3.5-turbo": 0.5,   # Input: 0.0005, Output: 0.0015
        "gpt-4": 3.0,            # Input: 0.03, Output: 0.06
        "gpt-4-turbo": 1.0,      # Input: 0.01, Output: 0.03
    }
    
    SENTIMENT_PROMPT = """Analyze the sentiment of this review and respond with ONLY one word: positive, neutral, or negative.
Review: {review_text}"""
    
    CATEGORY_PROMPT = """Categorize this review's main issue. Respond with ONLY one category: quality, delivery, packaging, service, other.
Review: {review_text}"""
    
    RESPONSE_PROMPT = """Generate a helpful response to this customer review for a marketplace seller.
Requirements:
- Be respectful and empathetic
- Keep it concise (2-3 sentences max)
- Don't ask for personal information
- Don't argue or make excuses
- Tone: {tone}
- Include signature if provided

Review: {review_text}
Signature: {signature}

Response draft #{variant}:"""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_model
        self.client = AsyncOpenAI(api_key=self.api_key) if self._has_key() else None
        self.quota_exceeded = False  # Track quota state

    def _has_key(self) -> bool:
        """Check if API key is configured (not placeholder)"""
        if not self.api_key:
            return False
        placeholder_prefixes = ["your_", "sk-PLACEHOLDER", "sk-XXXX"]
        return not any(self.api_key.lower().startswith(pref) for pref in placeholder_prefixes)
    
    def set_model(self, model: str) -> bool:
        """Change the model to use"""
        if model not in self.AVAILABLE_MODELS:
            logger.warning(f"Model {model} not in available models. Using {self.model}")
            return False
        self.model = model
        logger.info(f"Model changed to {model}")
        return True
    
    async def check_api_health(self) -> Dict[str, Any]:
        """
        Check OpenAI API health, available models, and quota status
        
        Returns:
            {
                "available": bool,
                "api_key_set": bool,
                "current_model": str,
                "supported_models": List[str],
                "quota_exceeded": bool,
                "error": Optional[str],
                "model_available": bool,
                "latency_ms": Optional[int],
                "fallback_mode": bool
            }
        """
        result = {
            "available": False,
            "api_key_set": self._has_key(),
            "current_model": self.model,
            "supported_models": self.AVAILABLE_MODELS,
            "quota_exceeded": self.quota_exceeded,
            "error": None,
            "model_available": False,
            "latency_ms": None,
            "fallback_mode": False
        }
        
        if not self._has_key():
            result["error"] = "OpenAI API key not configured"
            result["fallback_mode"] = True
            return result
        
        try:
            # Try a minimal API call to check connectivity
            start = asyncio.get_event_loop().time()
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": "healthcheck"}],
                    max_tokens=1,
                    temperature=0
                ),
                timeout=settings.ai_timeout
            )
            end = asyncio.get_event_loop().time()
            result["latency_ms"] = int((end - start) * 1000)
            result["available"] = True
            result["model_available"] = True
            logger.info(f"OpenAI API health check passed for model {self.model}")
            
        except AuthenticationError as e:
            result["error"] = "Invalid API key"
            result["fallback_mode"] = True
            logger.error(f"OpenAI auth error: {e}")

        except RateLimitError as e:
            # API quota exceeded or rate limited
            self.quota_exceeded = True
            result["quota_exceeded"] = True
            result["error"] = f"Rate limit or quota exceeded: {str(e)}"
            result["fallback_mode"] = True
            logger.error(f"OpenAI quota exceeded: {e}")
            
        except APIError as e:
            if "insufficient_quota" in str(e).lower():
                self.quota_exceeded = True
                result["quota_exceeded"] = True
            result["error"] = str(e)
            result["fallback_mode"] = True
            logger.error(f"OpenAI API error: {e}")
            
        except asyncio.TimeoutError:
            result["error"] = f"API timeout after {settings.ai_timeout}s"
            result["fallback_mode"] = True
            logger.error(f"OpenAI API timeout")
            
        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"
            result["fallback_mode"] = True
            logger.error(f"Unexpected error checking OpenAI: {e}")
        
        return result
    
    async def analyze_sentiment(self, review_text: str, retry_count: int = 0) -> Optional[str]:
        """Analyze review sentiment with graceful fallback"""
        try:
            if not self._has_key() or not settings.ai_enabled:
                return None
            
            if self.quota_exceeded:
                logger.debug("Quota exceeded; skipping sentiment analysis")
                return None
                
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": self.SENTIMENT_PROMPT.format(review_text=review_text)
                        }
                    ],
                    max_tokens=10,
                    temperature=0
                ),
                timeout=settings.ai_timeout
            )
            return response.choices[0].message.content.strip().lower()
            
        except RateLimitError:
            self.quota_exceeded = True
            logger.warning("OpenAI quota exceeded; disabling AI features")
            return None
            
        except APIError as e:
            if "insufficient_quota" in str(e).lower():
                self.quota_exceeded = True
            logger.error(f"Error analyzing sentiment: {e}")
            return None
            
        except asyncio.TimeoutError:
            logger.warning(f"Sentiment analysis timeout ({settings.ai_timeout}s)")
            return None
            
        except Exception as e:
            logger.error(f"Unexpected error in sentiment analysis: {e}")
            return None
    
    async def categorize_review(self, review_text: str) -> Optional[str]:
        """Categorize review with graceful fallback"""
        try:
            if not self._has_key() or not settings.ai_enabled:
                return None
            
            if self.quota_exceeded:
                logger.debug("Quota exceeded; skipping categorization")
                return None
            
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": self.CATEGORY_PROMPT.format(review_text=review_text)
                        }
                    ],
                    max_tokens=10,
                    temperature=0
                ),
                timeout=settings.ai_timeout
            )
            return response.choices[0].message.content.strip().lower()
            
        except RateLimitError:
            self.quota_exceeded = True
            logger.warning("OpenAI quota exceeded; disabling AI features")
            return None
            
        except APIError as e:
            if "insufficient_quota" in str(e).lower():
                self.quota_exceeded = True
            logger.error(f"Error categorizing review: {e}")
            return None
            
        except asyncio.TimeoutError:
            logger.warning(f"Categorization timeout ({settings.ai_timeout}s)")
            return None
            
        except Exception as e:
            logger.error(f"Unexpected error in categorization: {e}")
            return None
    
    async def generate_response_drafts(
        self,
        review_text: str,
        num_variants: int = 3,
        tone: Optional[str] = None,
        signature: Optional[str] = None
    ) -> List[str]:
        """
        Generate response drafts with graceful fallback on quota exceeded
        
        Returns empty list if API unavailable, list of drafts if available
        """
        if not self._has_key() or not settings.ai_enabled:
            return []
        
        if self.quota_exceeded:
            logger.debug("Quota exceeded; skipping draft generation")
            return []
        
        tone = tone or settings.response_tone
        signature = signature or settings.response_signature
        
        drafts = []
        
        for variant in range(1, min(num_variants + 1, 4)):
            try:
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {
                                "role": "user",
                                "content": self.RESPONSE_PROMPT.format(
                                    review_text=review_text,
                                    tone=tone,
                                    signature=signature,
                                    variant=variant
                                )
                            }
                        ],
                        max_tokens=300,
                        temperature=0.7
                    ),
                    timeout=settings.ai_timeout
                )
                draft = response.choices[0].message.content.strip()
                drafts.append(draft)
                
            except RateLimitError:
                self.quota_exceeded = True
                logger.warning(f"OpenAI quota exceeded at draft variant {variant}")
                break
                
            except APIError as e:
                if "insufficient_quota" in str(e).lower():
                    self.quota_exceeded = True
                    logger.warning(f"OpenAI quota exceeded at draft variant {variant}")
                    break
                logger.error(f"Error generating draft variant {variant}: {e}")
                continue
                
            except asyncio.TimeoutError:
                logger.warning(f"Draft generation timeout at variant {variant}")
                continue
                
            except Exception as e:
                logger.error(f"Unexpected error generating draft variant {variant}: {e}")
                continue
        
        return drafts
    
    def validate_api_key(self) -> bool:
        """Check if API key is set"""
        return self._has_key()
