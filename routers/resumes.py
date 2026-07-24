from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
import os
from db.database import get_conn
from db.auth_dep import get_current_user
from utils.document_parser import parse_resume_file

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


@router.post("/parse-file")
async def parse_file(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user)
):
    """
    Upload a resume file (.pdf, .docx, .txt), parse its text content,
    and return the parsed text for previewing/editing.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a valid filename")
    
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    
    try:
        parsed_text = parse_resume_file(file_bytes, file.filename)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    
    # Generate default profile title from clean filename (remove extension)
    base_name = os.path.splitext(file.filename)[0].replace("_", " ").replace("-", " ").title()

    return {
        "filename": file.filename,
        "suggested_name": base_name,
        "parsed_content": parsed_text
    }


@router.post("/upload")
async def upload_and_create_resume(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    user_id: int = Depends(get_current_user),
    conn=Depends(get_conn)
):
    """
    Upload a resume file (.pdf, .docx, .txt), parse text content,
    and immediately save it as a new resume in the database.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a valid filename")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        parsed_text = parse_resume_file(file_bytes, file.filename)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))

    resume_name = name.strip() if name and name.strip() else os.path.splitext(file.filename)[0].replace("_", " ").replace("-", " ").title()

    row = await conn.fetchrow(
        "INSERT INTO resumes (user_id, name, content) VALUES ($1, $2, $3) RETURNING *",
        user_id, resume_name, parsed_text
    )
    return dict(row)



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
