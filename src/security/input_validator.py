"""Input validator for security-related inputs."""

from typing import Any

from loguru import logger


class InputValidator:
    """Validator for security-critical inputs."""

    @staticmethod
    def validate_task_no(task_no: Any) -> bool:
        """
        Validate taskNo format.

        TaskNo must be:
        - A string or numeric type
        - Contains only digits
        - Length between 7 and 10 characters

        Args:
            task_no: Task number to validate

        Returns:
            True if task_no is valid, False otherwise
        """
        if task_no is None:
            logger.debug("TaskNo is None")
            return False

        # Convert to string for consistent validation
        task_str = str(task_no).strip()

        # Check length
        if not (7 <= len(task_str) <= 10):
            logger.debug(f"TaskNo length {len(task_str)} is out of range (7-10)")
            return False

        # Check if all characters are digits
        if not task_str.isdigit():
            logger.debug(f"TaskNo '{task_str}' contains non-digit characters")
            return False

        logger.debug(f"TaskNo '{task_str}' is valid")
        return True

    @staticmethod
    def validate_token(token: str | None) -> bool:
        """
        Validate token format.

        Token must be:
        - A non-empty string
        - Length between 10 and 200 characters

        Args:
            token: Token to validate

        Returns:
            True if token is valid, False otherwise
        """
        if token is None:
            logger.debug("Token is None")
            return False

        token_str = str(token).strip()

        if not (10 <= len(token_str) <= 200):
            logger.debug(f"Token length {len(token_str)} is out of range (10-200)")
            return False

        logger.debug("Token format is valid")
        return True
