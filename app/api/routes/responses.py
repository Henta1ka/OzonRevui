"""Response/Answer endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas.response import ResponseSchema, ResponseDraftSchema, ResponseCreateSchema
from app.models.response import Response, ResponseDraft
from app.models.review import Review
from app.services.review_service import ReviewService

router = APIRouter(prefix="/api/responses", tags=["responses"])


@router.get("/drafts/{review_id}", response_model=List[ResponseDraftSchema])
def get_response_drafts(review_id: int, db: Session = Depends(get_db)):
    """Get all response drafts for a review"""
    drafts = db.query(ResponseDraft).filter(
        ResponseDraft.review_id == review_id
    ).order_by(ResponseDraft.variant_number).all()
    if not drafts:
        raise HTTPException(status_code=404, detail="No drafts found")
    return drafts


@router.get("/{response_id}", response_model=ResponseSchema)
def get_response(response_id: int, db: Session = Depends(get_db)):
    """Get response details"""
    response = db.query(Response).filter(Response.id == response_id).first()
    if not response:
        raise HTTPException(status_code=404, detail="Response not found")
    return response


@router.post("", response_model=ResponseSchema)
async def create_response(
    data: ResponseCreateSchema,
    db: Session = Depends(get_db)
):
    """Create and submit a response"""
    # Verify review exists
    review = db.query(Review).filter(Review.id == data.review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    service = ReviewService(db)
    response = await service.submit_response(
        review_id=data.review_id,
        response_text=data.text,
        draft_id=data.draft_id
    )
    
    if not response:
        raise HTTPException(status_code=400, detail="Failed to submit response")
    
    return response


@router.get("/history/recent")
def get_recent_responses(limit: int = 100, db: Session = Depends(get_db)):
    """Get recent responses"""
    responses = db.query(Response).order_by(
        Response.created_at.desc()
    ).limit(limit).all()
    return [ResponseSchema.from_orm(r) for r in responses]


@router.get("/status/{status}", response_model=List[ResponseSchema])
def get_responses_by_status(status: str, db: Session = Depends(get_db)):
    """Get responses by status (draft, approved, sent, failed)"""
    responses = db.query(Response).filter(
        Response.status == status
    ).order_by(Response.created_at.desc()).all()
    return responses
