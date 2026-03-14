#!/usr/bin/env python3
from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.constants import HOT_MAJORS, MAJOR_DIFFICULTY_SCORE, SCHOOL_SELECTIVITY_SCORE, TOP30_SCHOOLS


def _clamp(v: float, low: float, high: float) -> float:
    return max(low, min(high, v))


def _sigmoid(x: float) -> float:
    return 1 / (1 + (2.718281828 ** (-x)))


def _sample_result(score: float) -> str:
    p = _clamp(score, 0.02, 0.97)
    r = random.random()
    if r < p:
        return "offer"
    if r < p + 0.06:
        return "waitlist"
    return "reject"


def make_demo_row() -> dict:
    school = random.choice(TOP30_SCHOOLS)
    major = random.choice(HOT_MAJORS)
    season = random.choice([2023, 2024, 2025])

    english_test_type = random.choice(["TOEFL", "IELTS"])
    english_score = random.randint(82, 116) if english_test_type == "TOEFL" else random.choice([6.5, 7.0, 7.5, 8.0])

    gpa = round(random.uniform(3.3, 4.2), 2)
    curriculum = random.choice(["AP", "IB", "A-Level"])
    activity_n = random.randint(1, 5)
    award_n = random.randint(0, 3)
    research_n = random.randint(0, 2)

    profile_score = _sigmoid(
        2.1 * (gpa / 4.3)
        + 1.2 * (min(120, english_score if english_test_type == "TOEFL" else 95 + (english_score - 7) * 14) / 120)
        + 0.6 * (activity_n / 5)
        + 0.35 * (award_n / 3)
        + 0.45 * (research_n / 2)
        - 1.7 * SCHOOL_SELECTIVITY_SCORE.get(school, 0.7)
        - 0.7 * MAJOR_DIFFICULTY_SCORE.get(major, 0.75)
        - 0.7
    )

    result = _sample_result(profile_score)

    return {
        "source": "synthetic",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "post_hash": f"synthetic_{random.randint(10_000, 999_999)}",
        "applicant": {
            "english_test_type": english_test_type,
            "english_score": english_score,
            "gpa": gpa,
            "curriculum_type": curriculum,
            "course_scores": [
                {"course": "Math", "score": random.randint(82, 100)},
                {"course": "Physics", "score": random.randint(80, 100)},
                {"course": "English", "score": random.randint(78, 100)},
            ],
            "activities": [{"title": f"Activity {i}", "level": "school", "intensity": random.randint(4, 9)} for i in range(activity_n)],
            "awards": [{"title": f"Award {i}", "level": "regional", "intensity": random.randint(4, 8)} for i in range(award_n)],
            "research": [{"title": f"Research {i}", "level": "school", "intensity": random.randint(5, 9)} for i in range(research_n)],
            "grad_year": season,
        },
        "applications": [
            {
                "school": school,
                "major": major,
                "result": result,
                "season": season,
            }
        ],
    }


def main() -> None:
    random.seed(42)
    settings.normalized_dir.mkdir(parents=True, exist_ok=True)
    output_path = settings.normalized_dir / "synthetic_seed.jsonl"

    rows = [make_demo_row() for _ in range(2000)]
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"seeded={len(rows)} output={output_path}")


if __name__ == "__main__":
    main()
