"""Token management with expiration detection and rotation alerts."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from loguru import logger


class TokenManager:
    """Manages token lifecycle including expiration detection and rotation alerts."""

    # Default token expiration threshold (30 days)
    DEFAULT_EXPIRATION_DAYS = 30
    # Default rotation alert threshold (7 days before expiration)
    DEFAULT_ROTATION_ALERT_DAYS = 7

    def __init__(
        self,
        expiration_days: int = DEFAULT_EXPIRATION_DAYS,
        rotation_alert_days: int = DEFAULT_ROTATION_ALERT_DAYS,
    ):
        """
        Initialize TokenManager.

        Args:
            expiration_days: Token expiration period in days
            rotation_alert_days: Days before expiration to start alerting
        """
        self.expiration_days = expiration_days
        self.rotation_alert_days = rotation_alert_days
        logger.debug(
            f"TokenManager initialized with expiration: {expiration_days} days, "
            f"alert: {rotation_alert_days} days"
        )

    def is_token_expired(self, token: str, created_at: Optional[datetime] = None) -> bool:
        """
        Check if a token has expired.

        Args:
            token: Token to check (used for logging purposes)
            created_at: Token creation timestamp

        Returns:
            True if token has expired, False otherwise
        """
        if created_at is None:
            logger.debug("Token created_at timestamp is None")
            return False

        expiration_date = created_at + timedelta(days=self.expiration_days)
        is_expired = datetime.now(timezone.utc) > expiration_date

        logger.debug(
            f"Token {'is expired' if is_expired else 'is valid'} - "
            f"created: {created_at}, expires: {expiration_date}"
        )

        return is_expired

    def needs_rotation_alert(self, token: str, created_at: Optional[datetime] = None) -> bool:
        """
        Check if a token needs rotation alert.

        Args:
            token: Token to check (used for logging purposes)
            created_at: Token creation timestamp

        Returns:
            True if token needs rotation alert, False otherwise
        """
        if created_at is None:
            logger.debug("Token created_at timestamp is None")
            return False

        alert_date = (
            created_at
            + timedelta(days=self.expiration_days)
            - timedelta(days=self.rotation_alert_days)
        )
        needs_alert = datetime.now(timezone.utc) >= alert_date

        logger.debug(
            f"Token rotation alert {'needed' if needs_alert else 'not needed'} - "
            f"alert date: {alert_date}"
        )

        return needs_alert

    def get_token_remaining_days(self, created_at: Optional[datetime] = None) -> Optional[float]:
        """
        Get remaining days until token expiration.

        Args:
            created_at: Token creation timestamp

        Returns:
            Remaining days or None if created_at is None
        """
        if created_at is None:
            return None

        remaining = (
            created_at + timedelta(days=self.expiration_days) - datetime.now(timezone.utc)
        ).total_seconds() / (24 * 3600)

        return max(0.0, remaining)

    def get_rotation_alert_days(self) -> int:
        """Get rotation alert threshold in days."""
        return self.rotation_alert_days

    def get_expiration_days(self) -> int:
        """Get expiration period in days."""
        return self.expiration_days
