"""
Tickets router — user-facing ticket operations.
Ownership enforced at the service layer; 404 returned for not-found OR not-owner.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.ticket_service import TicketService
from app.dependencies import PaginationParams, get_current_user
from app.domain.entities.user import User
from app.infrastructure.ai.openai_client import AIServiceError
from app.infrastructure.database import get_db_session
from app.presentation.schemas.ticket_schemas import (
    AIErrorDetail,
    CreateTicketRequest,
    TicketListResponse,
    TicketResponse,
)
from app.repositories.ticket_repository import TicketRepository

router = APIRouter(prefix="/tickets", tags=["Tickets"])


def _get_ticket_service(
    session: AsyncSession = Depends(get_db_session),
) -> TicketService:
    return TicketService(ticket_repo=TicketRepository(session))


@router.post(
    "",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a support ticket for AI triage",
    responses={
        503: {
            "description": "AI service unavailable — ticket saved without classification",
            "model": AIErrorDetail,
        }
    },
)
async def create_ticket(
    body: CreateTicketRequest,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(_get_ticket_service),
):
    try:
        ticket = await service.create_ticket(
            user_id=current_user.id,
            message=body.message,
        )
        return TicketResponse.model_validate(ticket)
    except AIServiceError as e:
        # The ticket was saved (service raises after persisting)
        # Return 503 with structured error per spec
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "AI_SERVICE_UNAVAILABLE",
                    "message": str(e),
                    "retry_after": e.retry_after,
                }
            },
        )


@router.get(
    "",
    response_model=TicketListResponse,
    summary="List your own tickets (paginated)",
)
async def list_tickets(
    current_user: User = Depends(get_current_user),
    pagination: PaginationParams = Depends(),
    service: TicketService = Depends(_get_ticket_service),
):
    tickets, total = await service.get_user_tickets(
        current_user.id,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return TicketListResponse(
        items=[TicketResponse.model_validate(t) for t in tickets],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get(
    "/{ticket_id}",
    response_model=TicketResponse,
    summary="Get a specific ticket (owner only)",
)
async def get_ticket(
    ticket_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(_get_ticket_service),
):
    ticket = await service.get_ticket_for_owner(ticket_id, current_user.id)
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return TicketResponse.model_validate(ticket)