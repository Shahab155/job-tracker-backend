import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    dsn = os.getenv("DATABASE_URL")
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    
    print("Connecting to:", dsn)
    conn = await asyncpg.connect(dsn)
    
    print("Dropping old/conflicting empty tables...")
    await conn.execute("""
        DROP TABLE IF EXISTS applications CASCADE;
        DROP TABLE IF EXISTS resumes CASCADE;
        DROP TABLE IF EXISTS jobs CASCADE;
        DROP TABLE IF EXISTS users CASCADE;
        DROP TABLE IF EXISTS ai_outputs CASCADE;
    """)
    print("Drop completed successfully!")
    
    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
