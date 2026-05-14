"""
Analytics router — ticket statistics, scoped by role.
Users see own stats; admins see global stats.
"""

from app.application.services.analytics_service import AnalyticsService
from app.dependencies import get_current_user
from app.domain.entities.user import User
from app.infrastructure.database import get_db_session
from app.presentation.schemas.admin_schemas import AnalyticsResponse
from app.repositories.ticket_repository import TicketRepository
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def _get_analytics_service(
    session: AsyncSession = Depends(get_db_session),
) -> AnalyticsService:
    return AnalyticsService(ticket_repo=TicketRepository(session))


@router.get(
    "",
    response_model=AnalyticsResponse,
    summary="Ticket analytics — own stats for users, global for admins",
)
async def get_analytics(
    current_user: User = Depends(get_current_user),
    service: AnalyticsService = Depends(_get_analytics_service),
):
    if current_user.is_staff:  # use the property already on User entity
        stats = await service.get_global_stats()
        scope = "global"
    else:
        stats = await service.get_user_stats(current_user.id)
        scope = "user"

    return AnalyticsResponse(
        total_tickets=stats["total"],
        ai_processing=stats["ai_processing"],
        by_status=stats["by_status"],
        by_category=stats["by_category"],
        by_priority=stats["by_priority"],
        scope=scope,
    )
