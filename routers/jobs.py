from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date
from db.database import get_conn
from db.auth_dep import get_current_user

router = APIRouter()

# Input validation model for creating a job application
class JobCreate(BaseModel):
    company:         str
    role:            str
    job_url:         Optional[str] = ""
    job_description: Optional[str] = ""
    status:          Optional[str] = "Saved"
    notes:           Optional[str] = ""
    applied_date:    Optional[date] = None

# Input validation model for updating a job application
# All fields are optional to allow partial updates (PATCH-like behavior)
class JobUpdate(BaseModel):
    company:         Optional[str] = None
    role:            Optional[str] = None
    job_url:         Optional[str] = None
    job_description: Optional[str] = None
    status:          Optional[str] = None
    notes:           Optional[str] = None
    applied_date:    Optional[date] = None

@router.get("/")
async def list_jobs(user_id: int = Depends(get_current_user), conn=Depends(get_conn)):
    """
    Retrieves all jobs created by the current user,
    ordered by creation date (newest first).
    """
    rows = await conn.fetch(
        "SELECT * FROM jobs WHERE user_id=$1 ORDER BY created_at DESC",
        user_id
    )
    return [dict(r) for r in rows]

@router.post("/")
async def create_job(
    body: JobCreate,
    user_id: int = Depends(get_current_user),
    conn=Depends(get_conn)
):
    """
    Registers a new job application under the currently logged-in user.
    """
    row = await conn.fetchrow(
        """
        INSERT INTO jobs
            (user_id, company, role, job_url, job_description, status, notes, applied_date)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        RETURNING *
        """,
        user_id, body.company, body.role, body.job_url,
        body.job_description, body.status, body.notes, body.applied_date,
    )

    # Log the initial status into history
    await conn.execute(
        "INSERT INTO job_status_history (job_id, from_status, to_status) VALUES ($1, NULL, $2)",
        row["id"], row["status"]
    )

    return dict(row)

@router.get("/{job_id}")
async def get_job(
    job_id: int,
    user_id: int = Depends(get_current_user),
    conn=Depends(get_conn)
):
    """
    Retrieves detailed info for a single job application along with
    all associated AI outputs generated for it (scorer, cover_letter, interview_prep).
    """
    # Fetch job record for the given ID, ensuring it belongs to the logged-in user
    job = await conn.fetchrow(
        "SELECT * FROM jobs WHERE id=$1 AND user_id=$2", job_id, user_id
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    # Fetch any AI generated reports or outputs related to this job
    outputs = await conn.fetch(
        "SELECT * FROM ai_outputs WHERE job_id=$1 ORDER BY created_at DESC", job_id
    )

    # Fetch the full status transition history for this job, oldest-first
    history = await conn.fetch(
        "SELECT * FROM job_status_history WHERE job_id=$1 ORDER BY changed_at ASC", job_id
    )

    return {
        **dict(job),
        "ai_outputs": [dict(o) for o in outputs],
        "status_history": [dict(h) for h in history],
    }

@router.put("/{job_id}")
async def update_job(
    job_id: int,
    body: JobUpdate,
    user_id: int = Depends(get_current_user),
    conn=Depends(get_conn)
):
    """
    Updates specific fields of an existing job application.
    Dynamically generates the SQL update query based on the fields provided.
    """
    # Exclude fields that were not provided in the request payload
    updates = body.dict(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Nothing to update")
        
    # Generate the dynamic SQL set clause: "col1=$1, col2=$2"
    # i+1 corresponds to 1-indexed placeholder indices in asyncpg
    set_clause = ", ".join(f"{k}=${i+1}" for i, k in enumerate(updates.keys()))
    
    # Store the actual values to update in a list
    values = list(updates.values())
    
    # Append job_id and user_id for the WHERE clause constraints
    values.append(job_id)
    values.append(user_id)
    
    # Build query: UPDATE jobs SET col1=$1, col2=$2 WHERE id=$3 AND user_id=$4 RETURNING *
    query = f"UPDATE jobs SET {set_clause} WHERE id=${len(values)-1} AND user_id=${len(values)} RETURNING *"
    
    # Fetch the old status BEFORE updating, so we can log the transition
    old_job = await conn.fetchrow(
        "SELECT status FROM jobs WHERE id=$1 AND user_id=$2", job_id, user_id
    )

    row = await conn.fetchrow(
        f"UPDATE jobs SET {set_clause} WHERE id=${len(values)-1} AND user_id=${len(values)} RETURNING *",
        *values
    )
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    # If status changed, log it
    if "status" in updates and old_job and old_job["status"] != row["status"]:
        await conn.execute(
            "INSERT INTO job_status_history (job_id, from_status, to_status) VALUES ($1, $2, $3)",
            job_id, old_job["status"], row["status"]
        )

    return dict(row)

@router.delete("/{job_id}")
async def delete_job(
    job_id: int,
    user_id: int = Depends(get_current_user),
    conn=Depends(get_conn)
):
    """
    Deletes a job application.
    Relies on ON DELETE CASCADE in the database to automatically delete associated ai_outputs.
    """
    result = await conn.execute(
        "DELETE FROM jobs WHERE id=$1 AND user_id=$2", job_id, user_id
    )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Job not found")
    return {"message": "Job deleted"}
