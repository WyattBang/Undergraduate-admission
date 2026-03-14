from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CourseScore(BaseModel):
    course: str = Field(..., min_length=1, max_length=120)
    score: float = Field(..., ge=0, le=100)


class ProfileItem(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    level: str | None = Field(default=None, max_length=80)
    intensity: float | None = Field(default=None, ge=0, le=10)


class PredictRequest(BaseModel):
    target_school: str = Field(..., min_length=3, max_length=255)
    target_major: str = Field(..., min_length=2, max_length=128)
    english_test_type: str = Field(..., pattern="^(TOEFL|IELTS)$")
    english_score: float = Field(..., ge=0, le=120)
    curriculum_type: str = Field(..., max_length=64)
    gpa: float = Field(..., ge=0, le=4.3)
    course_scores: list[CourseScore] = Field(default_factory=list)
    activities: list[ProfileItem] = Field(default_factory=list)
    awards: list[ProfileItem] = Field(default_factory=list)
    research: list[ProfileItem] = Field(default_factory=list)
    grad_year: int = Field(..., ge=2018, le=2035)


class TopFactor(BaseModel):
    factor: str
    impact: str
    evidence: str


class SchoolRecommendation(BaseModel):
    school: str
    major: str
    band: str
    probability: float


class PredictResponse(BaseModel):
    admit_probability: float
    confidence_band: str
    top_factors: list[TopFactor]
    weakness_diagnosis: list[str]
    reach_match_safe_schools: list[SchoolRecommendation]
    model_version: str
    data_cutoff_date: str


class CatalogResponse(BaseModel):
    values: list[str]


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_version: str
    timestamp: datetime
