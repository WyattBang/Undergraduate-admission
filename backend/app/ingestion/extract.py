from __future__ import annotations

import re
from datetime import datetime

from app.constants import HOT_MAJORS, TOP30_SCHOOLS

_SCHOOL_ALIASES = {
    "哈佛": "Harvard University",
    "斯坦福": "Stanford University",
    "MIT": "Massachusetts Institute of Technology",
    "普林斯顿": "Princeton University",
    "耶鲁": "Yale University",
    "宾大": "University of Pennsylvania",
    "康奈尔": "Cornell University",
    "哥大": "Columbia University",
    "UCB": "University of California, Berkeley",
    "UCLA": "University of California, Los Angeles",
    "CMU": "Carnegie Mellon University",
    "纽大": "New York University",
}

_MAJOR_ALIASES = {
    "computer science": "CS",
    "cs": "CS",
    "ee": "EE",
    "electrical": "EE",
    "data science": "Data Science",
    "economics": "Economics",
    "econ": "Economics",
    "计算机": "CS",
    "电子工程": "EE",
    "数据科学": "Data Science",
    "经济": "Economics",
}

_TOEFL_RE = re.compile(r"(?:toefl|托福)\D{0,6}(\d{2,3})", re.IGNORECASE)
_IELTS_RE = re.compile(r"(?:ielts|雅思)\D{0,6}(\d(?:\.\d)?)", re.IGNORECASE)
_GPA_RE = re.compile(r"(?:gpa|绩点)\D{0,6}([0-4](?:\.\d{1,3})?)", re.IGNORECASE)
_AVG_RE = re.compile(r"(?:均分|平均分)\D{0,6}(\d{2,3}(?:\.\d)?)", re.IGNORECASE)
_YEAR_RE = re.compile(r"(20\d{2})")
_AP_RE = re.compile(r"AP\s*([A-Za-z\s]+)?\s*[:：]?\s*([1-5])", re.IGNORECASE)


def _detect_school(text: str) -> str | None:
    lower = text.lower()
    for school in TOP30_SCHOOLS:
        if school.lower() in lower:
            return school
    for alias, school in _SCHOOL_ALIASES.items():
        if alias.lower() in lower:
            return school
    return None


def _detect_major(text: str) -> str:
    lower = text.lower()
    for alias, major in _MAJOR_ALIASES.items():
        if alias in lower:
            return major
    return HOT_MAJORS[0]


def _detect_result(text: str) -> str | None:
    lower = text.lower()
    if any(token in lower for token in ["offer", "admit", "录取", "上岸"]):
        return "offer"
    if any(token in lower for token in ["waitlist", "wl", "候补"]):
        return "waitlist"
    if any(token in lower for token in ["reject", "rej", "拒"]):
        return "reject"
    return None


def _parse_english(text: str) -> tuple[str, float] | None:
    toefl = _TOEFL_RE.search(text)
    if toefl:
        return "TOEFL", float(toefl.group(1))

    ielts = _IELTS_RE.search(text)
    if ielts:
        return "IELTS", float(ielts.group(1))
    return None


def _parse_gpa(text: str) -> float | None:
    gpa = _GPA_RE.search(text)
    if gpa:
        return float(gpa.group(1))
    avg = _AVG_RE.search(text)
    if avg:
        avg_score = float(avg.group(1))
        return round(min(4.3, max(0.0, avg_score / 100.0 * 4.0 + 0.1)), 3)
    return None


def _parse_course_scores(text: str) -> list[dict]:
    scores = []
    for idx, match in enumerate(_AP_RE.finditer(text)):
        name = match.group(1) or f"AP Course {idx + 1}"
        ap_score = float(match.group(2))
        scores.append({"course": name.strip()[:60], "score": ap_score / 5.0 * 100.0})
    return scores


def _infer_curriculum(text: str) -> str:
    lower = text.lower()
    if "ib" in lower:
        return "IB"
    if "a-level" in lower or "alevel" in lower:
        return "A-Level"
    if "ap" in lower:
        return "AP"
    return "Other"


def _extract_profile_items(text: str, keywords: list[str], default_title: str) -> list[dict]:
    lower = text.lower()
    found = [kw for kw in keywords if kw in lower]
    if not found:
        return []
    return [{"title": default_title, "level": "school", "intensity": min(10, 4 + len(found))}]


def normalize_raw_post(raw_record: dict) -> dict | None:
    content = str(raw_record.get("content", ""))
    school = _detect_school(content)
    result = _detect_result(content)
    if not school or not result:
        return None

    english = _parse_english(content) or ("TOEFL", 95.0)
    gpa = _parse_gpa(content) or 3.7

    season_year = datetime.utcnow().year
    year_match = _YEAR_RE.findall(content)
    if year_match:
        season_year = int(year_match[-1])

    major = _detect_major(content)
    curriculum = _infer_curriculum(content)
    course_scores = _parse_course_scores(content)

    applicant = {
        "english_test_type": english[0],
        "english_score": english[1],
        "gpa": gpa,
        "curriculum_type": curriculum,
        "course_scores": course_scores,
        "activities": _extract_profile_items(
            content,
            ["志愿", "社团", "volunteer", "club", "intern"],
            "综合活动",
        ),
        "awards": _extract_profile_items(content, ["奖", "award", "竞赛"], "奖项经历"),
        "research": _extract_profile_items(content, ["科研", "research", "paper"], "科研经历"),
        "grad_year": season_year,
    }

    normalized = {
        "source": raw_record.get("source", "unknown"),
        "collected_at": raw_record.get("collected_at"),
        "post_hash": raw_record.get("content_hash"),
        "raw_text": content,
        "applicant": applicant,
        "applications": [
            {
                "school": school,
                "major": major,
                "result": result,
                "season": season_year,
            }
        ],
    }
    return normalized
