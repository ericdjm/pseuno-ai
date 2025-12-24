import secrets
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


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
    """A saved Suno prompt that users can favorite and reuse."""

    __tablename__ = "suno_prompts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Core prompt content
    suno_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    exclude: Mapped[str] = mapped_column(Text, nullable=False, default="")
    weirdness: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    style_influence: Mapped[int] = mapped_column(Integer, nullable=False, default=50)

    # UX fields
    title: Mapped[Optional[str]] = mapped_column(String(255))
    notes: Mapped[Optional[str]] = mapped_column(Text)

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

    owner: Mapped[User] = relationship(back_populates="suno_prompts")
    term_links: Mapped[list["PromptTermLink"]] = relationship(
        back_populates="prompt", cascade="all, delete-orphan"
    )


# =============================================================================
# Phase 1: Term Registry
# =============================================================================


class Term(Base):
    """Canonical term in the term registry (genre, mood, era, etc.)."""

    __tablename__ = "terms"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    canonical: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )
    display_name: Mapped[Optional[str]] = mapped_column(String(100))
    term_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="other", index=True
    )  # artist|genre|mood|instrument|era|production|other

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    aliases: Mapped[list["TermAlias"]] = relationship(
        back_populates="term", cascade="all, delete-orphan"
    )
    prompt_links: Mapped[list["PromptTermLink"]] = relationship(
        back_populates="term", cascade="all, delete-orphan"
    )


class TermAlias(Base):
    """Alternate spelling/variant that maps to a canonical term."""

    __tablename__ = "term_aliases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    alias: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )
    term_id: Mapped[int] = mapped_column(
        ForeignKey("terms.id", ondelete="CASCADE"), nullable=False, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    term: Mapped[Term] = relationship(back_populates="aliases")


class TermEvent(Base):
    """Log of user interactions with terms (for learning co-occurrence)."""

    __tablename__ = "term_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True
    )  # query|select|save_prompt|spotify_seed|model_extracted
    term_id: Mapped[int] = mapped_column(
        ForeignKey("terms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_term_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("terms.id", ondelete="CASCADE"), nullable=True
    )  # for co-occurrence events
    source_metadata: Mapped[Optional[str]] = mapped_column(Text)  # JSON blob

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class PromptTermLink(Base):
    """Link between a saved prompt and a term (for learning from saves)."""

    __tablename__ = "prompt_term_links"
    __table_args__ = (
        UniqueConstraint("prompt_id", "term_id", name="uq_prompt_term_links_prompt_term"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    prompt_id: Mapped[int] = mapped_column(
        ForeignKey("suno_prompts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    term_id: Mapped[int] = mapped_column(
        ForeignKey("terms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="user"
    )  # user|model_extracted|spotify

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    prompt: Mapped[SunoPrompt] = relationship(back_populates="term_links")
    term: Mapped[Term] = relationship(back_populates="prompt_links")


__all__ = [
    "Base",
    "User",
    "ExternalAccount",
    "SunoPrompt",
    "Term",
    "TermAlias",
    "TermEvent",
    "PromptTermLink",
]
