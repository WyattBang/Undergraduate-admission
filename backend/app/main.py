from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.config import settings
from app.db import Base, engine
from app.services.modeling import PredictorService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.raw_dir.mkdir(parents=True, exist_ok=True)
    settings.normalized_dir.mkdir(parents=True, exist_ok=True)
    settings.training_dir.mkdir(parents=True, exist_ok=True)
    settings.model_dir.mkdir(parents=True, exist_ok=True)
    settings.snapshot_dir.mkdir(parents=True, exist_ok=True)

    Base.metadata.create_all(bind=engine)
    app.state.predictor = PredictorService(model_dir=settings.model_dir)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix, tags=["mvp"])
