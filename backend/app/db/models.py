import json
import secrets
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.db.base import Base


class JSONEncodedList(TypeDecorator):
    """Store a list as a JSON-encoded string (portable across SQLite/Postgres)."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return "[]"
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return []
        return json.loads(value)


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _share_id() -> str:
    """Generate a short, URL-safe share ID."""
    return secrets.token_urlsafe(12)


def _device_token() -> str:
    """Generate a long, secure device token (32 bytes = 43 chars base64)."""
    return secrets.token_urlsafe(32)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)

    # Guest/device identification
    device_token: Mapped[Optional[str]] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )
    is_guest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    external_accounts: Mapped[list["ExternalAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    suno_prompts: Mapped[list["SunoPrompt"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class ExternalAccount(Base):
    __tablename__ = "external_accounts"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_user_id",
            name="uq_external_accounts_provider_user",
        ),
        UniqueConstraint(
            "user_id",
            "provider",
            name="uq_external_accounts_user_provider",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    profile_image_url: Mapped[Optional[str]] = mapped_column(String(512))
    access_token: Mapped[Optional[str]] = mapped_column(Text)
    refresh_token: Mapped[Optional[str]] = mapped_column(Text)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    scopes: Mapped[Optional[str]] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="external_accounts")


class SunoPrompt(Base):
    """A saved Suno prompt (StylePrompt) that users can favorite and reuse.

    Each SunoPrompt represents a "style template" and can have multiple
    LyricsThreads (songs/variations) attached to it.
    """

    __tablename__ = "suno_prompts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Iteration chain: links to parent StylePrompt when refined
    parent_prompt_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("suno_prompts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Provenance: how this prompt was created (generate, refine, reuse, etc.)
    source_action: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown", index=True
    )

    # Core prompt content
    suno_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    lyrics: Mapped[str] = mapped_column(Text, nullable=False, default="")
    exclude: Mapped[str] = mapped_column(Text, nullable=False, default="")
    weirdness: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    style_influence: Mapped[int] = mapped_column(Integer, nullable=False, default=50)

    # UX fields
    title: Mapped[Optional[str]] = mapped_column(String(255))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Favorites / history tracking
    is_favorite: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    auto_tags: Mapped[list[str]] = mapped_column(
        JSONEncodedList, nullable=False, default=lambda: []
    )
    generation_id: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)

    # Shareability fields (backend-ready, frontend initially user-scoped)
    visibility: Mapped[str] = mapped_column(
        String(20), nullable=False, default="private"
    )  # private | unlisted | public
    share_id: Mapped[str] = mapped_column(
        String(24), unique=True, nullable=False, default=_share_id
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    owner: Mapped[User] = relationship(back_populates="suno_prompts")
    # Self-referential: parent/children for refinement chains
    parent_prompt: Mapped[Optional["SunoPrompt"]] = relationship(
        "SunoPrompt",
        remote_side=[id],
        foreign_keys=[parent_prompt_id],
        back_populates="child_prompts",
    )
    child_prompts: Mapped[list["SunoPrompt"]] = relationship(
        "SunoPrompt",
        back_populates="parent_prompt",
        foreign_keys=[parent_prompt_id],
    )
    # LyricsThreads (songs) under this StylePrompt
    lyrics_threads: Mapped[list["LyricsThread"]] = relationship(
        back_populates="style_prompt", cascade="all, delete-orphan"
    )


class LyricsThread(Base):
    """A song/lyrics variation under a StylePrompt (SunoPrompt).

    Each LyricsThread represents one "song" that can be edited independently.
    Users can have multiple LyricsThreads under a single StylePrompt.
    """

    __tablename__ = "lyrics_threads"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    style_prompt_id: Mapped[int] = mapped_column(
        ForeignKey("suno_prompts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Iteration chain: links to parent thread when forked
    parent_thread_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("lyrics_threads.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Song content
    title: Mapped[Optional[str]] = mapped_column(String(255))
    lyrics_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Provenance: how this thread was created
    source_action: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown", index=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    style_prompt: Mapped[SunoPrompt] = relationship(back_populates="lyrics_threads")
    # Self-referential: parent/children for fork chains
    parent_thread: Mapped[Optional["LyricsThread"]] = relationship(
        "LyricsThread",
        remote_side=[id],
        foreign_keys=[parent_thread_id],
        back_populates="child_threads",
    )
    child_threads: Mapped[list["LyricsThread"]] = relationship(
        "LyricsThread",
        back_populates="parent_thread",
        foreign_keys=[parent_thread_id],
    )
    # Checkpoints for this thread
    checkpoints: Mapped[list["LyricsCheckpoint"]] = relationship(
        back_populates="thread", cascade="all, delete-orphan"
    )


class LyricsCheckpoint(Base):
    """An immutable snapshot of lyrics within a LyricsThread.

    Used for undo/restore functionality. Checkpoints are created:
    - Explicitly by user clicking "Checkpoint"
    - Automatically before risky operations (refine, fork)
    """

    __tablename__ = "lyrics_checkpoints"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    thread_id: Mapped[int] = mapped_column(
        ForeignKey("lyrics_threads.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Checkpoint content
    label: Mapped[Optional[str]] = mapped_column(String(255))
    lyrics_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Timestamp (immutable, no updated_at)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    thread: Mapped[LyricsThread] = relationship(back_populates="checkpoints")


__all__ = [
    "Base",
    "User",
    "ExternalAccount",
    "SunoPrompt",
    "LyricsThread",
    "LyricsCheckpoint",
]
