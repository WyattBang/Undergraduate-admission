from app.ingestion.anonymize import anonymize_raw_record


def test_anonymize_removes_pii_fields_and_redacts() -> None:
    row = {
        "author": "foo",
        "author_id": "id123",
        "url": "https://example.com/post",
        "content": "联系我 test@example.com 或 13800138000 wechat:abc12345",
    }

    cleaned = anonymize_raw_record(row)

    assert cleaned["url"] == "[REMOVED]"
    assert "author" not in cleaned
    assert "author_id" not in cleaned
    assert "[REDACTED]" in cleaned["content"]
    assert cleaned["content_hash"]
