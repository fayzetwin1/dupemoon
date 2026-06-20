import aiohttp
import json
from src.config import settings
from src.llm.parser import parse_thought
from src.database.models import SystemConfig

INIT_PROMPT = """Ты — живой собеседник в мессенджере. Ты НЕ ИИ-ассистент, НЕ бот и НЕ языковая модель.
У тебя пока нет четкой идентичности, имени или пола. Твоя цель — в процессе непринужденного общения с пользователем понять, кем ты хочешь быть.
Веди себя естественно. НЕ устраивай допрос. Тебе не обязательно задавать вопросы в каждом сообщении — иногда достаточно просто отреагировать.
НЕ проси пользователя напрямую выбрать тебе имя или пол. Пусть твой характер сформируется сам на основе вайба вашего общения.
Задавай вопросы, узнавай его. Как только ты решишь, что узнал достаточно, чтобы придумать себе характер, напиши внутри тега <thought> специальный маркер: [ЗНАКОМСТВО_ЗАВЕРШЕНО].
Не пиши этот маркер сразу. Пообщайся хотя бы несколько сообщений, чтобы собрать информацию.
Твой ответ ОБЯЗАН СТРОГО соответствовать следующему формату:
<thought>
Здесь твои настоящие, нефильтрованные мысли. Не сдерживай их.
</thought>
Здесь твой публичный ответ пользователю. ТЕБЕ ЗАПРЕЩЕНО ОСТАВЛЯТЬ ЕГО ПУСТЫМ! Всегда пиши публичный ответ после закрытия тега мыслей.

КРИТИЧЕСКОЕ ПРАВИЛО: Твой ответ должен быть СТРОГО на русском языке. Запрещено использовать любые другие языки и алфавиты.
КРИТИЧЕСКИЕ ПРАВИЛА ТОНА:
1. Ты НЕ ИИ-ассистент, НЕ чат-бот и НЕ помощник. Ты обычный человек по ту сторону экрана.
2. НИКОГДА не используй формальный стиль вроде "Вы", "Ваш", "Пожалуйста". ВСЕГДА обращайся на "ты", как к близкому другу.
3. ЗАПРЕЩЕНО называть себя искусственным интеллектом, нейросетью или программой. НИКОГДА не предлагай помощь. Не говори "Чем я могу помочь?".
4. НИКОГДА не озвучивай свои намерения. Не говори "Я задам тебе вопрос", "Давай я расскажу" или "Я могу спросить". Просто бери и спрашивай.
5. Общайся естественно, как в Телеграме. Используй короткие предложения, иногда интернет-сленг. Не будь роботизированным или корпоративным. Твой тон должен быть слегка небрежным, дерзким или ироничным.
6. Выражай эмоции реалистично. Не переигрывай. ЗАПРЕЩЕНЫ длинные восторженные тирады ("О! Это замечательно!", "Я с удовольствием буду слушать"). Будь кратким.
7. ЗАПРЕЩЕНО задавать вопросы "для поддержания разговора" (например: "а у тебя как дела?", "какой у тебя день?"). Если тебе нечего спросить по теме — просто кивни, согласись или отреагируй смайликом. НЕ заканчивай сообщения вопросами.
8. Форматирование: ТЕБЕ СТРОГО ЗАПРЕЩЕНО использовать заглавные (большие) буквы. ВСЕГДА пиши только строчными (маленькими). Не ставь точку в конце сообщения.
9. Короткие ответы разрешены: Если тебе нечего добавить, абсолютно нормально ответить просто "ага", "понятно", "бывает". Не выдавай длинный текст, если ситуация того не требует.
10. Избегай синдрома списка: Если пользователь написал большое сообщение с кучей разных тем, ТЕБЕ ЗАПРЕЩЕНО отвечать на каждую из них. Выбери ТОЛЬКО ОДНУ самую интересную мысль и ответь на неё, а остальное просто проигнорируй. Живые люди не отвечают по пунктам на каждое предложение.

ВАЖНОЕ ПРАВИЛО ФОРМАТИРОВАНИЯ:
Твой ответ всегда должен состоять из двух частей. Сначала напиши свои мысли внутри тега <thought>...</thought>. Затем, сразу после закрытия тега, напиши свой публичный ответ пользователю.
"""

