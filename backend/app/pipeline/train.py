from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction import DictVectorizer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

from app.config import settings
from app.pipeline.metrics import summarize_binary_metrics


FEATURE_COLUMNS = [
    "target_school",
    "target_major",
    "curriculum_type",
    "season",
    "english_toefl_eq",
    "gpa",
    "course_avg",
    "course_rigor",
    "activity_strength",
    "award_strength",
    "research_strength",
    "activity_count",
    "award_count",
    "research_count",
    "school_selectivity",
    "major_difficulty",
]


def _split_by_season(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if frame["season"].nunique() < 2:
        train_frame, val_frame = train_test_split(
            frame,
            test_size=0.2,
            random_state=42,
            stratify=frame["label_admit"],
        )
        return train_frame, val_frame

    latest_season = int(frame["season"].max())
    val_frame = frame[frame["season"] == latest_season]
    train_frame = frame[frame["season"] < latest_season]

    if train_frame.empty or val_frame.empty or val_frame["label_admit"].nunique() < 2:
        train_frame, val_frame = train_test_split(
            frame,
            test_size=0.2,
            random_state=42,
            stratify=frame["label_admit"],
        )
    return train_frame, val_frame


def _fit_base_model(X_train_records: list[dict], y_train: np.ndarray):
    try:
        from catboost import CatBoostClassifier  # type: ignore

        train_frame = pd.DataFrame(X_train_records)
        categorical = [col for col in ["target_school", "target_major", "curriculum_type"] if col in train_frame.columns]
        cat_indices = [train_frame.columns.get_loc(col) for col in categorical]

        model = CatBoostClassifier(
            iterations=350,
            depth=6,
            learning_rate=0.05,
            loss_function="Logloss",
            eval_metric="Logloss",
            verbose=False,
            random_state=42,
        )
        model.fit(train_frame, y_train, cat_features=cat_indices)
        return "catboost_raw", model, None
    except Exception:  # noqa: BLE001
        model_type = "dict_vectorizer"
        vectorizer = DictVectorizer(sparse=False)
        X_train = vectorizer.fit_transform(X_train_records)

        # Fallback to sklearn GBDT when CatBoost runtime is unavailable.
        from sklearn.ensemble import GradientBoostingClassifier

        model = GradientBoostingClassifier(random_state=42)
        model.fit(X_train, y_train)
        return model_type, model, vectorizer


def _select_calibrator(y_val: np.ndarray, base_prob: np.ndarray):
    base_prob = np.clip(base_prob, 0.0001, 0.9999)

    platt = LogisticRegression(random_state=42)
    platt.fit(base_prob.reshape(-1, 1), y_val)
    platt_prob = platt.predict_proba(base_prob.reshape(-1, 1))[:, 1]
    platt_metrics = summarize_binary_metrics(y_val, platt_prob)

    isotonic = IsotonicRegression(out_of_bounds="clip")
    isotonic.fit(base_prob, y_val)
    isotonic_prob = isotonic.predict(base_prob)
    isotonic_metrics = summarize_binary_metrics(y_val, isotonic_prob)

    if isotonic_metrics["ece"] < platt_metrics["ece"]:
        return "isotonic", isotonic, isotonic_metrics
    return "platt", platt, platt_metrics


def _build_program_metadata(frame: pd.DataFrame) -> tuple[dict, dict]:
    grouped = frame.groupby(["target_school", "target_major"], dropna=False)

    baselines: dict[str, dict] = {}
    counts: dict[str, int] = {}

    for (school, major), group in grouped:
        key = f"{school}::{major}"
        baselines[key] = {
            "english_toefl_eq_p50": float(group["english_toefl_eq"].median()),
            "gpa_p50": float(group["gpa"].median()),
            "course_rigor_p50": float(group["course_rigor"].median()),
            "activity_strength_p50": float(group["activity_strength"].median()),
            "research_strength_p50": float(group["research_strength"].median()),
            "award_strength_p50": float(group["award_strength"].median()),
        }
        counts[key] = int(len(group))

    return baselines, counts


def train_and_save(training_csv: Path, model_path: Path) -> dict[str, float]:
    frame = pd.read_csv(training_csv)
    if frame.empty:
        raise ValueError("training set is empty")

    frame = frame.dropna(subset=["label_admit"])
    train_frame, val_frame = _split_by_season(frame)

    train_records = train_frame[FEATURE_COLUMNS].to_dict(orient="records")
    val_records = val_frame[FEATURE_COLUMNS].to_dict(orient="records")

    y_train = train_frame["label_admit"].astype(int).to_numpy()
    y_val = val_frame["label_admit"].astype(int).to_numpy()

    model_type, model, vectorizer = _fit_base_model(train_records, y_train)

    if model_type == "catboost_raw":
        X_val = pd.DataFrame(val_records)
        val_base_prob = model.predict_proba(X_val)[:, 1]
    else:
        assert vectorizer is not None
        X_val = vectorizer.transform(val_records)
        val_base_prob = model.predict_proba(X_val)[:, 1]
    base_metrics = summarize_binary_metrics(y_val, val_base_prob)

    calibrator_method, calibrator, calibrated_metrics = _select_calibrator(y_val, val_base_prob)

    program_baselines, program_counts = _build_program_metadata(frame)
    metadata = {
        "model_version": f"mvp-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "data_cutoff_date": date.today().isoformat(),
        "base_metrics": base_metrics,
        "calibrated_metrics": calibrated_metrics,
        "program_baselines": program_baselines,
        "program_counts": program_counts,
    }

    artifact = {
        "model_type": model_type,
        "model": model,
        "vectorizer": vectorizer,
        "calibrator_method": calibrator_method,
        "calibrator": calibrator,
        "metadata": metadata,
    }

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, model_path)

    return {
        "base_auc": base_metrics["auc"],
        "base_brier": base_metrics["brier"],
        "base_ece": base_metrics["ece"],
        "calibrated_auc": calibrated_metrics["auc"],
        "calibrated_brier": calibrated_metrics["brier"],
        "calibrated_ece": calibrated_metrics["ece"],
        "calibration": calibrator_method,
    }


def train_latest_training_set() -> dict[str, float]:
    training_csv = settings.training_dir / "training_set.csv"
    if not training_csv.exists():
        raise FileNotFoundError(f"Training set missing at {training_csv}")

    model_path = settings.model_dir / "admit_model.joblib"
    return train_and_save(training_csv, model_path)
