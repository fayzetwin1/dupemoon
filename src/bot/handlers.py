import asyncio
from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import select
from src.database.db import async_session_maker
from src.database.models import ChatHistory, InternalDiary, MoodMatrix, SystemConfig
from src.llm.engine import generate_response, generate_bot_persona, extract_facts
from src.database.vectors import search_facts, add_fact
from src.core.emotions import calculate_new_mood

router = Router()

async def send_typing_loop(bot, chat_id):
    """Periodically sends a 'typing' action to Telegram while waiting."""
    while True:
        try:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
            await asyncio.sleep(4)
        except asyncio.CancelledError:
            break

async def process_and_save_facts(user_text: str):
    """Background task to extract and save facts to LanceDB."""
    facts = await extract_facts(user_text)
    if facts:
        # Wrap the synchronous add_fact in a thread to prevent blocking the async loop, just in case
        for fact in facts:
            await asyncio.to_thread(add_fact, fact)

@router.message(Command("start"))
async def start_handler(message: types.Message):
    async with async_session_maker() as session:
        config_result = await session.execute(select(SystemConfig).limit(1))
        system_config = config_result.scalars().first()
        
        if not system_config:
            system_config = SystemConfig(chat_id=message.chat.id)
            session.add(system_config)
            await session.commit()
        elif not system_config.chat_id:
            system_config.chat_id = message.chat.id
            await session.commit()
        
        if not system_config or system_config.is_first_run:
            await message.answer(
                "Привет! Я — твой новый локальный ИИ-компаньон.\n\n"
                "Мой разум только что был активирован, и сейчас я — чистый лист. "
                "Я еще не знаю, кто я, как меня зовут и какой у меня характер. Я сформирую всё это сам, "
                "исходя из того, как мы с тобой будем общаться.\n\n"
                "Давай просто поболтаем? Расскажи мне немного о себе: чем ты увлекаешься, как у тебя дела, о чем любишь думать?"
            )
        else:
            await message.answer(f"С возвращением! Твой компаньон {system_config.bot_name} на связи. Чем займемся?")

@router.message(Command("thoughts"))
async def thoughts_handler(message: types.Message):
    async with async_session_maker() as session:
        config_result = await session.execute(select(SystemConfig).limit(1))
        system_config = config_result.scalars().first()
        
        if not system_config:
            system_config = SystemConfig(chat_id=message.chat.id)
            session.add(system_config)
            await session.commit()
        elif not system_config.chat_id:
            system_config.chat_id = message.chat.id
            await session.commit()
            
        # Get the last 3 diary entries where raw_thoughts is not empty
        result = await session.execute(
            select(InternalDiary)
            .filter(InternalDiary.raw_thoughts != "")
            .filter(InternalDiary.raw_thoughts != None)
            .order_by(InternalDiary.id.desc())
            .limit(3)
        )
        entries = result.scalars().all()
        
        if not entries:
            await message.answer("Пока нет никаких мыслей.")
            return
            
        response_lines = ["🧠 **Окно мыслей (Последние 3 записи):**\n"]
        for entry in reversed(entries):
            # Format timestamp nicely
            time_str = entry.timestamp.strftime("%H:%M:%S") if entry.timestamp else "Unknown"
            mood_val = round(entry.captured_mood, 2) if entry.captured_mood else "N/A"
            thoughts = entry.raw_thoughts.strip()
            
            response_lines.append(f"🕒 {time_str} (Настроение: {mood_val})")
            response_lines.append(f"💭 {thoughts}\n")
            
        await message.answer("\n".join(response_lines), parse_mode="Markdown")

@router.message()
async def message_handler(message: types.Message):
    user_text = message.text
    
    async with async_session_maker() as session:
        user_msg = ChatHistory(role="user", message=user_text)
        session.add(user_msg)
        
        result = await session.execute(select(MoodMatrix).order_by(MoodMatrix.id.desc()).limit(1))
        mood_record = result.scalars().first()
        current_mood = mood_record.mood if mood_record else 0.5
        
        # Simple RAG: fetch facts from LanceDB
        # In a real system, use a separate prompt to extract facts from user text
        facts = search_facts(user_text)
        context_facts = "\n".join([f.fact_text for f in facts])
        
        # Fetch or create SystemConfig
        config_result = await session.execute(select(SystemConfig).limit(1))
        system_config = config_result.scalars().first()
        if not system_config:
            system_config = SystemConfig(chat_id=message.chat.id)
            session.add(system_config)
            await session.commit()
            
        if not system_config.chat_id:
            system_config.chat_id = message.chat.id
            await session.commit()
            
        # Add facts to the prompt if available
        prompt_with_context = user_text
        if context_facts:
            prompt_with_context = f"Воспоминания:\n{context_facts}\n\nПользователь: {user_text}"
            
        # Commit pending writes to release SQLite database lock during long LLM generation
        await session.commit()
        
        # Start typing loop for better UX during slow LLM generation
        typing_task = asyncio.create_task(send_typing_loop(message.bot, message.chat.id))
        
        try:
            response_data = await generate_response(prompt_with_context, current_mood, system_config)
        finally:
            typing_task.cancel()
            
        final_output = response_data["final_output"]
        
        # Re-fetch config to avoid DetachedInstanceError after the previous commit
        config_result = await session.execute(select(SystemConfig).limit(1))
        system_config = config_result.scalars().first()

        # Check if initialization was completed
        if system_config.is_first_run and "[ЗНАКОМСТВО_ЗАВЕРШЕНО]" in response_data.get("raw_thoughts", ""):
            history_result = await session.execute(select(ChatHistory).order_by(ChatHistory.id.asc()))
            chat_history = [{"role": msg.role, "content": msg.message} for msg in history_result.scalars().all()]
            
            init_data = await generate_bot_persona(chat_history)
            
            system_config.is_first_run = False
            system_config.bot_name = init_data.get("bot_name", system_config.bot_name)
            system_config.bot_identity = init_data.get("bot_identity", system_config.bot_identity)

        
        if not final_output:
            final_output = "..."
        
        bot_msg = ChatHistory(role="assistant", message=final_output)
        session.add(bot_msg)
        
        diary_entry = InternalDiary(
            raw_thoughts=response_data["raw_thoughts"],
            final_output=response_data["final_output"],
            captured_mood=response_data["captured_mood"]
        )
        session.add(diary_entry)
        
        impact = 0.05
        new_mood = calculate_new_mood(current_mood, impact)
        new_mood_record = MoodMatrix(
            mood=new_mood,
            fatigue=mood_record.fatigue if mood_record else 0.0,
            detachment=mood_record.detachment if mood_record else 0.3
        )
        session.add(new_mood_record)
        
        await session.commit()
    
    # Launch background fact extraction (MVP level)
    asyncio.create_task(process_and_save_facts(user_text))
    
    await message.answer(final_output)