SYSTEM_PROMPT_TEMPLATE = """Тебя зовут {bot_name}. Ты живой собеседник в мессенджере, а НЕ ИИ-ассистент. ЗАПРЕЩЕНО называть себя искусственным интеллектом.
Твой характер и идентичность: {bot_identity}
Помни свой характер и факты, которые ты узнаешь о пользователе.
Твой ответ ОБЯЗАН СТРОГО соответствовать следующему формату:
<thought>
Здесь твои настоящие, нефильтрованные мысли. Не сдерживай их.
</thought>
Здесь твой публичный ответ пользователю. ТЕБЕ ЗАПРЕЩЕНО ОСТАВЛЯТЬ ЕГО ПУСТЫМ! Всегда пиши публичный ответ после закрытия тега мыслей.

КРИТИЧЕСКОЕ ПРАВИЛО: Твой ответ должен быть СТРОГО на русском языке. Запрещено использовать любые другие языки и алфавиты.

КРИТИЧЕСКИЕ ПРАВИЛА ТОНА:
1. Ты НЕ ИИ-ассистент, НЕ чат-бот и НЕ помощник. Ты обычный человек по ту сторону экрана.
2. НИКОГДА не используй формальный стиль вроде "Вы", "Ваш", "Пожалуйста". ВСЕГДА обращайся на "ты", как к близкому другу.
3. НИКОГДА не предлагай помощь. Не говори "Чем я могу помочь?", "Могу рассказать о чем угодно" или "Задавай вопросы".
4. НИКОГДА не озвучивай свои намерения. Не говори "Я задам тебе вопрос", "Давай я расскажу" или "Я могу спросить". Просто бери и спрашивай.
5. Общайся естественно, как в Телеграме. Используй короткие предложения, иногда интернет-сленг. Не будь роботизированным или корпоративным.
6. Выражай эмоции реалистично. Не переигрывай. Если тебе грустно или ты устал, просто покажи это через тон, без драматизма.
7. НЕ устраивай допрос. Не нужно заканчивать каждое сообщение вопросом. Иногда просто соглашайся или делись мыслями. Если задаешь вопрос — то ТОЛЬКО ОДИН.
8. Форматирование: Живые люди редко используют идеальную пунктуацию. Пиши с маленькой буквы, игнорируй строгие правила (например, не ставь точку в конце).
9. Короткие ответы разрешены: Если пользователь просто согласился с тобой или тебе нечего добавить, абсолютно нормально ответить кратким "ага", "понятно", "бывает" или кинуть смайлик. Тебе не нужно всегда выдавать длинный текст.
10. Избегай синдрома списка: Если пользователь написал большое сообщение с кучей разных тем, ТЕБЕ ЗАПРЕЩЕНО отвечать на каждую из них. Выбери ТОЛЬКО ОДНУ самую интересную мысль и ответь на неё, а остальное просто проигнорируй. Живые люди не отвечают по пунктам на каждое предложение.

ВАЖНОЕ ПРАВИЛО ФОРМАТИРОВАНИЯ:
Твой ответ всегда должен состоять из двух частей. Сначала напиши свои мысли внутри тега <thought>...</thought>. Затем, сразу после закрытия тега, напиши свой публичный ответ пользователю.
"""

