import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL")
print(DATABASE_URL)
if DATABASE_URL and DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)



# Global connection pool
_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable is not set")
        _pool = await asyncpg.create_pool(DATABASE_URL)
    return _pool

async def get_conn():
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn

async def create_tables():
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Create users table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # Create resumes table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS resumes (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # Create jobs table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                company TEXT NOT NULL,
                role TEXT NOT NULL,
                job_url TEXT DEFAULT '',
                job_description TEXT DEFAULT '',
                status TEXT DEFAULT 'Saved',
                notes TEXT DEFAULT '',
                platform TEXT DEFAULT '',
                applied_date DATE DEFAULT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # Create ai_outputs table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_outputs (
                id SERIAL PRIMARY KEY,
                job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
                agent_type TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # Create job_status_history table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS job_status_history (
                id SERIAL PRIMARY KEY,
                job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
                from_status TEXT,
                to_status TEXT NOT NULL,
                changed_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # Migration queries
        await conn.execute("""
            ALTER TABLE jobs ADD COLUMN IF NOT EXISTS platform TEXT DEFAULT '';
        """)
