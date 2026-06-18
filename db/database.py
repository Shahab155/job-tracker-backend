import asyncpg
import os
from dotenv import load_dotenv

# Load configuration details like DATABASE_URL from .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)


# Singleton variable to hold the asyncpg connection pool across the application lifecycle
_pool = None

async def get_pool():
    """
    Initializes and returns the shared connection pool.
    Reuses the existing pool if already instantiated.
    """
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL)
    return _pool

async def get_conn():
    """
    Async generator used as a FastAPI Dependency.
    Acquires a database connection from the pool and automatically releases it
    back to the pool after the calling endpoint completes.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn

async def create_tables():
    """
    Bootstrap operation executed on startup to build the required tables
    if they do not already exist in the database.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Create core tables: users, jobs, and ai_outputs with constraints
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          SERIAL PRIMARY KEY,
                email       TEXT UNIQUE NOT NULL,
                password    TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS resumes (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
                name       TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id              SERIAL PRIMARY KEY,
                user_id         INTEGER REFERENCES users(id) ON DELETE CASCADE,
                company         TEXT NOT NULL,
                role            TEXT NOT NULL,
                job_url         TEXT DEFAULT '',
                job_description TEXT DEFAULT '',
                status          TEXT DEFAULT 'Saved'
                                    CHECK (status IN ('Saved','Applied','Interview','Offer','Rejected')),
                notes           TEXT DEFAULT '',
                applied_date    DATE,
                created_at      TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS ai_outputs (
                id          SERIAL PRIMARY KEY,
                job_id      INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
                agent_type  TEXT NOT NULL
                                CHECK (agent_type IN ('scorer','cover_letter','interview_prep')),
                content     TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS job_status_history (
                id          SERIAL PRIMARY KEY,
                job_id      INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
                from_status TEXT,
                to_status   TEXT NOT NULL,
                changed_at  TIMESTAMP DEFAULT NOW()
            );
        """)
    print("✅ Tables ready")
