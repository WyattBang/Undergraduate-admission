from fastapi.testclient import TestClient
import pytest

from app.main import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


def test_predict_contract(client: TestClient) -> None:
    payload = {
        "target_school": "Harvard University",
        "target_major": "CS",
        "english_test_type": "TOEFL",
        "english_score": 110,
        "curriculum_type": "AP",
        "gpa": 3.95,
        "course_scores": [{"course": "AP Calculus", "score": 95}],
        "activities": [{"title": "Robotics", "level": "national", "intensity": 8}],
        "awards": [{"title": "Math Contest", "level": "regional", "intensity": 7}],
        "research": [{"title": "ML Research", "level": "school", "intensity": 6}],
        "grad_year": 2026,
    }

    resp = client.post("/api/v1/predict", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert 0 <= body["admit_probability"] <= 1
    assert body["confidence_band"] in {"high", "medium", "low"}
    assert isinstance(body["top_factors"], list)
    assert isinstance(body["weakness_diagnosis"], list)
    assert isinstance(body["reach_match_safe_schools"], list)


def test_predict_rejects_out_of_scope_school(client: TestClient) -> None:
    payload = {
        "target_school": "Some Unknown University",
        "target_major": "CS",
        "english_test_type": "TOEFL",
        "english_score": 105,
        "curriculum_type": "AP",
        "gpa": 3.9,
        "course_scores": [],
        "activities": [],
        "awards": [],
        "research": [],
        "grad_year": 2026,
    }

    resp = client.post("/api/v1/predict", json=payload)
    assert resp.status_code == 422