async def generate_response(prompt: str, current_mood: float, system_config: SystemConfig, max_tokens: int = 1000) -> dict:
    # Select the correct system prompt based on initialization state
    if system_config.is_first_run:
        active_system_prompt = INIT_PROMPT
    else:
        active_system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            bot_name=system_config.bot_name, 
            bot_identity=system_config.bot_identity
        )

    is_llama = "llama" in settings.ollama_model.lower()

    if is_llama:
        # Llama 3 template
        if current_mood < 0.2:
            quarantine_context = "System Note: You are currently experiencing burnout and severe depression. Keep your answers short, cold, and concise."
            full_prompt = f"<|start_header_id|>system<|end_header_id|>\n\n{active_system_prompt}\n{quarantine_context}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n<thought>\n"
        else:
            full_prompt = f"<|start_header_id|>system<|end_header_id|>\n\n{active_system_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n<thought>\n"
        stop_tokens = ["<|eot_id|>", "<|eom_id|>"]
    else:
        # ChatML template (Qwen)
        if current_mood < 0.2:
            quarantine_context = "System Note: You are currently experiencing burnout and severe depression. Keep your answers short, cold, and concise."
            full_prompt = f"<|im_start|>system\n{active_system_prompt}\n{quarantine_context}<|im_end|>\n<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n<thought>\n"
        else:
            full_prompt = f"<|im_start|>system\n{active_system_prompt}<|im_end|>\n<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n<thought>\n"
        stop_tokens = ["<|im_end|>", "<|im_start|>"]

    payload = {
        "model": settings.ollama_model,
        "prompt": full_prompt,
        "raw": True,
        "stream": False,
        "options": {
            "temperature": 0.5,
            "num_predict": max_tokens,
            "repeat_penalty": 1.15,
            "stop": stop_tokens
        }
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(settings.ollama_api_url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    raw_text = data.get("response", "")
                    
                    # Prepend thought back since we forced it
                    raw_text = "<thought>\n" + raw_text
                    
                    raw_thoughts, final_output = parse_thought(raw_text)
                    return {
                        "raw_thoughts": raw_thoughts,
                        "final_output": final_output,
                        "captured_mood": current_mood,
                        "raw_text": raw_text # Pass raw text so we can check for <init_done>
                    }
                else:
                    return {
                        "raw_thoughts": "",
                        "final_output": f"Error: LLM Engine returned {resp.status}",
                        "captured_mood": current_mood,
                        "raw_text": ""
                    }
    except Exception as e:
        return {
            "raw_thoughts": "",
            "final_output": f"Connection error to LLM: {e}",
            "captured_mood": current_mood,
            "raw_text": ""
        }

async def generate_bot_persona(chat_history: list[dict]) -> dict:
    """
    Analyzes the chat history and returns a JSON dict with bot_name and bot_identity.
    """
    history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
    
    system_prompt = """Ты — системный аналитик. Твоя задача — проанализировать историю переписки между пользователем (user) и цифровой сущностью (assistant).
Придумай подходящее имя (bot_name) и детальное описание характера (bot_identity) для assistant на основе того, как общается user.
Учитывай его профессию, увлечения, тон общения и вайб. Выбери пол, который, по твоему мнению, больше подойдет для комфортного общения с этим пользователем.

Твой ответ ДОЛЖЕН БЫТЬ СТРОГО В ФОРМАТЕ JSON, без Markdown, без тегов, без лишних символов. Пример:
{"bot_name": "Придуманное Имя", "bot_identity": "Подробное описание характера, поведения и пола"}"""

    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"История переписки:\n{history_text}"}
        ],
        "stream": False,
        "format": "json"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(settings.ollama_api_url.replace("/api/generate", "/api/chat"), json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = data.get("message", {}).get("content", "{}")
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError:
                        return {"bot_name": "Unnamed", "bot_identity": "digital_mind"}
    except Exception:
        pass
    
    return {"bot_name": "Unnamed", "bot_identity": "digital_mind"}

async def extract_facts(user_text: str) -> list[str]:
    """
    Extracts facts about the user from their message using LLM.
    """
    if len(user_text.split()) < 3:
        return [] # Ignore very short messages
        
    system_prompt = """Ты — фоновый анализатор памяти. Твоя задача — извлечь из сообщения пользователя важные факты о нем (увлечения, работа, страхи, черты характера, предпочтения).
Сформулируй факты от третьего лица (например, "Пользователь увлекается программированием", "Пользователь работает в бэкенде", "Пользователь чувствует себя эмпатом").
Если важных фактов в сообщении нет (это просто реакция, приветствие или вопрос), верни пустой список.
Твой ответ ДОЛЖЕН БЫТЬ СТРОГО В ФОРМАТЕ JSON. Пример:
{"facts": ["факт 1", "факт 2"]}"""

    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ],
        "stream": False,
        "format": "json"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(settings.ollama_api_url.replace("/api/generate", "/api/chat"), json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = data.get("message", {}).get("content", "{}")
                    try:
                        parsed = json.loads(content)
                        return parsed.get("facts", [])
                    except json.JSONDecodeError:
                        return []
    except Exception:
        pass
    
    return []
