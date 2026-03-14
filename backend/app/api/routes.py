from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.constants import HOT_MAJORS, TOP30_SCHOOLS
from app.db import get_db
from app.models import PredictionEvent
from app.schemas import CatalogResponse, HealthResponse, PredictRequest, PredictResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    predictor = request.app.state.predictor
    return HealthResponse(
        status="ok",
        model_loaded=predictor.model_loaded,
        model_version=predictor.model_version,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/schools", response_model=CatalogResponse)
def schools() -> CatalogResponse:
    return CatalogResponse(values=TOP30_SCHOOLS)


@router.get("/majors", response_model=CatalogResponse)
def majors() -> CatalogResponse:
    return CatalogResponse(values=HOT_MAJORS)


@router.post("/predict", response_model=PredictResponse)
def predict(
    payload: PredictRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> PredictResponse:
    predictor = request.app.state.predictor

    if payload.target_school not in TOP30_SCHOOLS:
        raise HTTPException(status_code=422, detail="target_school must be within MVP Top30 scope")
    if payload.target_major not in HOT_MAJORS:
        raise HTTPException(status_code=422, detail="target_major must be within MVP major scope")

    result = predictor.predict(payload)

    event = PredictionEvent(
        target_school=payload.target_school,
        target_major=payload.target_major,
        admit_probability=result["admit_probability"],
        confidence_band=result["confidence_band"],
        model_version=result["model_version"],
        data_cutoff_date=result["data_cutoff_date"],
        top_factors=[item.model_dump() for item in result["top_factors"]],
        weaknesses=result["weakness_diagnosis"],
        recommendations=[item.model_dump() for item in result["reach_match_safe_schools"]],
    )
    db.add(event)
    db.commit()

    return PredictResponse(**result)
