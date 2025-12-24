"""
Term registry endpoints.

Provides canonical term resolution and aliasing.
No DB-suggested terms are injected into prompts by default.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Term, TermAlias
from app.deps import get_db
from app.schemas.terms import (
    ResolvedTerm,
    TermAliasCreateRequest,
    TermCreateRequest,
    TermResolveRequest,
    TermResolveResponse,
    TermResponse,
)
from app.services.term_normalizer import normalize_term

router = APIRouter()


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
