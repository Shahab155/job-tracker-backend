from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from db.database import get_conn
from db.auth_dep import get_current_user

router = APIRouter()

# ── Pydantic models ────────────────────────────────────────────────────────────

class ResumeCreate(BaseModel):
    name:    str
    content: str

class ResumeUpdate(BaseModel):
    name:    Optional[str] = None
    content: Optional[str] = None

# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/")
async def list_resumes(
    user_id: int = Depends(get_current_user),
    conn=Depends(get_conn)
):
    """
    Return all resumes for the logged-in user.
    Returns id and name only — content is excluded to keep
    the response light. Content is only fetched when needed.
    """
    rows = await conn.fetch(
        "SELECT id, name, created_at FROM resumes WHERE user_id=$1 ORDER BY created_at DESC",
        user_id
    )
    return [dict(r) for r in rows]


@router.get("/{resume_id}")
async def get_resume(
    resume_id: int,
    user_id: int = Depends(get_current_user),
    conn=Depends(get_conn)
):
    """Return a single resume including full content — used when editing."""
    row = await conn.fetchrow(
        "SELECT * FROM resumes WHERE id=$1 AND user_id=$2",
        resume_id, user_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Resume not found")
    return dict(row)


@router.post("/")
async def create_resume(
    body: ResumeCreate,
    user_id: int = Depends(get_current_user),
    conn=Depends(get_conn)
):
    """Create a new resume. Name should describe the resume type e.g. Frontend, Full Stack."""
    row = await conn.fetchrow(
        "INSERT INTO resumes (user_id, name, content) VALUES ($1, $2, $3) RETURNING *",
        user_id, body.name, body.content
    )
    return dict(row)


@router.put("/{resume_id}")
async def update_resume(
    resume_id: int,
    body: ResumeUpdate,
    user_id: int = Depends(get_current_user),
    conn=Depends(get_conn)
):
    """Update the name or content of a resume."""
    updates = body.dict(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Nothing to update")

    set_clause = ", ".join(f"{k}=${i+1}" for i, k in enumerate(updates.keys()))
    values = list(updates.values())
    values.append(resume_id)
    values.append(user_id)

    row = await conn.fetchrow(
        f"UPDATE resumes SET {set_clause} WHERE id=${len(values)-1} AND user_id=${len(values)} RETURNING *",
        *values
    )
    if not row:
        raise HTTPException(status_code=404, detail="Resume not found")
    return dict(row)


@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: int,
    user_id: int = Depends(get_current_user),
    conn=Depends(get_conn)
):
    """Delete a resume permanently."""
    result = await conn.execute(
        "DELETE FROM resumes WHERE id=$1 AND user_id=$2",
        resume_id, user_id
    )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Resume not found")
    return {"message": "Resume deleted"}
