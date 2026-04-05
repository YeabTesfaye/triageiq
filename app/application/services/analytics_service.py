"""
Analytics service — ticket statistics, scoped by role.
Users see only their own stats; admins see global stats.
"""
import uuid
from typing import Any,Dict

from app.repositories.ticket_repository import TicketRepository

class AnalyticsService:
    def __init__(self, ticket_repo: TicketRepository) -> None:
        self._tickets = ticket_repo
 
    async def get_user_stats(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """Stats for a specific user — shown to the user themselves."""
        return await self._tickets.get_stats_for_user(user_id)
 
    async def get_global_stats(self) -> Dict[str, Any]:
        """Global stats — admin/superadmin only."""
        return await self._tickets.get_global_stats()