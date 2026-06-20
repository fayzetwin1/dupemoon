from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.config import settings
from src.database.models import Base

# sqlite+aiosqlite
engine = create_async_engine(settings.db_url, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    # Only if we want to run without migrations
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.create_all)
    pass
