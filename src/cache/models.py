from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


class CacheStatus(str, Enum):
    VALID = "valid"
    EXPIRED = "expired"
    NOT_EXISTS = "not_exists"


class CacheEntry(BaseModel):
    task_id: int
    data: dict[str, Any]
    created_at: datetime
    expires_at: datetime

    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at
