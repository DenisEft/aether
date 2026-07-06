"""Conversation and message management endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.deps import CurrentActiveUser, DBDep
from app.models.conversations import Conversation, Message, MessageAttachment
from app.models.enums import ConversationStatus
from app.schemas.conversations import (
    ConversationCreate,
    ConversationResponse,
    ConversationUpdate,
    MessageCreate,
    MessageResponse,
    PaginatedMessagesResponse,
    QuickReplySuggestionsResponse,
)

router = APIRouter(tags=["conversations"])


# ── GET /conversations ────────────────────────────────────────


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    db: DBDep,
    current_user: CurrentActiveUser,
    status_filter: str | None = Query(None, alias="status"),
    channel_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> list[ConversationResponse]:
    """List conversations with optional filters."""
    where = Conversation.tenant_id == current_user.tenant_id
    if status_filter:
        where &= Conversation.status == status_filter
    if channel_id:
        where &= Conversation.channel_id == channel_id
    if user_id:
        where &= Conversation.user_id == user_id

    result = await db.execute(
        select(Conversation)
        .where(where)
        .order_by(Conversation.last_message_at.desc().nullslast(), Conversation.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    conversations = result.scalars().all()

    responses = []
    for c in conversations:
        # Count messages
        msg_count = await db.execute(
            select(func.count()).select_from(Message).where(Message.conversation_id == c.id)
        )
        count = msg_count.scalar() or 0
        responses.append(
            ConversationResponse(
                id=c.id,
                status=c.status.value if hasattr(c.status, "value") else c.status,
                subject=c.subject,
                external_user_id=c.external_user_id,
                user_id=c.user_id,
                channel_id=c.channel_id,
                state=c.state or {},
                meta_info=c.meta_info or {},
                message_count=count,
                last_message_at=c.last_message_at,
                created_at=c.created_at,
            )
        )
    return responses


# ── POST /conversations ───────────────────────────────────────


@router.post("/conversations", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    body: ConversationCreate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ConversationResponse:
    """Create a new conversation."""
    conv = Conversation(
        tenant_id=current_user.tenant_id,
        user_id=body.user_id,
        channel_id=body.channel_id,
        external_user_id=body.external_user_id,
        subject=body.subject,
        state=body.state or {},
        status=ConversationStatus.active,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)

    return ConversationResponse(
        id=conv.id,
        status=conv.status.value if hasattr(conv.status, "value") else conv.status,
        subject=conv.subject,
        external_user_id=conv.external_user_id,
        user_id=conv.user_id,
        channel_id=conv.channel_id,
        state=conv.state or {},
        meta_info=conv.meta_info or {},
        message_count=0,
        last_message_at=conv.last_message_at,
        created_at=conv.created_at,
    )


# ── GET /conversations/{conversation_id} ──────────────────────


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ConversationResponse:
    """Get conversation details."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == current_user.tenant_id,
        )
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    msg_count = await db.execute(
        select(func.count()).select_from(Message).where(Message.conversation_id == conv.id)
    )
    count = msg_count.scalar() or 0

    return ConversationResponse(
        id=conv.id,
        status=conv.status.value if hasattr(conv.status, "value") else conv.status,
        subject=conv.subject,
        external_user_id=conv.external_user_id,
        user_id=conv.user_id,
        channel_id=conv.channel_id,
        state=conv.state or {},
        meta_info=conv.meta_info or {},
        message_count=count,
        last_message_at=conv.last_message_at,
        created_at=conv.created_at,
    )


