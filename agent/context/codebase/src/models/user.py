"""
models/user.py — User data model for Project Telos.

Defines the canonical User representation used across the API, database
layer, and serialisation. All PII fields are marked for audit logging.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import ClassVar


class UserRole(str, Enum):
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"
    SERVICE = "service"  # machine-to-machine service accounts


class AccountStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"
    DELETED = "deleted"


@dataclass
class UserModel:
    """
    Canonical user record. Maps directly to the `users` table.

    PII fields (marked with # PII):
      - email
      - display_name
      - avatar_url
    """

    # Immutable identity
    id: str                                    # UUID v4, set at creation
    email: str                                 # PII — lowercase, validated
    created_at: datetime

    # Mutable profile
    display_name: str = ""                     # PII
    avatar_url: str = ""                       # PII
    role: UserRole = UserRole.MEMBER
    status: AccountStatus = AccountStatus.PENDING_VERIFICATION

    # Auth
    hashed_password: str = ""                 # bcrypt hash, never serialised to API
    mfa_enabled: bool = False
    mfa_secret: str = ""                      # TOTP secret, never serialised to API

    # Metadata
    last_login_at: datetime | None = None
    failed_login_count: int = 0
    updated_at: datetime | None = None
    tags: list[str] = field(default_factory=list)

    # Class-level constraints
    _EMAIL_RE: ClassVar[re.Pattern] = re.compile(
        r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    )
    _MAX_DISPLAY_NAME_LEN: ClassVar[int] = 120

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        self.email = self.email.lower().strip()
        if not self._EMAIL_RE.match(self.email):
            raise ValueError(f"Invalid email address: {self.email!r}")
        if len(self.display_name) > self._MAX_DISPLAY_NAME_LEN:
            raise ValueError(
                f"display_name exceeds {self._MAX_DISPLAY_NAME_LEN} characters"
            )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_api_dict(self) -> dict:
        """
        Serialise to a safe dict for API responses.
        Never includes hashed_password, mfa_secret, or failed_login_count.
        """
        return {
            "id": self.id,
            "email": self.email,
            "display_name": self.display_name,
            "avatar_url": self.avatar_url,
            "role": self.role.value,
            "status": self.status.value,
            "mfa_enabled": self.mfa_enabled,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "tags": self.tags,
        }

    @classmethod
    def from_db_row(cls, row: dict) -> UserModel:
        """Construct from an asyncpg row (all columns present)."""
        return cls(
            id=str(row["id"]),
            email=row["email"],
            display_name=row.get("display_name", ""),
            avatar_url=row.get("avatar_url", ""),
            role=UserRole(row.get("role", "member")),
            status=AccountStatus(row.get("status", "pending_verification")),
            hashed_password=row.get("hashed_password", ""),
            mfa_enabled=bool(row.get("mfa_enabled", False)),
            mfa_secret=row.get("mfa_secret", ""),
            last_login_at=row.get("last_login_at"),
            failed_login_count=int(row.get("failed_login_count", 0)),
            created_at=row["created_at"],
            updated_at=row.get("updated_at"),
            tags=list(row.get("tags") or []),
        )

    # ------------------------------------------------------------------
    # Business logic
    # ------------------------------------------------------------------

    def is_locked_out(self) -> bool:
        """Account is locked after 10 consecutive failed login attempts."""
        return self.failed_login_count >= 10

    def can_access(self, required_role: UserRole) -> bool:
        """
        Hierarchical role check:
          admin > member > viewer
          service accounts can only access service-level resources
        """
        hierarchy = [UserRole.VIEWER, UserRole.MEMBER, UserRole.ADMIN]
        if self.role == UserRole.SERVICE or required_role == UserRole.SERVICE:
            return self.role == required_role
        try:
            return hierarchy.index(self.role) >= hierarchy.index(required_role)
        except ValueError:
            return False
