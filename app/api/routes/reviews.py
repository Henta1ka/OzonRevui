"""Review endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from typing import List, Optional
from app.database import get_db
from app.schemas.review import ReviewSchema, ReviewDetail
from app.models.review import Review
from app.services.ozon_service import OzonService
from app.services.review_service import ReviewService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.get("", response_model=List[ReviewSchema])
def get_reviews(
    limit: int = 50,
    offset: int = 0,
    answered: Optional[bool] = None,
    sort: str = "new",
    db: Session = Depends(get_db)
):
    """Get list of reviews with answered filter and sorting."""
    query = db.query(Review)

    if answered is not None:
        query = query.filter(Review.answered == answered)

    # Sorting: "new" (default) -> newest first, "old" -> oldest first
    if sort == "old":
        query = query.order_by(Review.created_at.asc())
    else:
        query = query.order_by(Review.created_at.desc())

    reviews = query.offset(offset).limit(limit).all()
    return reviews


@router.get("/unanswered/list")
def get_unanswered_reviews(limit: int = 50, db: Session = Depends(get_db)):
    """Get list of unanswered reviews"""
    reviews = db.query(Review).filter(
        Review.answered == False
    ).order_by(Review.created_at.desc()).limit(limit).all()
    return [ReviewSchema.from_orm(r) for r in reviews]


@router.get("/stats")
def get_review_stats(db: Session = Depends(get_db)):
    """Return aggregated review statistics from DB."""
    total_reviews = db.query(func.count(Review.id)).scalar() or 0
    unanswered = db.query(func.count(Review.id)).filter(Review.answered == False).scalar() or 0
    avg_rating = db.query(func.avg(Review.rating)).scalar()

    products_count = db.query(func.count(func.distinct(Review.product_id))).scalar() or 0
    # If product_id is missing, fall back to product_name
    if products_count == 0:
        products_count = db.query(func.count(func.distinct(Review.product_name))).scalar() or 0
    # As a last resort, count distinct review IDs
    if products_count == 0:
        products_count = db.query(func.count(func.distinct(Review.ozon_review_id))).scalar() or 0

    return {
        "total_reviews": total_reviews,
        "unanswered": unanswered,
        "avg_rating": round(avg_rating, 1) if avg_rating is not None else 0,
        "products": products_count or 0
    }


@router.get("/products")
def get_products_summary(limit: int = 50, db: Session = Depends(get_db)):
    """Return aggregated stats per product (top N by review count)."""
    rows = (
        db.query(
            Review.product_id.label("product_id"),
            Review.product_name.label("product_name"),
            func.count(Review.id).label("reviews_count"),
            func.sum(case((Review.answered == False, 1), else_=0)).label("unanswered_count"),
            func.avg(Review.rating).label("avg_rating"),
        )
        .group_by(Review.product_id, Review.product_name)
        .order_by(func.count(Review.id).desc())
        .limit(limit)
        .all()
    )

    products = []
    for row in rows:
        pid = row.product_id or ""
        name = row.product_name or (f"Товар {str(pid)[:8]}" if pid else "Товар")
        products.append(
            {
                "sku": pid,
                "name": name,
                "reviews": row.reviews_count or 0,
                "unanswered": row.unanswered_count or 0,
                "avg_rating": round(row.avg_rating, 1) if row.avg_rating is not None else 0,
            }
        )

    return products


@router.post("/sync")
async def sync_reviews(db: Session = Depends(get_db)):
    """Fetch latest reviews from Ozon and store them locally."""
    ozon_service = OzonService()
    if not ozon_service.validate_credentials():
        raise HTTPException(status_code=400, detail="Ozon API credentials are not configured")

    service = ReviewService(db)

    try:
        result = await ozon_service.get_reviews(limit=100, offset=0)
    except Exception as exc:
        logger.error("Failed to fetch reviews from Ozon", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Ozon API error: {exc}")

    if not result:
        raise HTTPException(status_code=502, detail="Empty response from Ozon API")

    reviews = result.get("reviews", [])
    if not reviews and isinstance(result, dict):
        nested = result.get("result")
        if isinstance(nested, dict):
            reviews = nested.get("reviews", [])

    processed = 0
    for review_data in reviews:
        saved = await service.process_new_review(review_data)
        if saved:
            processed += 1

    return {
        "fetched": len(reviews),
        "saved": processed
    }


@router.get("/{review_id}", response_model=ReviewDetail)
def get_review(review_id: int, db: Session = Depends(get_db)):
    """Get single review with details"""
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review
