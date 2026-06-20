import logging
from sqlalchemy import select
from aiogram import Bot
from src.database.db import async_session_maker
from src.database.models import MoodMatrix, SystemConfig, ChatHistory, InternalDiary
from src.core.emotions import calculate_new_mood
from src.llm.engine import generate_response

logger = logging.getLogger(__name__)

async def background_reflection(bot: Bot):
    """Background agent 'heartbeat'. Smoothly normalizes mood and proactively messages."""
    logger.info("Running background reflection job...")
    async with async_session_maker() as session:
        result = await session.execute(select(MoodMatrix).order_by(MoodMatrix.id.desc()).limit(1))
        mood_record = result.scalars().first()
        current_mood = mood_record.mood if mood_record else 0.5
        
        # In the background, impact is 0, only inertia works (return to baseline)
        new_mood = calculate_new_mood(current_mood, 0.0)
        
        new_record = MoodMatrix(
            mood=new_mood,
            fatigue=mood_record.fatigue if mood_record else 0.0,
            detachment=mood_record.detachment if mood_record else 0.3
        )
        session.add(new_record)
        
        config_result = await session.execute(select(SystemConfig).limit(1))
        system_config = config_result.scalars().first()
        
        # Proactive messaging
        if system_config and system_config.chat_id and not system_config.is_first_run:
            if new_mood >= 0.2:
                # Get last 2 messages for minimal context
                history_result = await session.execute(select(ChatHistory).order_by(ChatHistory.id.desc()).limit(2))
                recent_msgs = history_result.scalars().all()
                recent_msgs.reverse()
                
                context = "\n".join([f"{msg.role}: {msg.message}" for msg in recent_msgs])
                
                prompt = (
                    "СИСТЕМНОЕ СООБЩЕНИЕ: Пользователь давно не писал. Ты сейчас просыпаешься в фоновом режиме. "
                    "Реши сама, хочешь ли ты написать пользователю первой. Если тебе есть что сказать или спросить — "
                    "напиши короткое сообщение после тега </thought>. "
                    "Если ты хочешь промолчать и не беспокоить пользователя — "
                    "ПРОСТО ОСТАВЬ ПОЛЕ ПОСЛЕ ТЕГА </thought> АБСОЛЮТНО ПУСТЫМ (ничего не пиши в ответ). "
                    f"Ваш недавний разговор:\n\n{context}"
                )
                
                # Commit pending writes to release SQLite database lock during long LLM generation
                await session.commit()
                
                response_data = await generate_response(prompt, new_mood, system_config)
                final_output = response_data["final_output"]
                
                if final_output and final_output != "...":
                    await bot.send_message(chat_id=system_config.chat_id, text=final_output)
                    
                    bot_msg = ChatHistory(role="assistant", message=final_output)
                    session.add(bot_msg)
                    
                    diary_entry = InternalDiary(
                        raw_thoughts=response_data["raw_thoughts"],
                        final_output=final_output,
                        captured_mood=new_mood
                    )
                    session.add(diary_entry)
            else:
                logger.info("Mood too low (<0.2) for proactive message. Agent stays quiet.")
        
        await session.commit()
        logger.info(f"Background reflection completed. New mood: {new_mood}")
