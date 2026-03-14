from __future__ import annotations

from app.constants import TOP30_SCHOOLS
from app.schemas import SchoolRecommendation


def probability_band(probability: float) -> str:
    if probability < 0.35:
        return "reach"
    if probability < 0.65:
        return "match"
    return "safe"


def build_recommendations(
    scores_by_school: dict[str, float],
    target_major: str,
    limit_per_band: int = 3,
) -> list[SchoolRecommendation]:
    grouped: dict[str, list[tuple[str, float]]] = {"reach": [], "match": [], "safe": []}

    for school in TOP30_SCHOOLS:
        prob = scores_by_school.get(school)
        if prob is None:
            continue
        grouped[probability_band(prob)].append((school, prob))

    for band in grouped:
        grouped[band].sort(key=lambda item: item[1], reverse=True)

    ordered: list[SchoolRecommendation] = []
    for band in ["reach", "match", "safe"]:
        for school, prob in grouped[band][:limit_per_band]:
            ordered.append(
                SchoolRecommendation(
                    school=school,
                    major=target_major,
                    band=band,
                    probability=round(float(prob), 4),
                )
            )
    return ordered
