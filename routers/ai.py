

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from db.database import get_conn
from db.auth_dep import get_current_user
from custom_agents.ai_agents import run_agent_once, run_agent_chat
from utils.resume_selector import select_best_resume

router = APIRouter()

class RunAgentRequest(BaseModel):
    job_id:     int
    agent_type: str
    resume_id:  Optional[int] = None  # None = auto-select

class ChatMessage(BaseModel):
    role:    str
    content: str

class ChatRequest(BaseModel):
    job_id:     int
    agent_type: str
    messages:   list[ChatMessage]

VALID_TYPES = {"scorer", "cover_letter", "interview_prep"}

@router.post("/run-agent")
async def run_agent(
    body: RunAgentRequest,
    user_id: int = Depends(get_current_user),
    conn=Depends(get_conn)
):
    if body.agent_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail="Invalid agent_type")

    job = await conn.fetchrow(
        "SELECT company, role, job_description FROM jobs WHERE id=$1 AND user_id=$2",
        body.job_id, user_id
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # ── Resume selection ───────────────────────────────────────────────────────
    if body.resume_id:
        # Manual override — fetch only the selected resume
        resume = await conn.fetchrow(
            "SELECT id, name, content FROM resumes WHERE id=$1 AND user_id=$2",
            body.resume_id, user_id
        )
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        selected = dict(resume)
    else:
        # Auto-select — fetch all resumes, pick best by keyword match
        rows = await conn.fetch(
            "SELECT id, name, content FROM resumes WHERE user_id=$1", user_id
        )
        if not rows:
            raise HTTPException(status_code=400, detail="No resumes found. Add a resume first.")
        selected = select_best_resume(job["job_description"], [dict(r) for r in rows])

    # ── Build agent input ──────────────────────────────────────────────────────
    user_message = f"""
RESUME ({selected['name']}):
{selected['content']}

JOB TITLE: {job['role']} at {job['company']}

JOB DESCRIPTION:
{job['job_description'] or 'No job description provided.'}
""".strip()

    try:
        result = await run_agent_once(body.agent_type, user_message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    # ── Save result ────────────────────────────────────────────────────────────
    existing = await conn.fetchrow(
        "SELECT id FROM ai_outputs WHERE job_id=$1 AND agent_type=$2",
        body.job_id, body.agent_type
    )
    if existing:
        await conn.execute(
            "UPDATE ai_outputs SET content=$1, created_at=NOW() WHERE id=$2",
            result, existing["id"]
        )
    else:
        await conn.execute(
            "INSERT INTO ai_outputs (job_id, agent_type, content) VALUES ($1,$2,$3)",
            body.job_id, body.agent_type, result
        )

    return {
        "result": result,
        "agent_type": body.agent_type,
        "resume_used": selected["name"]   # tell frontend which resume was picked
    }


@router.post("/chat")
async def agent_chat(
    body: ChatRequest,
    user_id: int = Depends(get_current_user),
    conn=Depends(get_conn)
):
    if body.agent_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail="Invalid agent_type")

    job = await conn.fetchrow(
        "SELECT id FROM jobs WHERE id=$1 AND user_id=$2", body.job_id, user_id
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    try:
        reply = await run_agent_chat(body.agent_type, messages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    return {"reply": reply}


@router.get("/outputs")
async def get_user_ai_outputs(
    user_id: int = Depends(get_current_user),
    conn=Depends(get_conn)
):
    """
    Fetches all AI outputs for the current logged-in user across all of their jobs.
    """
    rows = await conn.fetch(
        """
        SELECT 
            ao.id, 
            ao.job_id, 
            ao.agent_type, 
            ao.content, 
            ao.created_at,
            j.company,
            j.role
        FROM ai_outputs ao
        JOIN jobs j ON ao.job_id = j.id
        WHERE j.user_id = $1
        ORDER BY ao.created_at DESC
        """,
        user_id
    )
    return [dict(r) for r in rows]