"""
Domain enumerations — the vocabulary of the system.
These are pure Python; no framework dependencies.
"""

from enum import Enum


class Role(str, Enum):
    """User roles in ascending privilege order."""

    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"

    @property
    def privilege_level(self) -> int:
        """Numeric level for hierarchy comparisons."""
        return {
            Role.USER: 0,
            Role.MODERATOR: 1,
            Role.ADMIN: 2,
            Role.SUPERADMIN: 3,
        }[self]

    def can_promote_to(self, target: "Role") -> bool:
        """SUPERADMIN cannot promote anyone to SUPERADMIN via API."""
        return target != Role.SUPERADMIN

    def outranks(self, other: "Role") -> bool:
        return self.privilege_level > other.privilege_level


class UserStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BANNED = "banned"


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketCategory(str, Enum):
    BILLING = "billing"
    TECHNICAL = "technical"
    GENERAL = "general"


class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AuditAction(str, Enum):
    """Every distinct admin action that must be audited."""

    USER_ROLE_CHANGE = "user.role_change"
    USER_STATUS_CHANGE = "user.status_change"
    USER_DELETE = "user.delete"
    TICKET_STATUS_CHANGE = "ticket.status_change"
    TICKET_DELETE = "ticket.delete"
    TOKEN_INVALIDATION = "token.invalidation"
