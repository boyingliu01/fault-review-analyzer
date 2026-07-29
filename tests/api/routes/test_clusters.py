"""Unit tests for /clusters routes."""

import pytest
from fastapi.testclient import TestClient

from src.api.server import create_app


@pytest.fixture
def client():
    """Create test client with a valid token."""
    app = create_app(valid_tokens={"test-token-123"})
    return TestClient(app)


def _headers() -> dict[str, str]:
    return {"X-API-Token": "test-token-123"}


# ---------------------------------------------------------------------------
# GET /clusters
# ---------------------------------------------------------------------------


class TestGetClusters:
    """Tests for GET /clusters endpoint."""

    def test_empty_cache(self, client):
        """When _cluster_cache is empty, returns zero counts."""
        import src.api.routes.clusters as cluster_routes

        cluster_routes._cluster_cache = {}

        response = client.get("/clusters", headers=_headers())
        assert response.status_code == 200
        data = response.json()
        assert data["total_clusters"] == 0
        assert data["total_tasks"] == 0
        assert data["noise_count"] == 0
        assert data["clusters"] == []

    def test_populated_cache_with_noise(self, client):
        """Cache with 2 clusters + noise cluster (-1)."""
        import src.api.routes.clusters as cluster_routes

        cluster_routes._cluster_cache = {
            0: {
                "size": 5,
                "label": "OOM issues",
                "keywords": ["memory", "heap"],
                "metadata": {"confidence": 0.9},
            },
            1: {
                "size": 3,
                "label": "Timeout issues",
                "keywords": ["timeout", "connection"],
                "metadata": {},
            },
            -1: {"size": 2, "label": "noise"},
        }

        response = client.get("/clusters", headers=_headers())
        assert response.status_code == 200
        data = response.json()
        assert data["total_clusters"] == 2
        assert data["total_tasks"] == 10
        assert data["noise_count"] == 2
        assert len(data["clusters"]) == 2
        assert {c["cluster_id"] for c in data["clusters"]} == {0, 1}

    def test_populated_cache_no_noise(self, client):
        """Cache with only regular clusters, no noise cluster -1."""
        import src.api.routes.clusters as cluster_routes

        cluster_routes._cluster_cache = {
            10: {"size": 7, "label": "Config", "keywords": ["env"], "metadata": {}},
        }

        response = client.get("/clusters", headers=_headers())
        data = response.json()
        assert data["total_clusters"] == 1
        assert data["total_tasks"] == 7
        assert data["noise_count"] == 0

    def test_cluster_info_fields(self, client):
        """ClusterInfo objects include label, keywords, metadata fields."""
        import src.api.routes.clusters as cluster_routes

        cluster_routes._cluster_cache = {
            5: {
                "size": 10,
                "label": "Network Errors",
                "keywords": ["dns", "tcp", "retry"],
                "metadata": {"pattern": "intermittent"},
            },
        }

        response = client.get("/clusters", headers=_headers())
        data = response.json()
        cluster = data["clusters"][0]
        assert cluster["cluster_id"] == 5
        assert cluster["size"] == 10
        assert cluster["label"] == "Network Errors"
        assert cluster["keywords"] == ["dns", "tcp", "retry"]
        assert cluster["metadata"] == {"pattern": "intermittent"}


# ---------------------------------------------------------------------------
# GET /clusters/{cluster_id}
# ---------------------------------------------------------------------------


class TestGetClusterDetail:
    """Tests for GET /clusters/{cluster_id} endpoint."""

    def test_found_with_tasks(self, client):
        """Cluster exists and has tasks attached."""
        import src.api.routes.clusters as cluster_routes

        cluster_routes._cluster_cache = {
            42: {
                "size": 2,
                "label": "Security",
                "description": "Security-related issues",
                "keywords": ["xss", "injection"],
                "metadata": {"severity": "high"},
                "tasks": [
                    {
                        "task_id": "1001",
                        "title": "XSS in form",
                        "description": "no escaping",
                        "similarity_score": 0.95,
                    },
                    {
                        "task_id": "1002",
                        "title": "SQL injection",
                        "description": "unsanitized input",
                        "similarity_score": 0.88,
                    },
                ],
            },
        }

        response = client.get("/clusters/42", headers=_headers())
        assert response.status_code == 200
        data = response.json()
        assert data["cluster_id"] == 42
        assert data["size"] == 2
        assert data["label"] == "Security"
        assert data["keywords"] == ["xss", "injection"]
        assert len(data["tasks"]) == 2
        assert data["tasks"][0]["task_id"] == "1001"
        assert data["tasks"][0]["similarity_score"] == 0.95

    def test_not_found(self, client):
        """Cluster ID does not exist in cache."""
        import src.api.routes.clusters as cluster_routes

        cluster_routes._cluster_cache = {}

        response = client.get("/clusters/999", headers=_headers())
        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "ClusterNotFound"

    def test_not_found_when_cache_has_others(self, client):
        """Cache has data but the requested cluster_id is not in it."""
        import src.api.routes.clusters as cluster_routes

        cluster_routes._cluster_cache = {1: {"size": 1}}

        response = client.get("/clusters/99", headers=_headers())
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# update_cluster_cache
# ---------------------------------------------------------------------------


class TestUpdateClusterCache:
    """Tests for the update_cluster_cache helper."""

    def test_multiple_tasks_grouped(self):
        """Tasks are grouped by cluster_id, noise tasks map to -1."""
        import src.api.routes.clusters as cluster_routes

        cluster_routes.update_cluster_cache(
            {
                "tasks": [
                    {"task_id": "a", "cluster_id": 0, "title": "T1"},
                    {"task_id": "b", "cluster_id": 0, "title": "T2"},
                    {"task_id": "c", "cluster_id": 1, "title": "T3"},
                    {"task_id": "d", "cluster_id": -1, "title": "T4"},
                    {"task_id": "e", "cluster_id": -1, "title": "T5"},
                ],
            }
        )

        assert len(cluster_routes._cluster_cache) == 3
        assert cluster_routes._cluster_cache[0]["size"] == 2
        assert cluster_routes._cluster_cache[1]["size"] == 1
        assert cluster_routes._cluster_cache[-1]["size"] == 2

    def test_empty_tasks(self):
        """Empty tasks list produces empty cache."""
        import src.api.routes.clusters as cluster_routes

        cluster_routes.update_cluster_cache({"tasks": []})
        assert len(cluster_routes._cluster_cache) == 0