# ── PATCH /conversations/{conversation_id} ────────────────────


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: uuid.UUID,
    body: ConversationUpdate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ConversationResponse:
    """Update a conversation."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == current_user.tenant_id,
        )
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    if body.status is not None:
        conv.status = body.status.value if hasattr(body.status, "value") else body.status
    if body.subject is not None:
        conv.subject = body.subject
    if body.state is not None:
        conv.state = body.state

    await db.commit()
    await db.refresh(conv)

    msg_count = await db.execute(
        select(func.count()).select_from(Message).where(Message.conversation_id == conv.id)
    )
    count = msg_count.scalar() or 0

    return ConversationResponse(
        id=conv.id,
        status=conv.status.value if hasattr(conv.status, "value") else conv.status,
        subject=conv.subject,
        external_user_id=conv.external_user_id,
        user_id=conv.user_id,
        channel_id=conv.channel_id,
        state=conv.state or {},
        meta_info=conv.meta_info or {},
        message_count=count,
        last_message_at=conv.last_message_at,
        created_at=conv.created_at,
    )


# ── GET /conversations/{conversation_id}/messages ─────────────


@router.get("/conversations/{conversation_id}/messages", response_model=PaginatedMessagesResponse)
async def list_messages(
    conversation_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: str | None = None,
) -> PaginatedMessagesResponse:
    """List messages in a conversation."""
    # Verify conversation exists
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == current_user.tenant_id,
        )
    )
    if conv_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    where = Message.conversation_id == conversation_id
    if role:
        where &= Message.role == role

    total = await db.execute(select(func.count()).select_from(Message).where(where))
    total_count = total.scalar() or 0

    result = await db.execute(
        select(Message)
        .where(where)
        .order_by(Message.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    messages = result.scalars().all()

    items = [
        MessageResponse(
            id=m.id,
            conversation_id=m.conversation_id,
            role=m.role.value if hasattr(m.role, "value") else m.role,
            content=m.content,
            content_type=m.content_type or "text",
            intent=m.intent,
            entities=m.entities,
            tokens_used=m.tokens_used,
            cost_usd=m.cost_usd,
            meta_info=m.meta_info or {},
            created_at=m.created_at,
        )
        for m in messages
    ]

    return PaginatedMessagesResponse(
        items=items,
        total=total_count,
        page=page,
        page_size=page_size,
    )


# ── POST /conversations/{conversation_id}/messages ────────────


@router.post(
    "/conversations/{conversation_id}/messages", response_model=MessageResponse, status_code=201
)
async def send_message(
    conversation_id: uuid.UUID,
    body: MessageCreate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> MessageResponse:
    """Send a message in a conversation."""
    # Verify conversation
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == current_user.tenant_id,
        )
    )
    conv = conv_result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    msg = Message(
        tenant_id=current_user.tenant_id,
        conversation_id=conversation_id,
        role=body.role.value if hasattr(body.role, "value") else body.role,
        content=body.content,
        content_type=body.content_type,
        intent=body.intent,
        entities=body.entities,
    )
    db.add(msg)

    # Update conversation's last_message_at
    conv.last_message_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(msg)

    return MessageResponse(
        id=msg.id,
        conversation_id=msg.conversation_id,
        role=msg.role.value if hasattr(msg.role, "value") else msg.role,
        content=msg.content,
        content_type=msg.content_type or "text",
        intent=msg.intent,
        entities=msg.entities,
        tokens_used=msg.tokens_used,
        cost_usd=msg.cost_usd,
        meta_info=msg.meta_info or {},
        created_at=msg.created_at,
    )


# ── POST .../quick-reply ──────────────────────────────────────


@router.post(
    "/conversations/{conversation_id}/messages/{message_id}/quick-reply",
    response_model=QuickReplySuggestionsResponse,
)
async def suggest_quick_replies(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> QuickReplySuggestionsResponse:
    """Suggest quick reply buttons. Stub: returns defaults."""
    # Verify message exists
    result = await db.execute(
        select(Message).where(
            Message.id == message_id,
            Message.conversation_id == conversation_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    return QuickReplySuggestionsResponse(replies=["Понял", "Продолжить", "Нет, спасибо"])


# ── POST .../attachments ──────────────────────────────────────


@router.post("/conversations/{conversation_id}/messages/{message_id}/attachments", status_code=201)
async def attach_to_message(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> dict:
    """Attach a file to a message. Stub: creates an empty attachment record."""
    result = await db.execute(
        select(Message).where(
            Message.id == message_id,
            Message.conversation_id == conversation_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    attachment = MessageAttachment(
        tenant_id=current_user.tenant_id,
        message_id=message_id,
        file_type="document",
        file_url="stub://placeholder",
        file_size_bytes=0,
        mime_type="application/octet-stream",
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)

    return {"id": str(attachment.id), "message": "Attachment stub created"}
