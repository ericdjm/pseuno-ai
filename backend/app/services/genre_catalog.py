"""
Genre catalog helpers for user-managed top genres.
"""

from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Genre


DEFAULT_GENRES = [
    "ambient",
    "art pop",
    "dream pop",
    "electronic",
    "folk",
    "funk",
    "hip-hop",
    "house",
    "industrial",
    "indie rock",
    "jazz fusion",
    "lo-fi",
    "neo-soul",
    "post-punk",
    "progressive rock",
    "psychedelic",
    "R&B",
    "shoegaze",
    "synth-pop",
    "trip-hop",
]


def normalize_genre_name(name: str) -> str:
    """Normalize a genre name for matching and uniqueness."""
    return " ".join(name.strip().lower().split())


def ensure_genres_seeded(db: Session) -> None:
    """Seed the genre catalog if it's empty."""
    existing_count = db.scalar(select(func.count(Genre.id)))
    if existing_count:
        return
    db.add_all(
        [
            Genre(name=genre, normalized_name=normalize_genre_name(genre))
            for genre in DEFAULT_GENRES
        ]
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def get_or_create_genres(db: Session, names: Iterable[str]) -> list[Genre]:
    """Fetch or create genre rows for the provided names."""
    normalized_to_name = {}
    for name in names:
        if not name:
            continue
        normalized_to_name[normalize_genre_name(name)] = name.strip()

    if not normalized_to_name:
        return []

    normalized_list = list(normalized_to_name.keys())
    existing = db.scalars(
        select(Genre).where(Genre.normalized_name.in_(normalized_list))
    ).all()
    existing_by_norm = {genre.normalized_name: genre for genre in existing}

    created = []
    for normalized, display_name in normalized_to_name.items():
        if normalized in existing_by_norm:
            continue
        created.append(Genre(name=display_name, normalized_name=normalized))

    if created:
        db.add_all(created)
        db.commit()
        for genre in created:
            db.refresh(genre)

    return existing + created
