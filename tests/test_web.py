"""
Unit tests for FastAPI Web Dashboard & Backend API.
"""

from fastapi.testclient import TestClient
import pytest

from src.web.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_get_status(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "environment" in data
    assert "mcp" in data
    assert data["environment"]["llm_provider"] == "Groq"


def test_get_pulses(client):
    response = client.get("/api/pulses")
    assert response.status_code == 200
    data = response.json()
    assert "pulses" in data
    assert "total" in data
    assert data["total"] >= 1
    # Check that 2026-W40 exists
    weeks = [p["week"] for p in data["pulses"]]
    assert "2026-W40" in weeks


def test_get_pulse_detail(client):
    response = client.get("/api/pulses/2026-W40")
    assert response.status_code == 200
    data = response.json()
    assert data["week"] == "2026-W40"
    assert "summary" in data
    assert len(data["themes"]) == 3
    assert len(data["quotes"]) == 3
    assert len(data["actions"]) == 3
    assert "markdown" in data
    assert "html" in data


def test_get_pulse_not_found(client):
    response = client.get("/api/pulses/1999-W01")
    assert response.status_code == 404


def test_get_metrics(client):
    response = client.get("/api/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "total_raw_reviews" in data
    assert "average_rating" in data
    assert "sentiment_distribution" in data
    assert "top_themes" in data


def test_get_reviews_pagination(client):
    response = client.get("/api/reviews?page=1&page_size=5")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert "reviews" in data
    assert len(data["reviews"]) <= 5


def test_get_pipeline_status(client):
    response = client.get("/api/pipeline/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["idle", "running", "completed", "failed"]


def test_serve_static_index(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Groww App Review Pulse" in response.text
