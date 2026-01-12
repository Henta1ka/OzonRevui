"""Ozon API integration service"""
import httpx
import logging
from typing import Optional, List, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)


class OzonService:
    """Service for interacting with Ozon Seller API"""
    
    BASE_URL = "https://api-seller.ozon.ru"
    
    def __init__(self, client_id: Optional[str] = None, api_key: Optional[str] = None):
        self.client_id = str(client_id or settings.ozon_client_id).strip()
        self.api_key = str(api_key or settings.ozon_api_key).strip()
        self.headers = {
            "Client-Id": self.client_id,
            "Api-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        logger.info(f"OzonService initialized with Client-Id: {self.client_id}")
    
    async def get_reviews(self, limit: int = 100, offset: int = 0) -> Optional[Dict[str, Any]]:
        """
        Fetch reviews from Ozon API
        
        Args:
            limit: Maximum number of reviews to fetch (20-100)
            offset: Number of reviews to skip
            
        Returns:
            List of reviews or None if error
        """
        try:
            # Ozon API requires limit between 20 and 100
            limit = max(20, min(limit, 100))
            
            # Try different endpoints for reviews
            endpoints = [
                f"{self.BASE_URL}/v1/review/list",  # v1 - correct endpoint
                f"{self.BASE_URL}/v2/review/list",  # v2 alternative
            ]
            
            payload = {
                "limit": limit,
                "offset": offset,
                "filter": {
                    "statuses": [1]
                }
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                for url in endpoints:
                    logger.info(f"Trying endpoint: {url}")
                    logger.info(f"Headers: Client-Id={self.client_id}, Api-Key={'*' * len(self.api_key)}")
                    try:
                        response = await client.post(
                            url,
                            headers=self.headers,
                            json=payload
                        )
                        
                        logger.info(f"Response status: {response.status_code}")
                        logger.info(f"Response text: {response.text[:500]}")
                        
                        if response.status_code == 200:
                            logger.info("✅ Success with " + url)
                            data = response.json()

                            # Ozon часто возвращает данные под ключом "result"
                            if isinstance(data, dict) and "reviews" not in data:
                                nested = data.get("result")
                                if isinstance(nested, dict) and "reviews" in nested:
                                    reviews = nested.get("reviews", [])
                                    total = nested.get("count") or nested.get("total")
                                    data["reviews"] = reviews
                                    if total is not None:
                                        data["total"] = total
                                    logger.info(f"Unwrapped result: {len(reviews)} reviews")

                            return data
                        elif response.status_code == 404:
                            logger.info(f"404 - Trying next endpoint...")
                            continue
                        else:
                            logger.warning(f"Status {response.status_code}: {response.text[:200]}")
                            # Don't continue on other errors, return the response
                            if response.status_code < 500:
                                logger.warning(f"Client error, stopping retry loop")
                                return None
                    except Exception as e:
                        logger.warning(f"Failed with {url}: {e}")
                        continue
                
                logger.error("All endpoints failed")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching reviews from Ozon: {e}", exc_info=True)
            return None
    
    async def send_response(self, review_id: str, text: str) -> Optional[Dict[str, Any]]:
        """
        Send response (comment) to a review
        
        Args:
            review_id: Ozon review ID
            text: Response text
            
        Returns:
            Response from Ozon API or None if error
        """
        try:
            url = f"{self.BASE_URL}/v2/review/comment/create"
            payload = {
                "review_id": review_id,
                "text": text
            }
            
            logger.info(f"Sending response to review {review_id}")
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload
                )
                
                logger.info(f"Response status: {response.status_code}")
                
                if response.status_code == 200:
                    logger.info("✅ Response sent successfully")
                    return response.json()
                else:
                    logger.warning(f"Status {response.status_code}: {response.text[:200]}")
                    return None
        except Exception as e:
            logger.error(f"Error sending response to Ozon: {e}", exc_info=True)
            return None
    
    def validate_credentials(self) -> bool:
        """Validate that API credentials are set"""
        return bool(self.client_id and self.api_key)
