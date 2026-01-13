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
        # Ozon requires Client-Id to be a numeric string
        client_id_value = client_id or settings.ozon_client_id
        try:
            # Ensure Client-Id is numeric (Ozon API requirement)
            self.client_id = str(int(str(client_id_value).strip()))
        except (ValueError, TypeError):
            self.client_id = str(client_id_value).strip()
        
        self.api_key = str(api_key or settings.ozon_api_key).strip()
        self.headers = {
            "Client-Id": self.client_id,
            "Api-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        logger.info(f"OzonService initialized with Client-Id: {self.client_id}")
    
    async def get_reviews(self, limit: int = 100, offset: int = 0, days_back: int = 30) -> Optional[Dict[str, Any]]:
        """
        Fetch reviews from Ozon API
        
        Args:
            limit: Maximum number of reviews to fetch (20-100)
            offset: Number of reviews to skip (deprecated, use days_back)
            days_back: Number of days back to fetch reviews (default 30, set to 0 for all)
            
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
            
            # Build filter with date range for fresher reviews
            filter_config = {"statuses": [1]}
            
            # If days_back is specified, add date filter
            if days_back > 0:
                from datetime import datetime, timedelta
                date_from = (datetime.utcnow() - timedelta(days=days_back)).isoformat() + "Z"
                filter_config["date_from"] = date_from
                logger.info(f"Filtering reviews from last {days_back} days (since {date_from})")
            
            payload = {
                "limit": limit,
                "offset": offset,
                "filter": filter_config
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
            Dict with ok flag, data or error info
        """
        try:
            # Try different endpoints for sending responses
            endpoints = [
                f"{self.BASE_URL}/v2/review/comment/create",
                f"{self.BASE_URL}/v1/review/comment",
                f"{self.BASE_URL}/v1/review/{review_id}/comment",
            ]
            
            payload = {
                "review_id": review_id,
                "text": text
            }
            
            logger.info(f"Sending response to review {review_id}, text length: {len(text)}")
            logger.info(f"Payload: {payload}")
            
            async with httpx.AsyncClient(timeout=30) as client:
                for url in endpoints:
                    logger.info(f"Trying endpoint: {url}")
                    try:
                        response = await client.post(
                            url,
                            headers=self.headers,
                            json=payload
                        )
                        
                        body_preview = response.text[:500]
                        logger.info(f"Response status: {response.status_code}")
                        logger.info(f"Response body: {body_preview}")
                        
                        if response.status_code == 200:
                            logger.info(f"✅ Response sent successfully via {url}")
                            return {
                                "ok": True,
                                "data": response.json()
                            }
                        elif response.status_code == 404:
                            logger.info(f"404 - {url} not found, trying next...")
                            continue
                        else:
                            logger.warning(f"Status {response.status_code} from {url}: {body_preview}")
                            # If client error and not 404, don't try other endpoints
                            if response.status_code < 500 and response.status_code != 404:
                                return {
                                    "ok": False,
                                    "status_code": response.status_code,
                                    "text": body_preview
                                }
                    except Exception as e:
                        logger.warning(f"Failed with {url}: {e}")
                        continue
                
                logger.error("All send_response endpoints failed")
                return {
                    "ok": False,
                    "error": "All endpoints returned 404 or failed"
                }
        except Exception as e:
            logger.error(f"Error sending response to Ozon: {e}", exc_info=True)
            return {
                "ok": False,
                "error": str(e)
            }
            return {
                "ok": False,
                "error": str(e)
            }
    
    def validate_credentials(self) -> bool:
        """Validate that API credentials are set"""
        return bool(self.client_id and self.api_key)
