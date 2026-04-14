"""
Tickets router — user-facing ticket operations.
Ownership enforced at the service layer; 404 returned for not-found OR not-owner.
"""

import uuid

from app.application.services.ticket_service import TicketService
from app.dependencies import PaginationParams, get_current_user
from app.domain.entities.user import User
from app.infrastructure.database import get_db_session
from app.presentation.schemas.ticket_schemas import (
    CreateTicketRequest,
    CreateTicketResponse,
    TicketListResponse,
    TicketResponse,
    UpdateTicketStatusRequest,
)
from app.repositories.ticket_repository import TicketRepository
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/tickets", tags=["Tickets"])


def _get_ticket_service(
    session: AsyncSession = Depends(get_db_session),
) -> TicketService:
    return TicketService(ticket_repo=TicketRepository(session))


@router.post(
    "",
    response_model=CreateTicketResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a support ticket for AI triage",
)
async def create_ticket(
    body: CreateTicketRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(_get_ticket_service),
):
    ticket = await service.create_ticket_pending(
        user_id=current_user.id,
        message=body.message,
    )
    background_tasks.add_task(service.run_ai_analysis, ticket.id)
    return CreateTicketResponse.from_ticket(ticket)


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


@router.delete(
    "/{ticket_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a ticket (owner only)",
)
async def delete_ticket(
    ticket_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(_get_ticket_service),
):
    deleted = await service.delete_ticket_for_owner(
        ticket_id=ticket_id,
        user_id=current_user.id,
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    return None


@router.patch(
    "/{ticket_id}",
    response_model=TicketResponse,
    summary="Update ticket status (owner only)",
)
async def update_ticket_status(
    ticket_id: uuid.UUID,
    body: UpdateTicketStatusRequest,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(_get_ticket_service),
):
    ticket = await service.update_ticket_status_for_owner(
        ticket_id=ticket_id,
        user_id=current_user.id,
        status=body.status,
    )

    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    return TicketResponse.model_validate(ticket)
