"""
Pydantic schemas for user-managed genres.
"""

from pydantic import BaseModel, Field


class GenreItem(BaseModel):
    id: int
    name: str


class GenreCatalogResponse(BaseModel):
    genres: list[GenreItem]


class UserGenreAddRequest(BaseModel):
    genre_id: int = Field(..., description="ID of the genre to add")


class UserGenresResponse(BaseModel):
    genres: list[str]
