"""
CRUD routes for saved Suno prompts (favorites).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.models import SunoPrompt
from app.deps import get_current_user_id, get_db
from app.schemas.prompts import (
    SunoPromptCreate,
    SunoPromptListResponse,
    SunoPromptResponse,
    SunoPromptUpdate,
)

router = APIRouter()


@router.post("", response_model=SunoPromptResponse, status_code=status.HTTP_201_CREATED)
def create_prompt(
    body: SunoPromptCreate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Save a new Suno prompt as a favorite."""
    prompt = SunoPrompt(
        owner_user_id=user_id,
        suno_prompt=body.suno_prompt,
        exclude=body.exclude,
        weirdness=body.weirdness,
        style_influence=body.style_influence,
        title=body.title,
        notes=body.notes,
    )
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


@router.get("", response_model=SunoPromptListResponse)
def list_prompts(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    """List the current user's saved prompts."""
    query = (
        select(SunoPrompt)
        .where(SunoPrompt.owner_user_id == user_id)
        .order_by(SunoPrompt.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    prompts = list(db.scalars(query).all())

    total_query = (
        select(func.count())
        .select_from(SunoPrompt)
        .where(SunoPrompt.owner_user_id == user_id)
    )
    total = db.scalar(total_query) or 0

    return SunoPromptListResponse(prompts=prompts, total=total)


@router.get("/{prompt_id}", response_model=SunoPromptResponse)
def get_prompt(
    prompt_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get a single saved prompt by ID (owner only)."""
    prompt = db.get(SunoPrompt, prompt_id)

    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    if prompt.owner_user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this prompt")

    return prompt


@router.patch("/{prompt_id}", response_model=SunoPromptResponse)
def update_prompt(
    prompt_id: int,
    body: SunoPromptUpdate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Update a saved prompt's title, notes, or visibility (owner only)."""
    prompt = db.get(SunoPrompt, prompt_id)

    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    if prompt.owner_user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this prompt")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(prompt, key, value)

    db.commit()
    db.refresh(prompt)
    return prompt


@router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prompt(
    prompt_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Delete a saved prompt (owner only)."""
    prompt = db.get(SunoPrompt, prompt_id)

    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    if prompt.owner_user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this prompt")

    db.delete(prompt)
    db.commit()


@router.get("/shared/{share_id}", response_model=SunoPromptResponse)
def get_shared_prompt(
    share_id: str,
    db: Session = Depends(get_db),
):
    """
    Get a prompt by its share_id (public access).
    Only returns prompts with visibility != 'private'.
    """
    prompt = db.scalar(
        select(SunoPrompt).where(SunoPrompt.share_id == share_id)
    )

    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    if prompt.visibility == "private":
        raise HTTPException(status_code=404, detail="Prompt not found")

    return prompt

