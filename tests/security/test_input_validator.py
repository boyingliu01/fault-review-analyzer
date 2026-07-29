"""Tests for InputValidator."""

import pytest

from src.security.input_validator import InputValidator


class TestInputValidator:
    """Tests for InputValidator class."""

    class TestValidateTaskNo:
        """Tests for validate_task_no method."""

        @pytest.mark.parametrize(
            "task_no,expected",
            [
                # Valid cases
                ("11745664", True),
                ("11751534", True),
                (11745664, True),
                ("1234567", True),  # 7 digits
                ("1234567890", True),  # 10 digits
                (" 11745664 ", True),  # with whitespace
                # Invalid cases
                (None, False),
                ("", False),
                (" ", False),
                ("abc123", False),  # contains letters
                ("123abc", False),  # contains letters
                ("123-456", False),  # contains hyphen
                ("123456", False),  # too short (6 digits)
                ("12345678901", False),  # too long (11 digits)
                ("123 4567", False),  # contains space
            ],
        )
        def test_validate_task_no(self, task_no, expected):
            """Test validate_task_no with various inputs."""
            assert InputValidator.validate_task_no(task_no) == expected

    class TestValidateToken:
        """Tests for validate_token method."""

        @pytest.mark.parametrize(
            "token,expected",
            [
                # Valid cases
                ("valid-token-12345", True),
                ("x" * 10, True),  # minimum length
                ("x" * 200, True),  # maximum length
                ("  valid-token-with-whitespace  ", True),  # with whitespace
                # Invalid cases
                (None, False),
                ("", False),
                (" ", False),
                ("x" * 9, False),  # too short
                ("x" * 201, False),  # too long
            ],
        )
        def test_validate_token(self, token, expected):
            """Test validate_token with various inputs."""
            assert InputValidator.validate_token(token) == expected
