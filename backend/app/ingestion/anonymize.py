from __future__ import annotations

import hashlib
import re

_PII_PATTERNS = [
    re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
    re.compile(r"\b1[3-9]\d{9}\b"),
    re.compile(r"\b(?:wx|wechat|v)[:：\s]*[a-zA-Z0-9_-]{5,}\b", re.IGNORECASE),
]


def redact_text(text: str) -> str:
    sanitized = text
    for pattern in _PII_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)
    return sanitized


def stable_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def anonymize_raw_record(record: dict) -> dict:
    copied = dict(record)
    copied.pop("author", None)
    copied.pop("author_id", None)
    copied.pop("user_id", None)
    copied["url"] = "[REMOVED]"

    content = str(copied.get("content", ""))
    copied["content"] = redact_text(content)
    copied["content_hash"] = stable_hash(copied["content"])
    return copied


def anonymize_normalized_record(record: dict) -> dict:
    cloned = dict(record)
    applicant = cloned.get("applicant", {})

    key = "|".join(
        [
            str(applicant.get("english_test_type", "")),
            str(applicant.get("english_score", "")),
            str(applicant.get("gpa", "")),
            str(applicant.get("curriculum_type", "")),
            str(applicant.get("grad_year", "")),
        ]
    )

    cloned["applicant_id"] = stable_hash(key)[:24]
    cloned.pop("raw_text", None)
    cloned.pop("url", None)
    cloned.pop("post_id", None)
    return cloned
