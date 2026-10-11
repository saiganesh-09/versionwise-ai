"""Chat endpoints — question answering backed by the retrieval engine."""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import NotFoundError
from app.core.security import CurrentUser, ForbiddenError
from app.db.session import get_session
from app.models import ChatMessage, ChatSession, MessageRole, SourceCitation
from app.retrieval.engine import answer_question
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    SessionDetailOut,
    SessionOut,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
def ask(
    body: ChatRequest,
    current: CurrentUser,
    session: Session = Depends(get_session),
) -> ChatResponse:
    # Resolve or create the session — always owned by the caller.
    if body.session_id is not None:
        chat_session = session.get(ChatSession, body.session_id)
        if chat_session is None:
            raise NotFoundError("Chat session not found.")
        if chat_session.user_id != current.id:
            raise ForbiddenError("This chat session belongs to another user.")
    else:
        chat_session = ChatSession(
            user_id=current.id, title=body.question[:80]
        )
        session.add(chat_session)
        session.flush()

    result = answer_question(
        session,
        current,
        body.question,
        as_of=body.as_of_date,
        document_id=body.document_id,
    )

    # Persist both sides of the exchange + auditable citation links.
    session.add(
        ChatMessage(
            session_id=chat_session.id,
            role=MessageRole.user,
            content=body.question,
            as_of_date=result.intent.get("as_of"),
        )
    )
    assistant = ChatMessage(
        session_id=chat_session.id,
        role=MessageRole.assistant,
        content=result.answer,
        as_of_date=result.intent.get("as_of"),
    )
    session.add(assistant)
    session.flush()
    for c in result.citations:
        session.add(
            SourceCitation(
                message_id=assistant.id, chunk_id=uuid.UUID(c["chunk_id"]), rank=c["rank"]
            )
        )
    session.commit()

    return ChatResponse(
        session_id=chat_session.id,
        message_id=assistant.id,
        status=result.status,
        answer=result.answer,
        citations=result.citations,
        evidence=result.evidence,
        warnings=result.warnings,
        intent=result.intent,
    )


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    current: CurrentUser,
    session: Session = Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ChatSession]:
    return list(
        session.execute(
            select(ChatSession)
            .where(ChatSession.user_id == current.id)
            .order_by(ChatSession.updated_at.desc())
            .limit(limit)
            .offset(offset)
        ).scalars()
    )


@router.get("/sessions/{session_id}", response_model=SessionDetailOut)
def get_session_detail(
    session_id: uuid.UUID,
    current: CurrentUser,
    session: Session = Depends(get_session),
) -> ChatSession:
    # Eager-load messages + their citations in two queries — no N+1.
    chat_session = session.execute(
        select(ChatSession)
        .options(
            selectinload(ChatSession.messages).selectinload(
                ChatMessage.citations
            )
        )
        .where(ChatSession.id == session_id)
    ).scalar_one_or_none()
    if chat_session is None:
        raise NotFoundError("Chat session not found.")
    if chat_session.user_id != current.id:
        raise ForbiddenError("This chat session belongs to another user.")
    return chat_session
