import json

from app.pipeline.quality_gate import audit_and_rollback


def test_quality_gate_rolls_back_on_low_precision(tmp_path) -> None:
    normalized = tmp_path / "batch.jsonl"
    audit = tmp_path / "audit.csv"

    rows = [
        {"applications": [{"result": "offer"}]},
        {"applications": [{"result": "reject"}]},
    ]
    normalized.write_text("\n".join(json.dumps(x) for x in rows), encoding="utf-8")
    audit.write_text("label\nreject\nreject\n", encoding="utf-8")

    passed, precision, rejected = audit_and_rollback(normalized, audit, threshold=0.9)

    assert not passed
    assert precision < 0.9
    assert rejected is not None
    assert rejected.exists()
    assert not normalized.exists()
