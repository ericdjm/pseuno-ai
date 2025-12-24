"""
Schemas for term registry endpoints (Phase 1).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TermResolveRequest(BaseModel):
    """Request to resolve raw term strings to canonical forms."""

    terms: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of raw term strings to resolve",
    )
    create_if_missing: bool = Field(
        default=False,
        description="If True, create new terms for unresolved strings",
    )


class ResolvedTerm(BaseModel):
    """A single resolved term result."""

    input: str = Field(description="Original input string")
    canonical: str = Field(description="Normalized canonical form")
    term_id: Optional[int] = Field(
        default=None, description="Term ID if matched in registry"
    )
    display_name: Optional[str] = Field(
        default=None, description="Display name if available"
    )
    term_type: Optional[str] = Field(
        default=None, description="Term type (genre, mood, etc.)"
    )
    matched_via: Optional[str] = Field(
        default=None,
        description="How it was matched: 'canonical', 'alias', or None if new",
    )
    created: bool = Field(
        default=False, description="True if this term was just created"
    )


class TermResolveResponse(BaseModel):
    """Response from term resolution."""

    resolved: list[ResolvedTerm] = Field(description="List of resolved terms")
    unresolved_count: int = Field(
        default=0, description="Count of terms that couldn't be matched to existing"
    )


class TermResponse(BaseModel):
    """Response for a single term from the registry."""

    id: int
    canonical: str
    display_name: Optional[str]
    term_type: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TermCreateRequest(BaseModel):
    """Request to manually create a term."""

    canonical: str = Field(
        ..., min_length=2, max_length=100, description="Canonical term key"
    )
    display_name: Optional[str] = Field(
        default=None, max_length=100, description="Human-readable display name"
    )
    term_type: str = Field(
        default="other",
        pattern="^(artist|genre|mood|instrument|era|production|other)$",
        description="Term category",
    )


class TermAliasCreateRequest(BaseModel):
    """Request to add an alias to an existing term."""

    alias: str = Field(..., min_length=2, max_length=100, description="Alias to add")
    term_id: int = Field(..., description="ID of the term to alias to")


# =============================================================================
# Phase 2: Similarity endpoints
# =============================================================================


class SimilarTermResult(BaseModel):
    """A single similar term with score and provenance."""

    term_id: int
    canonical: str
    display_name: Optional[str] = None
    term_type: str
    score: float = Field(description="Similarity score (0-1)")
    provenance: list[str] = Field(
        default_factory=list,
        description="Sources contributing to this score (curated, cooccur, etc.)",
    )


class TermSimilarResponse(BaseModel):
    """Response from similarity search."""

    query_term: str = Field(description="The term being queried")
    query_term_id: Optional[int] = Field(
        default=None, description="Term ID if it exists in registry"
    )
    similar: list[SimilarTermResult] = Field(
        description="Similar terms ranked by score"
    )


class TermCompareRequest(BaseModel):
    """Request to compare multiple terms and find shared/differing facets."""

    terms: list[str] = Field(
        ...,
        min_length=2,
        max_length=10,
        description="Terms to compare (2-10)",
    )


class TermCompareResult(BaseModel):
    """Result of term comparison."""

    terms_resolved: list[str] = Field(description="Input terms resolved to canonical")
    shared_terms: list[SimilarTermResult] = Field(
        description="Terms that appear similar to ALL input terms"
    )
    differing_terms: dict[str, list[SimilarTermResult]] = Field(
        description="Terms unique to each input term (keyed by canonical)"
    )
