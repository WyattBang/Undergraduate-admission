from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.config import settings
from app.constants import MAJOR_DIFFICULTY_SCORE, SCHOOL_SELECTIVITY_SCORE
from app.services.features import english_to_toefl_equivalent


def _profile_strength(items: list[dict]) -> float:
    if not items:
        return 0.0
    total = 0.0
    for item in items:
        intensity = float(item.get("intensity", 5)) / 10.0
        level = str(item.get("level", "school")).lower()
        weight = {
            "international": 1.0,
            "national": 0.85,
            "regional": 0.68,
            "provincial": 0.62,
            "school": 0.45,
        }.get(level, 0.55)
        total += max(0.1, min(1.0, intensity)) * weight
    return min(1.0, total / len(items))


def _course_rigor(curriculum: str, course_scores: list[dict]) -> float:
    base = {"AP": 0.82, "IB": 0.86, "A-Level": 0.8}.get(curriculum, 0.72)
    if not course_scores:
        return base
    course_avg = sum(float(item.get("score", 85)) for item in course_scores) / len(course_scores)
    return max(0.0, min(1.0, base + (course_avg - 80.0) * 0.0015 + min(len(course_scores) / 10.0, 0.18)))


def _iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def build_training_set(input_files: list[Path], output_csv: Path) -> pd.DataFrame:
    rows: list[dict] = []

    for file_path in input_files:
        for record in _iter_jsonl(file_path):
            applicant = record.get("applicant", {})
            applications = record.get("applications", [])

            english = english_to_toefl_equivalent(
                str(applicant.get("english_test_type", "TOEFL")),
                float(applicant.get("english_score", 95.0)),
            )
            gpa = float(applicant.get("gpa", 3.7))
            curriculum = str(applicant.get("curriculum_type", "Other"))
            course_scores = list(applicant.get("course_scores", []))
            activity_strength = _profile_strength(list(applicant.get("activities", [])))
            award_strength = _profile_strength(list(applicant.get("awards", [])))
            research_strength = _profile_strength(list(applicant.get("research", [])))
            course_rigor = _course_rigor(curriculum, course_scores)
            course_avg = (
                sum(float(c.get("score", 85)) for c in course_scores) / len(course_scores)
                if course_scores
                else 85.0
            )

            for app in applications:
                school = str(app.get("school", ""))
                major = str(app.get("major", "CS"))
                result = str(app.get("result", "reject")).lower()
                season = int(app.get("season", applicant.get("grad_year", 2025)))

                row = {
                    "target_school": school,
                    "target_major": major,
                    "curriculum_type": curriculum,
                    "season": season,
                    "english_toefl_eq": english,
                    "gpa": gpa,
                    "course_avg": course_avg,
                    "course_rigor": course_rigor,
                    "activity_strength": activity_strength,
                    "award_strength": award_strength,
                    "research_strength": research_strength,
                    "activity_count": len(applicant.get("activities", [])),
                    "award_count": len(applicant.get("awards", [])),
                    "research_count": len(applicant.get("research", [])),
                    "school_selectivity": SCHOOL_SELECTIVITY_SCORE.get(school, 0.7),
                    "major_difficulty": MAJOR_DIFFICULTY_SCORE.get(major, 0.75),
                    "label_admit": 1 if result == "offer" else 0,
                    "waitlist_flag": 1 if result == "waitlist" else 0,
                }
                rows.append(row)

    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError("No valid training rows were generated from normalized data")

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_csv, index=False)
    return frame


def build_latest_training_set() -> Path:
    normalized_files = sorted(settings.normalized_dir.glob("*.jsonl"))
    if not normalized_files:
        raise FileNotFoundError("No normalized batches found under backend/data/normalized")

    output = settings.training_dir / "training_set.csv"
    build_training_set(normalized_files, output)
    return output


if __name__ == "__main__":
    path = build_latest_training_set()
    print(path)
