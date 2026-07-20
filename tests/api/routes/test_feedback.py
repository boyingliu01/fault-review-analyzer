"""Unit tests for /feedback routes."""

import uuid
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.server import create_app
from src.feedback.models import Feedback, FeedbackRating, FeedbackResponse, FeedbackType


@pytest.fixture
def mock_feedback_manager():
    """Create a pure MagicMock FeedbackManager with all needed methods."""
    mgr = MagicMock()
    mgr.add_feedback = MagicMock()
    mgr.get_feedback = MagicMock()
    mgr.get_feedback_by_task = MagicMock()
    mgr.list_feedback = MagicMock()
    mgr.review_feedback = MagicMock()
    mgr.get_statistics = MagicMock()
    mgr.close = MagicMock()
    return mgr


@pytest.fixture
def client(mock_feedback_manager):
    """Create client with FeedbackManager dependency overridden."""
    app = create_app(valid_tokens={"test-token-123"})

    from src.api.routes.feedback import get_feedback_manager
    app.dependency_overrides[get_feedback_manager] = lambda: mock_feedback_manager

    with TestClient(app) as tc:
        yield tc

    app.dependency_overrides.clear()


def _headers() -> dict[str, str]:
    return {"X-API-Token": "test-token-123"}


def _make_feedback(**overrides):
    """Helper: create a Feedback instance with defaults."""
    defaults = {
        "id": str(uuid.uuid4()),
        "task_id": "12345",
        "feedback_type": FeedbackType.GENERAL,
        "original_result": {"label": "bug"},
        "corrected_result": None,
        "rating": FeedbackRating.GOOD,
        "comment": "Looks good",
        "created_by": "tester",
        "created_at": datetime.now(),
        "reviewed": False,
        "reviewed_by": None,
        "reviewed_at": None,
    }
    defaults.update(overrides)
    return Feedback(**defaults)


def _make_response(**overrides):
    """Helper: create a FeedbackResponse from a Feedback (for list_feedback mock)."""
    fb = _make_feedback(**overrides)
    return FeedbackResponse(**fb.model_dump())


# ---------------------------------------------------------------------------
# POST /feedback
# ---------------------------------------------------------------------------

class TestCreateFeedback:
    """Tests for POST /feedback (create_feedback)."""

    def test_happy_path(self, client, mock_feedback_manager):
        fb = _make_feedback()
        mock_feedback_manager.add_feedback.return_value = fb.id
        mock_feedback_manager.get_feedback.return_value = fb

        payload = {
            "task_id": "12345",
            "feedback_type": "general",
            "original_result": {"label": "bug"},
            "rating": 4,
            "comment": "Looks good",
            "created_by": "tester",
        }

        response = client.post("/feedback", json=payload, headers=_headers())
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "12345"
        assert data["feedback_type"] == "general"
        assert data["rating"] == 4

    def test_with_correction_result(self, client, mock_feedback_manager):
        fb = _make_feedback(
            feedback_type=FeedbackType.LABEL_CORRECTION,
            corrected_result={"label": "not-a-bug"},
        )
        mock_feedback_manager.add_feedback.return_value = fb.id
        mock_feedback_manager.get_feedback.return_value = fb

        payload = {
            "task_id": "999",
            "feedback_type": "label_correction",
            "original_result": {"label": "bug"},
            "corrected_result": {"label": "not-a-bug"},
            "rating": 3,
            "comment": "Wrong label",
            "created_by": "reviewer",
        }

        response = client.post("/feedback", json=payload, headers=_headers())
        assert response.status_code == 200
        assert response.json()["feedback_type"] == "label_correction"

    def test_manager_add_returns_none_gives_500(self, client, mock_feedback_manager):
        fb = _make_feedback()
        mock_feedback_manager.add_feedback.return_value = fb.id
        mock_feedback_manager.get_feedback.return_value = None

        payload = {
            "task_id": "12345",
            "feedback_type": "general",
            "original_result": {"label": "bug"},
            "rating": 4,
            "comment": "Looks good",
            "created_by": "tester",
        }

        response = client.post("/feedback", json=payload, headers=_headers())
        assert response.status_code == 500


# ---------------------------------------------------------------------------
# GET /feedback/{feedback_id}
# ---------------------------------------------------------------------------

