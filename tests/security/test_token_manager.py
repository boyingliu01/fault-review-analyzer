"""Tests for TokenManager."""

from datetime import datetime, timedelta, timezone

import pytest

from src.security.token_manager import TokenManager


class TestTokenManager:
    """Tests for TokenManager class."""

    class TestInitialization:
        """Tests for initialization."""

        def test_default_initialization(self):
            """Test default initialization."""
            manager = TokenManager()
            assert manager.get_expiration_days() == TokenManager.DEFAULT_EXPIRATION_DAYS
            assert manager.get_rotation_alert_days() == TokenManager.DEFAULT_ROTATION_ALERT_DAYS

        def test_custom_initialization(self):
            """Test custom expiration and alert settings."""
            expiration = 60
            alert = 15
            manager = TokenManager(expiration_days=expiration, rotation_alert_days=alert)
            assert manager.get_expiration_days() == expiration
            assert manager.get_rotation_alert_days() == alert

    class TestIsTokenExpired:
        """Tests for is_token_expired method."""

        @pytest.mark.parametrize(
            "days_ago,expected",
            [
                (TokenManager.DEFAULT_EXPIRATION_DAYS + 1, True),  # Expired
                (TokenManager.DEFAULT_EXPIRATION_DAYS + 0.001, True),  # Expired by a little
                (TokenManager.DEFAULT_EXPIRATION_DAYS - 1, False),  # Still valid
                (0, False),  # Just created
            ],
        )
        def test_is_token_expired(self, days_ago, expected):
            """Test is_token_expired with various creation dates."""
            manager = TokenManager()
            created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
            assert manager.is_token_expired("test-token", created_at) == expected

        def test_is_token_expired_with_none_created_at(self):
            """Test is_token_expired with None created_at."""
            manager = TokenManager()
            assert manager.is_token_expired("test-token", None) is False

    class TestNeedsRotationAlert:
        """Tests for needs_rotation_alert method."""

        def test_needs_rotation_alert_when_near_expiration(self):
            """Test needs_rotation_alert when token is near expiration."""
            manager = TokenManager()
            # Created at (expiration_days - alert_days - 1) days ago
            created_at = (
                datetime.now(timezone.utc)
                - timedelta(days=manager.get_expiration_days() - manager.get_rotation_alert_days() - 1)
            )
            assert manager.needs_rotation_alert("test-token", created_at) is False

            # Created at exactly (expiration_days - alert_days) days ago
            created_at = (
                datetime.now(timezone.utc)
                - timedelta(days=manager.get_expiration_days() - manager.get_rotation_alert_days())
            )
            assert manager.needs_rotation_alert("test-token", created_at) is True

            # Created at (expiration_days - alert_days + 1) days ago
            created_at = (
                datetime.now(timezone.utc)
                - timedelta(days=manager.get_expiration_days() - manager.get_rotation_alert_days() + 1)
            )
            assert manager.needs_rotation_alert("test-token", created_at) is True

        def test_needs_rotation_alert_with_none_created_at(self):
            """Test needs_rotation_alert with None created_at."""
            manager = TokenManager()
            assert manager.needs_rotation_alert("test-token", None) is False

    class TestGetTokenRemainingDays:
        """Tests for get_token_remaining_days method."""

        def test_get_token_remaining_days(self):
            """Test get_token_remaining_days with valid created_at."""
            manager = TokenManager()
            days_ago = 10
            created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
            remaining = manager.get_token_remaining_days(created_at)
            assert remaining is not None
            assert 0 < remaining <= manager.get_expiration_days()

        def test_get_token_remaining_days_with_none_created_at(self):
            """Test get_token_remaining_days with None created_at."""
            manager = TokenManager()
            assert manager.get_token_remaining_days(None) is None

    class TestCustomExpirationSettings:
        """Tests with custom expiration settings."""

        def test_custom_expiration(self):
            """Test with custom expiration days."""
            manager = TokenManager(expiration_days=90, rotation_alert_days=15)
            # At 80 days ago (10 days before expiration, 25 days after alert threshold)
            created_at = datetime.now(timezone.utc) - timedelta(days=80)
            assert manager.is_token_expired("test-token", created_at) is False
            # This will trigger an alert because we passed the alert date (90-15=75 days ago)
            # 80 days ago is before (earlier) than 75 days ago, so alert should be triggered
            assert manager.needs_rotation_alert("test-token", created_at) is True

            created_at = datetime.now(timezone.utc) - timedelta(days=80)
            remaining = manager.get_token_remaining_days(created_at)
            assert remaining is not None
            # Allow floating-point tolerance (~10 days remaining from 90-day expiration)
            assert remaining == pytest.approx(10.0, rel=1e-6)
