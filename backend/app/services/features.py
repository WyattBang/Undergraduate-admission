from __future__ import annotations

from statistics import mean

from app.constants import (
    CURRICULUM_RIGOR_BASE,
    IELTS_TO_TOEFL,
    MAJOR_DIFFICULTY_SCORE,
    SCHOOL_SELECTIVITY_SCORE,
)
from app.schemas import PredictRequest, ProfileItem


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _ielts_to_toefl(score: float) -> float:
    known = sorted(IELTS_TO_TOEFL.items(), key=lambda item: item[0])
    if score <= known[0][0]:
        return float(known[0][1])
    if score >= known[-1][0]:
        return float(known[-1][1])

    for idx in range(1, len(known)):
        left_band, left_toefl = known[idx - 1]
        right_band, right_toefl = known[idx]
        if left_band <= score <= right_band:
            ratio = (score - left_band) / (right_band - left_band)
            return left_toefl + ratio * (right_toefl - left_toefl)
    return 90.0


def english_to_toefl_equivalent(test_type: str, score: float) -> float:
    if test_type.upper() == "TOEFL":
        return _clamp(score, 0.0, 120.0)
    return _clamp(_ielts_to_toefl(score), 0.0, 120.0)


def _level_weight(level: str | None) -> float:
    if not level:
        return 0.6
    normalized = level.strip().lower()
    mapping = {
        "international": 1.0,
        "national": 0.85,
        "regional": 0.68,
        "provincial": 0.62,
        "school": 0.45,
    }
    return mapping.get(normalized, 0.58)


def _profile_strength(items: list[ProfileItem]) -> float:
    if not items:
        return 0.0
    weighted = []
    for item in items:
        intensity = item.intensity if item.intensity is not None else 5.0
        weighted.append(_level_weight(item.level) * _clamp(intensity / 10.0, 0.1, 1.0))
    return _clamp(mean(weighted), 0.0, 1.0)


def _course_average(course_scores: list) -> float:
    if not course_scores:
        return 85.0
    return _clamp(mean(item.score for item in course_scores), 0.0, 100.0)


def compute_course_rigor(curriculum_type: str, course_scores: list) -> float:
    base = CURRICULUM_RIGOR_BASE.get(curriculum_type, CURRICULUM_RIGOR_BASE["Other"])
    score_bonus = (_course_average(course_scores) - 80.0) / 100.0 * 0.15
    load_bonus = min(len(course_scores) / 10.0, 0.18)
    return _clamp(base + score_bonus + load_bonus, 0.0, 1.0)


def build_feature_profile(
    request: PredictRequest,
    target_school: str | None = None,
    target_major: str | None = None,
) -> dict[str, float | str | int]:
    school = target_school or request.target_school
    major = target_major or request.target_major

    english = english_to_toefl_equivalent(request.english_test_type, request.english_score)
    gpa_ratio = _clamp(request.gpa / 4.3, 0.0, 1.0)
    course_avg = _course_average(request.course_scores)

    activity_strength = _profile_strength(request.activities)
    award_strength = _profile_strength(request.awards)
    research_strength = _profile_strength(request.research)
    course_rigor = compute_course_rigor(request.curriculum_type, request.course_scores)

    school_selectivity = SCHOOL_SELECTIVITY_SCORE.get(school, 0.7)
    major_difficulty = MAJOR_DIFFICULTY_SCORE.get(major, 0.75)

    return {
        "english_toefl_eq": round(english, 3),
        "gpa": round(request.gpa, 3),
        "gpa_ratio": round(gpa_ratio, 4),
        "course_avg": round(course_avg, 3),
        "course_rigor": round(course_rigor, 4),
        "activity_strength": round(activity_strength, 4),
        "award_strength": round(award_strength, 4),
        "research_strength": round(research_strength, 4),
        "activity_count": len(request.activities),
        "award_count": len(request.awards),
        "research_count": len(request.research),
        "target_school": school,
        "target_major": major,
        "curriculum_type": request.curriculum_type,
        "school_selectivity": round(school_selectivity, 4),
        "major_difficulty": round(major_difficulty, 4),
        "grad_year": request.grad_year,
    }
