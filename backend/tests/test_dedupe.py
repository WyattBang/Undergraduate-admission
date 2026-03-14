from app.ingestion.dedupe import dedupe_records


def test_dedupe_records_uses_fingerprint() -> None:
    base = {
        "collected_at": "2025-11-01T00:00:00+00:00",
        "applicant": {
            "english_score": 108,
            "gpa": 3.9,
            "curriculum_type": "AP",
            "grad_year": 2025,
            "activities": [{"title": "volunteer"}],
        },
        "applications": [
            {
                "school": "Harvard University",
                "major": "CS",
                "result": "offer",
                "season": 2025,
            }
        ],
    }

    unique, duplicates = dedupe_records([base, base.copy()])
    assert len(unique) == 1
    assert duplicates == 1
