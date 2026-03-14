from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np

from app.config import settings
from app.schemas import PredictRequest
from app.services.explanations import generate_top_factors
from app.services.features import build_feature_profile
from app.services.recommendations import build_recommendations


@dataclass
class ModelState:
    model_type: str
    model: object | None
    vectorizer: object | None
    calibrator_method: str
    calibrator: object | None
    metadata: dict


class HeuristicScorer:
    @staticmethod
    def sigmoid(x: float) -> float:
        return 1.0 / (1.0 + np.exp(-x))

    def score(self, feature_profile: dict[str, float | str | int]) -> float:
        gpa_ratio = float(feature_profile["gpa_ratio"])
        english_ratio = float(feature_profile["english_toefl_eq"]) / 120.0
        score = (
            2.2 * gpa_ratio
            + 1.3 * english_ratio
            + 0.95 * float(feature_profile["course_rigor"])
            + 0.7 * float(feature_profile["activity_strength"])
            + 0.5 * float(feature_profile["research_strength"])
            + 0.35 * float(feature_profile["award_strength"])
            - 1.85 * float(feature_profile["school_selectivity"])
            - 0.72 * float(feature_profile["major_difficulty"])
            - 0.8
        )
        probability = self.sigmoid(score)
        return float(np.clip(probability, 0.01, 0.98))


class PredictorService:
    def __init__(self, model_dir: Path | None = None) -> None:
        self.model_dir = model_dir or settings.model_dir
        self.artifact_path = self.model_dir / "admit_model.joblib"
        self.heuristic = HeuristicScorer()
        self.state = ModelState(
            model_type="heuristic",
            model=None,
            vectorizer=None,
            calibrator_method="none",
            calibrator=None,
            metadata={
                "model_version": "heuristic-v0",
                "data_cutoff_date": "N/A",
                "program_baselines": {},
                "program_counts": {},
            },
        )
        self.load()

    def load(self) -> None:
        if not self.artifact_path.exists():
            return
        try:
            artifact = joblib.load(self.artifact_path)
            self.state = ModelState(
                model_type=artifact.get("model_type", "heuristic"),
                model=artifact.get("model"),
                vectorizer=artifact.get("vectorizer"),
                calibrator_method=artifact.get("calibrator_method", "none"),
                calibrator=artifact.get("calibrator"),
                metadata=artifact.get("metadata", {}),
            )
        except Exception:
            self.state = ModelState(
                model_type="heuristic",
                model=None,
                vectorizer=None,
                calibrator_method="none",
                calibrator=None,
                metadata={
                    "model_version": "heuristic-fallback",
                    "data_cutoff_date": "N/A",
                    "program_baselines": {},
                    "program_counts": {},
                },
            )

    @property
    def model_loaded(self) -> bool:
        return self.state.model is not None

    @property
    def model_version(self) -> str:
        return self.state.metadata.get("model_version", "heuristic-v0")

    @property
    def data_cutoff_date(self) -> str:
        return self.state.metadata.get("data_cutoff_date", "N/A")

    def _apply_calibration(self, base_probability: float) -> float:
        method = self.state.calibrator_method
        calibrator = self.state.calibrator
        base = float(np.clip(base_probability, 0.0001, 0.9999))

        if calibrator is None or method == "none":
            return base

        if method == "platt":
            calibrated = float(calibrator.predict_proba(np.array([[base]]))[0, 1])
            return float(np.clip(calibrated, 0.0001, 0.9999))

        if method == "isotonic":
            calibrated = float(calibrator.predict(np.array([base]))[0])
            return float(np.clip(calibrated, 0.0001, 0.9999))

        return base

    def _predict_base_probability(self, feature_profile: dict[str, float | str | int]) -> float:
        if self.state.model is None:
            return self.heuristic.score(feature_profile)

        if self.state.model_type == "dict_vectorizer":
            assert self.state.vectorizer is not None
            row = self.state.vectorizer.transform([feature_profile])
            probability = float(self.state.model.predict_proba(row)[0, 1])
            return probability

        if self.state.model_type == "pipeline":
            import pandas as pd

            frame = pd.DataFrame([feature_profile])
            probability = float(self.state.model.predict_proba(frame)[0, 1])
            return probability

        if self.state.model_type == "catboost_raw":
            import pandas as pd

            frame = pd.DataFrame([feature_profile])
            probability = float(self.state.model.predict_proba(frame)[0, 1])
            return probability

        return self.heuristic.score(feature_profile)

    def _program_key(self, school: str, major: str) -> str:
        return f"{school}::{major}"

    def _program_baseline(self, school: str, major: str) -> dict[str, float]:
        baselines = self.state.metadata.get("program_baselines", {})
        return baselines.get(self._program_key(school, major), {})

    def _program_count(self, school: str, major: str) -> int:
        counts = self.state.metadata.get("program_counts", {})
        return int(counts.get(self._program_key(school, major), 0))

    def _confidence_band(self, school: str, major: str) -> str:
        if self.state.model is None:
            return "low"

        n = self._program_count(school, major)
        if n >= 120:
            return "high"
        if n >= 40:
            return "medium"
        return "low"

    def score_profile(self, feature_profile: dict[str, float | str | int]) -> float:
        base_probability = self._predict_base_probability(feature_profile)
        calibrated = self._apply_calibration(base_probability)
        return float(np.clip(calibrated, 0.0001, 0.9999))

    def predict_for_target(self, request: PredictRequest, school: str, major: str) -> float:
        profile = build_feature_profile(request, target_school=school, target_major=major)
        return self.score_profile(profile)

    def predict(self, request: PredictRequest) -> dict:
        target_profile = build_feature_profile(request)
        admit_probability = self.score_profile(target_profile)
        baseline = self._program_baseline(request.target_school, request.target_major)
        top_factors, weaknesses = generate_top_factors(target_profile, baseline)

        score_map: dict[str, float] = {}
        from app.constants import TOP30_SCHOOLS

        for school in TOP30_SCHOOLS:
            score_map[school] = self.predict_for_target(request, school, request.target_major)

        recommendations = build_recommendations(score_map, request.target_major)

        return {
            "admit_probability": round(admit_probability, 4),
            "confidence_band": self._confidence_band(request.target_school, request.target_major),
            "top_factors": top_factors,
            "weakness_diagnosis": weaknesses,
            "reach_match_safe_schools": recommendations,
            "model_version": self.model_version,
            "data_cutoff_date": self.data_cutoff_date,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
