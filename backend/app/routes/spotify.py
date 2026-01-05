"""
Spotify Data Routes
Fetches and processes user's Spotify data
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Genre, UserGenre
from app.deps import get_current_user_id, get_db, get_spotify_client
from app.schemas.genres import (
    GenreCatalogResponse,
    GenreItem,
    UserGenreAddRequest,
    UserGenresResponse,
)
from app.schemas.spotify import SpotifyProfileResponse
from app.services.genre_catalog import ensure_genres_seeded, get_or_create_genres
from app.services.spotify_client import SpotifyClient
from app.services.taste_analyzer import (
    compute_avg_popularity,
    derive_mood_tags,
    generate_summary,
)
from app.utils import fetch_and_parse_spotify_data

router = APIRouter()
MAX_USER_GENRES = 20


def _get_user_genre_names(db: Session, user_id: str) -> list[str]:
    return (
        db.scalars(
            select(Genre.name)
            .join(UserGenre, UserGenre.genre_id == Genre.id)
            .where(UserGenre.user_id == user_id)
            .order_by(UserGenre.id.asc())
        )
        .all()
    )


def _seed_user_genres(
    db: Session,
    user_id: str,
    genre_names: list[str],
) -> list[str]:
    trimmed_names = genre_names[:MAX_USER_GENRES]
    genres = get_or_create_genres(db, trimmed_names)
    if not genres:
        return []
    try:
        db.add_all(
            [
                UserGenre(user_id=user_id, genre_id=genre.id)
                for genre in genres
            ]
        )
        db.commit()
    except IntegrityError:
        db.rollback()
    return _get_user_genre_names(db, user_id)


@router.get("/profile", response_model=SpotifyProfileResponse)
async def get_profile(
    client: SpotifyClient = Depends(get_spotify_client),
    time_range: str = Query(default="medium_term", pattern="^(short_term|medium_term|long_term)$"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Get user's Spotify profile with taste analysis
    
    Time ranges:
    - short_term: ~4 weeks
    - medium_term: ~6 months
    - long_term: Several years
    """
    # Fetch and parse data (uses parallel API calls internally)
    top_artists, top_tracks, taste_profile = await fetch_and_parse_spotify_data(
        client, time_range
    )

    # Ensure catalog exists and load user-managed genres
    ensure_genres_seeded(db)
    user_genres = _get_user_genre_names(db, user_id)
    if not user_genres and taste_profile.top_genres:
        user_genres = _seed_user_genres(db, user_id, taste_profile.top_genres)

    if user_genres:
        taste_profile.top_genres = user_genres
        avg_popularity = compute_avg_popularity(top_artists)
        taste_profile.mood_tags = derive_mood_tags(user_genres, avg_popularity)
        taste_profile.summary_sentence = generate_summary(
            user_genres, taste_profile.mood_tags, avg_popularity
        )
    
    return SpotifyProfileResponse(
        top_artists=top_artists,
        top_tracks=top_tracks,
        taste_profile=taste_profile,
        time_range=time_range
    )


@router.get("/genres/catalog", response_model=GenreCatalogResponse)
def list_genre_catalog(
    db: Session = Depends(get_db),
    _user_id: str = Depends(get_current_user_id),
):
    """
    List available genres for the top-genres picker.
    """
    ensure_genres_seeded(db)
    genres = db.scalars(select(Genre).order_by(Genre.name.asc())).all()
    return GenreCatalogResponse(
        genres=[GenreItem(id=genre.id, name=genre.name) for genre in genres]
    )


@router.post("/genres", response_model=UserGenresResponse)
def add_user_genre(
    body: UserGenreAddRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Add a genre to the user's top genres list.
    """
    genre = db.get(Genre, body.genre_id)
    if not genre:
        raise HTTPException(status_code=404, detail="Genre not found")

    existing = db.scalar(
        select(UserGenre)
        .where(UserGenre.user_id == user_id)
        .where(UserGenre.genre_id == body.genre_id)
    )
    if not existing:
        current_count = db.scalar(
            select(func.count(UserGenre.id)).where(UserGenre.user_id == user_id)
        )
        if (current_count or 0) >= MAX_USER_GENRES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You can only have up to 20 genres.",
            )
        db.add(UserGenre(user_id=user_id, genre_id=body.genre_id))
        db.commit()

    return UserGenresResponse(genres=_get_user_genre_names(db, user_id))


@router.delete("/genres/{genre_id}", response_model=UserGenresResponse)
def delete_user_genre(
    genre_id: int,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Remove a genre from the user's top genres list.
    """
    link = db.scalar(
        select(UserGenre)
        .where(UserGenre.user_id == user_id)
        .where(UserGenre.genre_id == genre_id)
    )
    if link:
        db.delete(link)
        db.commit()
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Genre not linked to user",
        )

    return UserGenresResponse(genres=_get_user_genre_names(db, user_id))
