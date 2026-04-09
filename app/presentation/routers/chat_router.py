from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.chat_service import ChatError, ChatService
from app.dependencies import get_current_user
from app.domain.entities.user import Role, User
from app.infrastructure.database import get_db_session
from app.presentation.schemas.chat_schemas import (
    MessageListResponse,
    MessageResponse,
    SendMessageRequest,
    SendMessageResponse,
)
from app.repositories.chat_repository import ChatRepository
from app.repositories.ticket_repository import TicketRepository

router = APIRouter(prefix="/chat", tags=["chat"])


@dataclass
class PaginationParams:
    limit: int = 50
    offset: int = 0


def _is_admin(user: User) -> bool:
    return user.role in (Role.ADMIN, Role.SUPERADMIN, Role.MODERATOR)


def _get_chat_service(db: AsyncSession = Depends(get_db_session)) -> ChatService:
    return ChatService(
        chat_repo=ChatRepository(db),
        ticket_repo=TicketRepository(db),
    )


_ERROR_CODE_TO_STATUS: dict[str, int] = {
    "TICKET_NOT_FOUND": status.HTTP_404_NOT_FOUND,
}


def _chat_error_to_http(exc: ChatError) -> HTTPException:
    http_status = _ERROR_CODE_TO_STATUS.get(exc.code, status.HTTP_400_BAD_REQUEST)
    return HTTPException(status_code=http_status, detail=str(exc))


@router.post(
    "/{ticket_id}/messages",
    response_model=SendMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send a message — AI replies automatically",
)
async def send_message(
    ticket_id: uuid.UUID,
    body: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(_get_chat_service),
) -> SendMessageResponse:
    try:
        user_msg, ai_msg = await service.send_message(
            ticket_id=ticket_id,
            sender_id=current_user.id,
            sender_role=current_user.role,
            content=body.content,
            is_admin=_is_admin(current_user),
        )
    except ChatError as exc:
        raise _chat_error_to_http(exc) from exc

    return SendMessageResponse(
        user_message=MessageResponse.model_validate(user_msg),
        ai_reply=MessageResponse.model_validate(ai_msg) if ai_msg else None,
    )


@router.get(
    "/{ticket_id}/messages",
    response_model=MessageListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all messages on a ticket thread",
)
async def list_messages(
    ticket_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(_get_chat_service),
    pagination: PaginationParams = Depends(),
) -> MessageListResponse:
    try:
        messages, total = await service.get_messages(
            ticket_id=ticket_id,
            requester_id=current_user.id,
            is_admin=_is_admin(current_user),
            limit=pagination.limit,
            offset=pagination.offset,
        )
    except ChatError as exc:
        raise _chat_error_to_http(exc) from exc

    return MessageListResponse(
        items=[MessageResponse.model_validate(m) for m in messages],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )