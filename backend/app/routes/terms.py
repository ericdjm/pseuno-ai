"""
Term registry endpoints.

Provides canonical term resolution, aliasing, and similarity search.
No DB-suggested terms are injected into prompts by default.
"""

import math
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PromptTermLink, Term, TermAlias, TermEvent
from app.deps import get_db
from app.schemas.terms import (
    ResolvedTerm,
    SimilarTermResult,
    TermAliasCreateRequest,
    TermCompareRequest,
    TermCompareResult,
    TermCreateRequest,
    TermResolveRequest,
    TermResolveResponse,
    TermResponse,
    TermSimilarResponse,
)
from app.services.term_normalizer import normalize_term

router = APIRouter()

# Time decay constant (in days) for event-based co-occurrence
# Events older than ~3*tau have negligible weight
TIME_DECAY_TAU_DAYS = 30.0


@router.post("/resolve", response_model=TermResolveResponse)
def resolve_terms(
    body: TermResolveRequest,
    db: Session = Depends(get_db),
):
    """
    Resolve raw term strings to canonical forms.

    For each input term:
    1. Normalize to snake_case
    2. Check if it matches an existing canonical term
    3. Check if it matches an existing alias
    4. If create_if_missing=True, create new terms for unmatched strings

    Returns the resolved terms with their IDs and metadata.
    """
    resolved: list[ResolvedTerm] = []
    unresolved_count = 0

    for raw_term in body.terms:
        canonical = normalize_term(raw_term)

        if not canonical:
            # Skip empty/invalid terms
            resolved.append(
                ResolvedTerm(
                    input=raw_term,
                    canonical="",
                    matched_via=None,
                )
            )
            unresolved_count += 1
            continue

        # Try to find existing term by canonical match
        term = db.scalar(select(Term).where(Term.canonical == canonical))

        if term:
            resolved.append(
                ResolvedTerm(
                    input=raw_term,
                    canonical=term.canonical,
                    term_id=term.id,
                    display_name=term.display_name,
                    term_type=term.term_type,
                    matched_via="canonical",
                )
            )
            continue

        # Try to find by alias
        alias_record = db.scalar(select(TermAlias).where(TermAlias.alias == canonical))

        if alias_record:
            term = alias_record.term
            resolved.append(
                ResolvedTerm(
                    input=raw_term,
                    canonical=term.canonical,
                    term_id=term.id,
                    display_name=term.display_name,
                    term_type=term.term_type,
                    matched_via="alias",
                )
            )
            continue

        # Not found — optionally create
        if body.create_if_missing:
            new_term = Term(
                canonical=canonical,
                display_name=(
                    raw_term.strip() if raw_term.strip() != canonical else None
                ),
                term_type="other",
            )
            db.add(new_term)
            db.flush()  # Get the ID

            resolved.append(
                ResolvedTerm(
                    input=raw_term,
                    canonical=new_term.canonical,
                    term_id=new_term.id,
                    display_name=new_term.display_name,
                    term_type=new_term.term_type,
                    matched_via=None,
                    created=True,
                )
            )
        else:
            resolved.append(
                ResolvedTerm(
                    input=raw_term,
                    canonical=canonical,
                    matched_via=None,
                )
            )
            unresolved_count += 1

    db.commit()

    return TermResolveResponse(resolved=resolved, unresolved_count=unresolved_count)


@router.get("/{term_id}", response_model=TermResponse)
def get_term(
    term_id: int,
    db: Session = Depends(get_db),
):
    """Get a term by ID."""
    term = db.get(Term, term_id)
    if not term:
        raise HTTPException(status_code=404, detail="Term not found")
    return term


@router.post("", response_model=TermResponse, status_code=status.HTTP_201_CREATED)
def create_term(
    body: TermCreateRequest,
    db: Session = Depends(get_db),
):
    """
    Manually create a new term in the registry.
    The canonical key must be unique.
    """
    # Normalize the canonical key
    canonical = normalize_term(body.canonical)
    if not canonical:
        raise HTTPException(
            status_code=400, detail="Invalid canonical key (normalizes to empty)"
        )

    # Check for existing
    existing = db.scalar(select(Term).where(Term.canonical == canonical))
    if existing:
        raise HTTPException(
            status_code=409, detail=f"Term '{canonical}' already exists"
        )

    term = Term(
        canonical=canonical,
        display_name=body.display_name,
        term_type=body.term_type,
    )
    db.add(term)
    db.commit()
    db.refresh(term)
    return term


@router.post("/alias", status_code=status.HTTP_201_CREATED)
def create_alias(
    body: TermAliasCreateRequest,
    db: Session = Depends(get_db),
):
    """
    Add an alias to an existing term.
    The alias is normalized and must be unique.
    """
    # Normalize the alias
    alias = normalize_term(body.alias)
    if not alias:
        raise HTTPException(
            status_code=400, detail="Invalid alias (normalizes to empty)"
        )

    # Check term exists
    term = db.get(Term, body.term_id)
    if not term:
        raise HTTPException(status_code=404, detail="Term not found")

    # Check alias doesn't already exist
    existing_alias = db.scalar(select(TermAlias).where(TermAlias.alias == alias))
    if existing_alias:
        raise HTTPException(status_code=409, detail=f"Alias '{alias}' already exists")

    # Check alias doesn't match an existing canonical term
    existing_canonical = db.scalar(select(Term).where(Term.canonical == alias))
    if existing_canonical:
        raise HTTPException(
            status_code=409,
            detail=f"Alias '{alias}' conflicts with existing canonical term",
        )

    alias_record = TermAlias(alias=alias, term_id=term.id)
    db.add(alias_record)
    db.commit()

    return {"alias": alias, "term_id": term.id, "canonical": term.canonical}


# =============================================================================
# Phase 2: Similarity endpoints
# =============================================================================


def _time_decay_weight(event_time: datetime, now: datetime, tau_days: float) -> float:
    """
    Calculate exponential time decay weight.
    Returns 1.0 for now, ~0.37 at tau_days ago, ~0.05 at 3*tau_days ago.
    """
    if event_time.tzinfo is None:
        event_time = event_time.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    age_days = (now - event_time).total_seconds() / 86400.0
    return math.exp(-age_days / tau_days)


def _resolve_term_id(canonical: str, db: Session) -> Optional[int]:
    """Look up term ID by canonical name or alias."""
    term = db.scalar(select(Term).where(Term.canonical == canonical))
    if term:
        return term.id

    alias = db.scalar(select(TermAlias).where(TermAlias.alias == canonical))
    if alias:
        return alias.term_id

    return None


def _get_co_occurring_terms(
    term_id: int,
    db: Session,
    limit: int = 20,
) -> list[tuple[int, float, list[str]]]:
    """
    Find terms that co-occur with the given term in saved prompts.

    Returns list of (term_id, score, provenance_sources) tuples.
    Uses time decay to weight recent saves higher.
    """
    now = datetime.now(timezone.utc)

    # Find all prompts containing this term
    prompt_links = db.scalars(
        select(PromptTermLink).where(PromptTermLink.term_id == term_id)
    ).all()

    if not prompt_links:
        return []

    prompt_ids = [link.prompt_id for link in prompt_links]

    # Find other terms in those prompts (excluding the query term)
    co_occur_links = db.scalars(
        select(PromptTermLink)
        .where(PromptTermLink.prompt_id.in_(prompt_ids))
        .where(PromptTermLink.term_id != term_id)
    ).all()

    # Aggregate scores with time decay
    scores: dict[int, float] = {}
    sources: dict[int, set[str]] = {}

    for link in co_occur_links:
        weight = _time_decay_weight(link.created_at, now, TIME_DECAY_TAU_DAYS)
        scores[link.term_id] = scores.get(link.term_id, 0.0) + weight
        if link.term_id not in sources:
            sources[link.term_id] = set()
        sources[link.term_id].add(f"cooccur:{link.source}")

    # Also factor in term_events for co-occurrence
    events = db.scalars(
        select(TermEvent)
        .where(TermEvent.term_id == term_id)
        .where(TermEvent.candidate_term_id.isnot(None))
    ).all()

    for event in events:
        if event.candidate_term_id:
            weight = _time_decay_weight(event.created_at, now, TIME_DECAY_TAU_DAYS)
            scores[event.candidate_term_id] = (
                scores.get(event.candidate_term_id, 0.0) + weight
            )
            if event.candidate_term_id not in sources:
                sources[event.candidate_term_id] = set()
            sources[event.candidate_term_id].add(f"event:{event.event_type}")

    # Normalize scores to 0-1 range
    if scores:
        max_score = max(scores.values())
        if max_score > 0:
            for tid in scores:
                scores[tid] = scores[tid] / max_score

    # Sort by score and limit
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]

    return [(tid, score, list(sources.get(tid, []))) for tid, score in ranked]


@router.get("/similar/{term}", response_model=TermSimilarResponse)
def get_similar_terms(
    term: str,
    limit: int = Query(default=20, ge=1, le=100, description="Max results"),
    db: Session = Depends(get_db),
):
    """
    Get terms similar to the given term.

    Similarity is computed from:
    - Co-occurrence in saved prompts (time-decayed)
    - Term events linking related terms

    Returns similar terms ranked by score with provenance tags.
    This endpoint does NOT inject suggestions into generation by default.
    """
    canonical = normalize_term(term)
    if not canonical:
        raise HTTPException(status_code=400, detail="Invalid term")

    term_id = _resolve_term_id(canonical, db)

    if not term_id:
        # Term doesn't exist in registry — return empty results
        return TermSimilarResponse(
            query_term=canonical,
            query_term_id=None,
            similar=[],
        )

    # Get co-occurring terms
    co_occurring = _get_co_occurring_terms(term_id, db, limit)

    # Build response
    similar: list[SimilarTermResult] = []

    for tid, score, provenance in co_occurring:
        term_record = db.get(Term, tid)
        if term_record:
            similar.append(
                SimilarTermResult(
                    term_id=term_record.id,
                    canonical=term_record.canonical,
                    display_name=term_record.display_name,
                    term_type=term_record.term_type,
                    score=round(score, 3),
                    provenance=provenance,
                )
            )

    return TermSimilarResponse(
        query_term=canonical,
        query_term_id=term_id,
        similar=similar,
    )


@router.post("/compare", response_model=TermCompareResult)
def compare_terms(
    body: TermCompareRequest,
    db: Session = Depends(get_db),
):
    """
    Compare multiple terms and find shared vs. differing facets.

    Shared terms: Terms that are similar to ALL input terms.
    Differing terms: Terms that are similar to only one input term.

    Useful for understanding "what's common between Rush and Meshuggah?"
    """
    # Resolve all input terms
    resolved_terms: list[str] = []
    term_ids: list[int] = []

    for raw in body.terms:
        canonical = normalize_term(raw)
        if not canonical:
            continue
        resolved_terms.append(canonical)
        tid = _resolve_term_id(canonical, db)
        if tid:
            term_ids.append(tid)

    if len(term_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 terms must exist in the registry to compare",
        )

    # Get similar terms for each input
    similar_per_term: dict[int, dict[int, tuple[float, list[str]]]] = {}

    for tid in term_ids:
        co_occurring = _get_co_occurring_terms(tid, db, limit=50)
        similar_per_term[tid] = {
            co_tid: (score, prov) for co_tid, score, prov in co_occurring
        }

    # Find shared terms (appear in ALL input term's similar sets)
    all_similar_sets = [set(s.keys()) for s in similar_per_term.values()]
    shared_term_ids = set.intersection(*all_similar_sets) if all_similar_sets else set()

    # Exclude the input terms themselves
    shared_term_ids -= set(term_ids)

    # Build shared results with averaged scores
    shared_terms: list[SimilarTermResult] = []
    for shared_tid in shared_term_ids:
        avg_score = sum(
            similar_per_term[tid][shared_tid][0]
            for tid in term_ids
            if shared_tid in similar_per_term[tid]
        ) / len(term_ids)

        all_prov = set()
        for tid in term_ids:
            if shared_tid in similar_per_term[tid]:
                all_prov.update(similar_per_term[tid][shared_tid][1])

        term_record = db.get(Term, shared_tid)
        if term_record:
            shared_terms.append(
                SimilarTermResult(
                    term_id=term_record.id,
                    canonical=term_record.canonical,
                    display_name=term_record.display_name,
                    term_type=term_record.term_type,
                    score=round(avg_score, 3),
                    provenance=list(all_prov),
                )
            )

    shared_terms.sort(key=lambda x: x.score, reverse=True)

    # Find differing terms (unique to each input term)
    differing_terms: dict[str, list[SimilarTermResult]] = {}

    for tid in term_ids:
        term_record = db.get(Term, tid)
        if not term_record:
            continue

        # Terms in this one's similar set but not in all others
        unique_tids = set(similar_per_term[tid].keys())
        for other_tid in term_ids:
            if other_tid != tid:
                unique_tids -= set(similar_per_term[other_tid].keys())
        unique_tids -= set(term_ids)  # Exclude input terms

        unique_results: list[SimilarTermResult] = []
        for unique_tid in unique_tids:
            score, prov = similar_per_term[tid][unique_tid]
            unique_record = db.get(Term, unique_tid)
            if unique_record:
                unique_results.append(
                    SimilarTermResult(
                        term_id=unique_record.id,
                        canonical=unique_record.canonical,
                        display_name=unique_record.display_name,
                        term_type=unique_record.term_type,
                        score=round(score, 3),
                        provenance=list(prov),
                    )
                )

        unique_results.sort(key=lambda x: x.score, reverse=True)
        differing_terms[term_record.canonical] = unique_results[:10]

    return TermCompareResult(
        terms_resolved=resolved_terms,
        shared_terms=shared_terms[:20],
        differing_terms=differing_terms,
    )