class TestGetFeedback:
    """Tests for GET /feedback/{feedback_id}."""

    def test_found(self, client, mock_feedback_manager):
        fb = _make_feedback(id="fb-001")
        mock_feedback_manager.get_feedback.return_value = fb

        response = client.get("/feedback/fb-001", headers=_headers())
        assert response.status_code == 200
        assert response.json()["id"] == "fb-001"

    def test_not_found(self, client, mock_feedback_manager):
        mock_feedback_manager.get_feedback.return_value = None

        response = client.get("/feedback/nonexistent", headers=_headers())
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /feedback/task/{task_id}
# ---------------------------------------------------------------------------

class TestGetTaskFeedback:
    """Tests for GET /feedback/task/{task_id}."""

    def test_returns_list(self, client, mock_feedback_manager):
        fb1 = _make_feedback(id="fb-1", task_id="task-42")
        fb2 = _make_feedback(id="fb-2", task_id="task-42", rating=FeedbackRating.EXCELLENT)
        mock_feedback_manager.get_feedback_by_task.return_value = [fb1, fb2]

        response = client.get("/feedback/task/task-42", headers=_headers())
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["id"] == "fb-1"

    def test_empty_list(self, client, mock_feedback_manager):
        mock_feedback_manager.get_feedback_by_task.return_value = []

        response = client.get("/feedback/task/no-feedback", headers=_headers())
        assert response.status_code == 200
        assert response.json() == []


# ---------------------------------------------------------------------------
# GET /feedback (list)
# ---------------------------------------------------------------------------

class TestListFeedback:
    """Tests for GET /feedback (list_feedback)."""

    def test_no_filters(self, client, mock_feedback_manager):
        resp_obj = _make_response()
        mock_feedback_manager.list_feedback.return_value = [resp_obj]

        response = client.get("/feedback", headers=_headers())
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1

    def test_with_type_filter(self, client, mock_feedback_manager):
        mock_feedback_manager.list_feedback.return_value = []

        response = client.get("/feedback?feedback_type=false_positive", headers=_headers())
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_with_rating_filter(self, client, mock_feedback_manager):
        resp_obj = _make_response(rating=FeedbackRating.EXCELLENT)
        mock_feedback_manager.list_feedback.return_value = [resp_obj]

        response = client.get("/feedback?rating=5", headers=_headers())
        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_pagination(self, client, mock_feedback_manager):
        mock_feedback_manager.list_feedback.return_value = []

        response = client.get("/feedback?limit=10&offset=20", headers=_headers())
        assert response.status_code == 200
        data = response.json()
        assert data["offset"] == 20
        assert data["limit"] == 10


# ---------------------------------------------------------------------------
# POST /feedback/{feedback_id}/review
# ---------------------------------------------------------------------------

class TestReviewFeedback:
    """Tests for POST /feedback/{feedback_id}/review."""

    def test_happy_path(self, client, mock_feedback_manager):
        fb = _make_feedback(reviewed=True, reviewed_by="admin")
        mock_feedback_manager.review_feedback.return_value = True
        mock_feedback_manager.get_feedback.return_value = fb

        response = client.post(
            "/feedback/fb-review/review",
            json={"reviewed_by": "admin"},
            headers=_headers(),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["reviewed"] is True
        assert data["reviewed_by"] == "admin"

    def test_not_found(self, client, mock_feedback_manager):
        mock_feedback_manager.review_feedback.return_value = False

        response = client.post(
            "/feedback/missing/review",
            json={"reviewed_by": "admin"},
            headers=_headers(),
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /feedback/stats/summary
# ---------------------------------------------------------------------------

class TestGetFeedbackStatistics:
    """Tests for GET /feedback/stats/summary."""

    def test_returns_stats(self, client, mock_feedback_manager):
        mock_feedback_manager.get_statistics.return_value = {
            "total_feedback": 10,
            "by_type": {"general": 7, "label_correction": 3},
            "by_rating": {4: 6, 5: 4},
            "reviewed_count": 5,
            "correction_ratio": 0.3,
            "positive_ratio": 1.0,
        }

        response = client.get("/feedback/stats/summary", headers=_headers())
        assert response.status_code == 200
        data = response.json()
        assert data["total_feedback"] == 10
        assert data["by_type"] == {"general": 7, "label_correction": 3}
        assert data["positive_ratio"] == 1.0
