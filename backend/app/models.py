from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String

from app.db import Base


class PredictionEvent(Base):
    __tablename__ = "prediction_events"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    target_school = Column(String(255), nullable=False)
    target_major = Column(String(128), nullable=False)
    admit_probability = Column(Float, nullable=False)
    confidence_band = Column(String(16), nullable=False)
    model_version = Column(String(64), nullable=False)
    data_cutoff_date = Column(String(32), nullable=False)
    top_factors = Column(JSON, nullable=False)
    weaknesses = Column(JSON, nullable=False)
    recommendations = Column(JSON, nullable=False)


class IngestionBatch(Base):
    __tablename__ = "ingestion_batches"

    id = Column(String(64), primary_key=True)
    source = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    raw_count = Column(Integer, default=0, nullable=False)
    deduped_count = Column(Integer, default=0, nullable=False)
    acceptance_rate = Column(Float, nullable=True)
    notes = Column(String(512), nullable=True)
