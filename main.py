import asyncio
import logging
from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from src.config import settings
from src.database.db import engine, Base, async_session_maker
from src.database.vectors import init_vector_db
from src.bot.handlers import router
from src.scheduler.jobs import background_reflection
from src.database.models import MoodMatrix

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_db_and_defaults():
    # Create tables (useful before alembic setup or as fallback)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Add base mood if DB is empty
    async with async_session_maker() as session:
        result = await session.execute(select(MoodMatrix).limit(1))
        if not result.scalars().first():
            session.add(MoodMatrix(mood=settings.base_mood))
            await session.commit()

async def main():
    logger.info("Initializing database...")
    await init_db_and_defaults()
    
    logger.info("Initializing vector DB...")
    init_vector_db()
    
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    
    logger.info("Starting APScheduler...")
    scheduler = AsyncIOScheduler()
    # Run reflection every 30 minutes, pass bot instance
    scheduler.add_job(background_reflection, 'interval', minutes=30, args=[bot])
    scheduler.start()
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
