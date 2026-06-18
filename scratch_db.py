import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    dsn = os.getenv("DATABASE_URL")
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    
    conn = await asyncpg.connect(dsn)
    
    tables = ['users', 'jobs', 'resumes', 'applications']
    for t in tables:
        try:
            count = await conn.fetchval(f"SELECT COUNT(*) FROM {t}")
            print(f"Table '{t}' has {count} rows.")
        except Exception as e:
            print(f"Could not count table '{t}': {e}")
            
    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
