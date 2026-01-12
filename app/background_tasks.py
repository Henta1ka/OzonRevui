"""Background tasks for periodic review fetching"""
import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import SessionLocal
from app.services.ozon_service import OzonService
from app.services.review_service import ReviewService
from app.config import settings

logger = logging.getLogger(__name__)


class ReviewPoller:
    """Handles periodic fetching of reviews from Ozon"""
    
    def __init__(self):
        self.ozon_service = OzonService()
        self.scheduler = AsyncIOScheduler()
    
    async def poll_reviews(self):
        """Fetch and process new reviews from Ozon"""
        logger.info("Starting review polling...")
        
        if not self.ozon_service.validate_credentials():
            logger.error("Ozon API credentials not configured")
            return
        
        db = SessionLocal()
        try:
            service = ReviewService(db)
            
            # Fetch reviews from Ozon
            result = await self.ozon_service.get_reviews(limit=100, offset=0)
            
            if not result:
                logger.warning("Failed to fetch reviews from Ozon")
                return
            
            # Process each review (Ozon sometimes nests the list under result.reviews)
            reviews = result.get("reviews", [])
            if not reviews and isinstance(result, dict):
                nested = result.get("result")
                if isinstance(nested, dict):
                    reviews = nested.get("reviews", [])
            
            logger.info(f"Processing {len(reviews)} new reviews")
            
            for review_data in reviews:
                await service.process_new_review(review_data)
            
            logger.info(f"Successfully processed {len(reviews)} reviews")
            
        except Exception as e:
            logger.error(f"Error during review polling: {e}", exc_info=True)
        finally:
            db.close()
    
    def start(self):
        """Start the scheduler"""
        interval_minutes = settings.polling_interval_minutes
        
        self.scheduler.add_job(
            self.poll_reviews,
            "interval",
            minutes=interval_minutes,
            id="poll_reviews",
            name="Poll Ozon for new reviews",
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info(f"Review polling scheduled every {interval_minutes} minutes")

    def reschedule(self, minutes: int):
        """Update polling interval at runtime"""
        try:
            job = self.scheduler.get_job('poll_reviews')
            if job:
                job.reschedule(trigger='interval', minutes=minutes)
                logger.info(f"Review polling rescheduled to every {minutes} minutes")
            else:
                # If no job yet, start one
                self.scheduler.add_job(
                    self.poll_reviews,
                    "interval",
                    minutes=minutes,
                    id="poll_reviews",
                    name="Poll Ozon for new reviews",
                    replace_existing=True
                )
                logger.info(f"Review polling scheduled (late) every {minutes} minutes")
        except Exception as e:
            logger.error(f"Failed to reschedule polling: {e}")
    
    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        logger.info("Review polling stopped")


# Global poller instance
poller = ReviewPoller()


async def start_background_tasks():
    """Start background tasks"""
    poller.start()
    # Do an immediate fetch so the dashboard is not empty on first load
    await poller.poll_reviews()


async def shutdown_background_tasks():
    """Stop background tasks"""
    poller.stop()
