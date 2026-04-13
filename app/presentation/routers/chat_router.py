"""
Chat router — 3 endpoints.

  POST /{ticket_id}/messages       send a message; AI reply via Firebase
  GET  /{ticket_id}/thread         open chat window (ticket + messages, 1 call)
  GET  /{ticket_id}/messages       load older messages (cursor pagination)
"""
from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.chat_service import ChatError, ChatService
from app.dependencies import get_current_user
from app.domain.entities.user import User
from app.infrastructure.database import get_db_session, get_session_factory
from app.presentation.schemas.chat_schemas import (
    MessageListResponse,
    MessageResponse,
    SendMessageRequest,
    ThreadResponse,
    TicketSummary,
)
from app.repositories.chat_repository import ChatRepository
from app.repositories.ticket_repository import TicketRepository

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


# ------------------------------------------------------------------
# Dependency
# ------------------------------------------------------------------

def _get_chat_service(db: AsyncSession = Depends(get_db_session)) -> ChatService:
    return ChatService(
        chat_repo=ChatRepository(db),
        ticket_repo=TicketRepository(db),
        session_factory=get_session_factory(),
    )


# ------------------------------------------------------------------
# Error map  (Open/Closed: add codes, never touch the converter)
# ------------------------------------------------------------------

_ERROR_CODE_TO_STATUS: dict[str, int] = {
    "TICKET_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "TICKET_CLOSED":    status.HTTP_409_CONFLICT,
    "ACCESS_DENIED":    status.HTTP_403_FORBIDDEN,
}


def _chat_error_to_http(exc: ChatError) -> HTTPException:
    http_status = _ERROR_CODE_TO_STATUS.get(exc.code, status.HTTP_400_BAD_REQUEST)
    return HTTPException(status_code=http_status, detail=str(exc))


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _build_list_response(
    messages,
    total: int,
    limit: int,
) -> dict:
    """Shared pagination logic for both list endpoints."""
    next_cursor = messages[0].id if messages and len(messages) == limit else None
    return dict(
        messages=[MessageResponse.model_validate(m) for m in messages],
        total=total,
        limit=limit,
        has_more=next_cursor is not None,
        next_cursor=next_cursor,
    )


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@router.post(
    "/{ticket_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send a message — AI reply delivered via Firebase",
)
async def send_message(
    ticket_id: uuid.UUID,
    body: SendMessageRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(_get_chat_service),
) -> MessageResponse:
    """
    Persists the user message and returns HTTP 201 immediately (<50ms).
    The AI reply is generated in the background and pushed to Firebase —
    subscribe to the Firebase thread, do not poll this endpoint.

    Response is a single MessageResponse (not a wrapper).
    is_ai will always be false here since this is the user's own message.
    """
    try:
        user_msg = await service.send_message(
            ticket_id=ticket_id,
            sender_id=current_user.id,
            sender_role=current_user.role,
            content=body.content,
            is_admin=current_user.is_staff,
            background_tasks=background_tasks,
        )
    except ChatError as exc:
        raise _chat_error_to_http(exc) from exc

    return MessageResponse.model_validate(user_msg)


@router.get(
    "/{ticket_id}/thread",
    response_model=ThreadResponse,
    status_code=status.HTTP_200_OK,
    summary="Open chat window — ticket context + latest messages in one call",
)
async def get_thread(
    ticket_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100, description="Initial message page size."),
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(_get_chat_service),
) -> ThreadResponse:
    """
    The 'open chat window' endpoint.

    Returns the ticket header (status, subject, priority, category) alongside
    the latest messages in a single HTTP call. The frontend calls this once
    when the user opens a support thread — no waterfall requests needed.

    To load older messages, use GET /{ticket_id}/messages?before_id=<next_cursor>.
    """
    try:
        ticket, messages, total = await service.get_thread(
            ticket_id=ticket_id,
            requester_id=current_user.id,
            is_admin=current_user.is_staff,
            limit=limit,
        )
    except ChatError as exc:
        raise _chat_error_to_http(exc) from exc

    pagination = _build_list_response(messages, total, limit)

    return ThreadResponse(
        ticket=TicketSummary(
            id=ticket.id,
            subject=ticket.message,   # original ticket description
            status=ticket.status,
            category=ticket.category,
            priority=ticket.priority,
            created_at=ticket.created_at,
        ),
        **pagination,
    )


@router.get(
    "/{ticket_id}/messages",
    response_model=MessageListResponse,
    status_code=status.HTTP_200_OK,
    summary="Load older messages — cursor pagination",
)
async def list_messages(
    ticket_id: uuid.UUID,
    before_id: uuid.UUID | None = Query(
        None,
        description=(
            "Cursor for loading older messages. "
            "Pass next_cursor from the previous response."
        ),
    ),
    limit: int = Query(50, ge=1, le=100, description="Page size (1-100)."),
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(_get_chat_service),
) -> MessageListResponse:
    """
    Loads older messages for infinite-scroll / 'load more' UI.

    Typical flow:
      1. GET /chat/{id}/thread             <- open chat window
      2. User scrolls up, tap 'load more'
      3. GET /chat/{id}/messages?before_id=<next_cursor from step 1>
      4. Repeat until has_more=false.
    """
    try:
        messages, total = await service.get_messages(
            ticket_id=ticket_id,
            requester_id=current_user.id,
            is_admin=current_user.is_staff,
            limit=limit,
            before_id=before_id,
        )
    except ChatError as exc:
        raise _chat_error_to_http(exc) from exc

    return MessageListResponse(**_build_list_response(messages, total, limit))


