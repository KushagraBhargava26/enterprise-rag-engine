import enum
from typing import Optional, List
from sqlalchemy import String, ForeignKey, Enum, Text, Float, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from packages.core.database import Base
from packages.core.models.base import TimestampMixin, generate_uuid

class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class AnswerStatus(str, enum.Enum):
    GROUNDED = "grounded"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    GENERATION_ERROR = "generation_error"

class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="New Conversation")

    messages: Mapped[List["Message"]] = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_conversations_tenant_user", "tenant_id", "user_id"),
    )

class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    answer_status: Mapped[Optional[AnswerStatus]] = mapped_column(Enum(AnswerStatus), nullable=True)

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
    citations: Mapped[List["Citation"]] = relationship("Citation", back_populates="message", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_messages_tenant_conv", "tenant_id", "conversation_id"),
    )

class Citation(Base, TimestampMixin):
    __tablename__ = "citations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    message_id: Mapped[str] = mapped_column(String(36), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id: Mapped[str] = mapped_column(String(36), ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    relevance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    section_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    message: Mapped["Message"] = relationship("Message", back_populates="citations")

    __table_args__ = (
        Index("ix_citations_tenant_message", "tenant_id", "message_id"),
    )
