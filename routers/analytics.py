from fastapi import APIRouter, Depends
from db.database import get_conn
from db.auth_dep import get_current_user
from collections import defaultdict
from datetime import datetime, timedelta

router = APIRouter()

STATUS_ORDER = ["Saved", "Applied", "Interview", "Offer", "Rejected"]

@router.get("/summary")
async def get_analytics(
    user_id: int = Depends(get_current_user),
    conn=Depends(get_conn)
):
    # ── 1. Status funnel — current count per status ──────────────────────
    funnel_rows = await conn.fetch(
        """
        SELECT status, COUNT(*) as count
        FROM jobs WHERE user_id=$1
        GROUP BY status
        """,
        user_id
    )
    funnel = {s: 0 for s in STATUS_ORDER}
    for r in funnel_rows:
        funnel[r["status"]] = r["count"]

    # ── 2. Applications over time — last 8 weeks ──────────────────────────
    time_rows = await conn.fetch(
        """
        SELECT DATE_TRUNC('week', created_at) as week, COUNT(*) as count
        FROM jobs
        WHERE user_id=$1 AND created_at > NOW() - INTERVAL '8 weeks'
        GROUP BY week ORDER BY week
        """,
        user_id
    )
    timeline = [{"week": r["week"].strftime("%b %d"), "count": r["count"]} for r in time_rows]

    # ── 3. Conversion rates ────────────────────────────────────────────────
    total_jobs = sum(funnel.values())
    applied_or_further = sum(funnel[s] for s in ["Applied", "Interview", "Offer", "Rejected"])
    interview_or_further = sum(funnel[s] for s in ["Interview", "Offer", "Rejected"])
    offers = funnel["Offer"]

    conversion = {
        "saved_to_applied": round((applied_or_further / total_jobs * 100), 1) if total_jobs else 0,
        "applied_to_interview": round((interview_or_further / applied_or_further * 100), 1) if applied_or_further else 0,
        "interview_to_offer": round((offers / interview_or_further * 100), 1) if interview_or_further else 0,
    }

    # ── 4. Average time spent in each stage ──────────────────────────────
    history_rows = await conn.fetch(
        """
        SELECT job_id, from_status, to_status, changed_at
        FROM job_status_history
        WHERE job_id IN (SELECT id FROM jobs WHERE user_id=$1)
        ORDER BY job_id, changed_at
        """,
        user_id
    )

    # Group history by job_id, then compute time between consecutive entries
    by_job = defaultdict(list)
    for r in history_rows:
        by_job[r["job_id"]].append(r)

    stage_durations = defaultdict(list)  # status -> [days, days, ...]
    for job_id, entries in by_job.items():
        for i in range(len(entries) - 1):
            stage = entries[i]["to_status"]
            duration = (entries[i + 1]["changed_at"] - entries[i]["changed_at"]).total_seconds() / 86400
            stage_durations[stage].append(duration)

    avg_time_in_stage = {
        stage: round(sum(durs) / len(durs), 1)
        for stage, durs in stage_durations.items()
    }

    return {
        "funnel": funnel,
        "timeline": timeline,
        "conversion": conversion,
        "avg_time_in_stage": avg_time_in_stage,
        "total_jobs": total_jobs,
    }
