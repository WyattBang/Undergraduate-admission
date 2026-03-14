from __future__ import annotations

from app.schemas import TopFactor

_FACTOR_LABELS = {
    "english_toefl_eq": "语言成绩",
    "gpa": "GPA",
    "course_rigor": "课程强度",
    "activity_strength": "活动背景",
    "research_strength": "科研背景",
    "award_strength": "奖项背景",
}


def _safe_baseline(baseline: dict[str, float], key: str, default: float) -> float:
    value = baseline.get(key)
    if value is None:
        return default
    return float(value)


def _fmt(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def generate_top_factors(
    feature_profile: dict[str, float | str | int],
    program_baseline: dict[str, float],
) -> tuple[list[TopFactor], list[str]]:
    candidate_metrics = {
        "english_toefl_eq": float(feature_profile.get("english_toefl_eq", 0)),
        "gpa": float(feature_profile.get("gpa", 0)),
        "course_rigor": float(feature_profile.get("course_rigor", 0)),
        "activity_strength": float(feature_profile.get("activity_strength", 0)),
        "research_strength": float(feature_profile.get("research_strength", 0)),
        "award_strength": float(feature_profile.get("award_strength", 0)),
    }

    baseline_defaults = {
        "english_toefl_eq_p50": 98,
        "gpa_p50": 3.75,
        "course_rigor_p50": 0.78,
        "activity_strength_p50": 0.55,
        "research_strength_p50": 0.45,
        "award_strength_p50": 0.42,
    }

    factor_scores: list[tuple[str, float, float, float]] = []
    for key, value in candidate_metrics.items():
        baseline_key = f"{key}_p50"
        baseline_value = _safe_baseline(
            program_baseline,
            baseline_key,
            baseline_defaults[baseline_key],
        )
        denominator = max(0.05, abs(baseline_value))
        normalized_delta = (value - baseline_value) / denominator
        factor_scores.append((key, value, baseline_value, normalized_delta))

    factor_scores.sort(key=lambda item: abs(item[3]), reverse=True)

    factors: list[TopFactor] = []
    weaknesses: list[str] = []

    for key, value, baseline_value, delta in factor_scores[:4]:
        impact = "positive" if delta >= 0 else "negative"
        label = _FACTOR_LABELS[key]
        evidence = (
            f"{label}为{_fmt(value)}，"
            f"项目样本中位数约为{_fmt(baseline_value)}。"
        )
        factors.append(TopFactor(factor=label, impact=impact, evidence=evidence))

        if delta <= -0.08:
            weaknesses.append(
                f"{label}低于目标项目同档样本中位数，建议优先补强该维度。"
            )

    if not weaknesses:
        weaknesses.append("当前硬指标未见明显短板，建议在活动叙事与项目匹配度上继续优化。")

    return factors, weaknesses
