"""Business logic service for review management"""
import logging
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.review import Review
from app.models.response import Response, ResponseDraft
from app.services.ai_service import AIService
from app.services.ozon_service import OzonService
from app.services.auto_response_service import AutoResponseService
from app.config import settings

logger = logging.getLogger(__name__)


class ReviewService:
    """Service for managing reviews and responses"""
    
    def __init__(self, db: Session):
        self.db = db
        self.ai_service = AIService()
        self.ozon_service = OzonService()
    
    async def process_new_review(self, review_data: dict) -> Optional[Review]:
        """
        Process a new review: save to DB and generate drafts
        
        Args:
            review_data: Review data from Ozon API
            
        Returns:
            Created Review object or None if failed
        """
        try:
            # Check if review already exists
            existing = self.db.query(Review).filter(
                Review.ozon_review_id == review_data.get("id")
            ).first()
            if existing:
                return existing
            
            # Analyze sentiment and category
            review_text = review_data.get("text") or review_data.get("comment") or review_data.get("content") or ""
            sentiment = await self.ai_service.analyze_sentiment(review_text)
            category = await self.ai_service.categorize_review(review_text)

            # Detect already answered on marketplace to avoid double replies
            status_raw = (review_data.get("status") or "").lower()
            comments_amount = review_data.get("comments_amount") or review_data.get("answers_amount") or review_data.get("comments") or 0
            answered_flag = bool(comments_amount and comments_amount > 0 or status_raw in {"processed", "answered", "commented"})
            
            # Create review record
            review = Review(
                ozon_review_id=review_data.get("id"),
                product_id=review_data.get("product_id") or review_data.get("sku"),
                product_name=review_data.get("product_name") or review_data.get("sku_name") or review_data.get("title"),
                customer_name=review_data.get("customer_name") or review_data.get("author") or "Anonymous",
                rating=review_data.get("rating", 0),
                text=review_text,
                sentiment=sentiment,
                category=category,
                answered=answered_flag
            )
            
            self.db.add(review)
            self.db.commit()
            self.db.refresh(review)

            # If already answered on marketplace, skip auto-generation
            if answered_flag:
                return review

            # Auto-generate single draft (configurable)
            start_variant = 1
            if settings.auto_response_enabled:
                auto_service = AutoResponseService()
                auto_result = await auto_service.generate_response(review_text)
                ai_text = None
                if isinstance(auto_result, dict):
                    ai_text = auto_result.get('response') or auto_result.get('text') or auto_result.get('response_text')
                if ai_text:
                    draft = ResponseDraft(
                        review_id=review.id,
                        text=ai_text,
                        variant_number=1
                    )
                    self.db.add(draft)
                    self.db.commit()
                    start_variant = 2
            
            # Generate additional response drafts
            await self.generate_response_drafts(review.id, review_text, start_variant=start_variant)
            
            return review
            
        except Exception as e:
            logger.error(f"Error processing review: {e}")
            self.db.rollback()
            return None
    
    async def generate_response_drafts(
        self,
        review_id: int,
        review_text: str,
        num_variants: int = 3,
        start_variant: int = 1
    ) -> List[ResponseDraft]:
        """Generate response draft variants for a review"""
        try:
            drafts_text = await self.ai_service.generate_response_drafts(
                review_text,
                num_variants=num_variants
            )
            
            drafts = []
            for idx, draft_text in enumerate(drafts_text, 1):
                draft = ResponseDraft(
                    review_id=review_id,
                    text=draft_text,
                    variant_number=start_variant + idx - 1
                )
                self.db.add(draft)
                drafts.append(draft)
            
            self.db.commit()
            return drafts
            
        except Exception as e:
            logger.error(f"Error generating drafts: {e}")
            self.db.rollback()
            return []
    
    async def submit_response(
        self,
        review_id: int,
        response_text: str,
        draft_id: Optional[int] = None
    ) -> Optional[Response]:
        """
        Submit a response to Ozon
        
        Args:
            review_id: Review ID in our database
            response_text: Text to send
            draft_id: Optional draft ID if edited from draft
            
        Returns:
            Response object or None if failed
        """
        try:
            review = self.db.query(Review).filter(Review.id == review_id).first()
            if not review:
                logger.error(f"Review {review_id} not found")
                return None

            # Prevent double responses if already marked answered
            if review.answered:
                logger.warning(f"Review {review_id} already answered; skipping send")
                return None

            # Ensure we have marketplace review id to send response
            if not review.ozon_review_id:
                logger.error(f"Review {review_id} has no ozon_review_id; cannot send")
                return None
            
            # Send to Ozon
            result = await self.ozon_service.send_response(
                review.ozon_review_id,
                response_text
            )
            
            # Create response record
            response = Response(
                review_id=review_id,
                draft_id=draft_id,
                text=response_text,
                status="sent" if result else "failed",
                error_message=None if result else "Failed to send to Ozon"
            )
            
            if result and "id" in result:
                response.ozon_response_id = result["id"]
            
            self.db.add(response)
            review.answered = True
            self.db.commit()
            self.db.refresh(response)
            
            return response
            
        except Exception as e:
            logger.error(f"Error submitting response: {e}")
            self.db.rollback()
            return None
    
    def get_unanswered_reviews(self, limit: int = 50) -> List[Review]:
        """Get list of unanswered reviews"""
        return self.db.query(Review).filter(
            Review.answered == False
        ).order_by(Review.created_at.desc()).limit(limit).all()
    
    def get_review_with_drafts(self, review_id: int) -> Optional[Review]:
        """Get review with all its response drafts"""
        return self.db.query(Review).filter(Review.id == review_id).first()
