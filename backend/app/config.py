from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    api_prefix: str
    database_url: str
    data_dir: Path
    raw_dir: Path
    normalized_dir: Path
    training_dir: Path
    model_dir: Path
    snapshot_dir: Path

    @staticmethod
    def from_env() -> "Settings":
        backend_root = Path(__file__).resolve().parents[1]
        data_dir = Path(os.getenv("DATA_DIR", backend_root / "data")).resolve()
        return Settings(
            app_name=os.getenv("APP_NAME", "us-admit-predictor"),
            app_env=os.getenv("APP_ENV", "dev"),
            api_prefix=os.getenv("API_PREFIX", "/api/v1"),
            database_url=os.getenv("DATABASE_URL", "sqlite:///./admit_predictor.db"),
            data_dir=data_dir,
            raw_dir=data_dir / "raw",
            normalized_dir=data_dir / "normalized",
            training_dir=data_dir / "training",
            model_dir=data_dir / "model",
            snapshot_dir=data_dir / "snapshots",
        )


settings = Settings.from_env()
