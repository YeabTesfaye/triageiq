"""
Analytics router — ticket statistics, scoped by role.
Users see own stats; admins see global stats.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.analytics_service import AnalyticsService
from app.dependencies import get_current_user, require_roles
from app.domain.entities.user import User
from app.domain.enums import Role
from app.infrastructure.database import get_db_session
from app.presentation.schemas.admin_schemas import AnalyticsResponse
from app.repositories.ticket_repository import TicketRepository

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
    is_admin = Role(current_user.role) in (
        Role.ADMIN, Role.SUPERADMIN, Role.MODERATOR
    )

    if is_admin:
        stats = await service.get_global_stats()
    else:
        stats = await service.get_user_stats(current_user.id)

    return AnalyticsResponse(
        total_tickets=stats.get("total", 0),
        by_category=stats.get("by_category", {}),
        by_priority=stats.get("by_priority", {}),
        by_status=stats.get("by_status", {}),
    )