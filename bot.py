import os
import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from google import genai
from google.genai import types as genai_types
import edge_tts

# Налаштування логування
logging.basicConfig(level=logging.INFO)

# Зчитування ключів
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Ініціалізація нового клієнта Gemini API
client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """
Ти — професійний AI-тренер і аналітик з World of Tanks (WoT). 
Твоє завдання — аналізувати надані відеозаписи або файли боїв, карти, ТТХ техніки та помилки гравця.

Коли гравець надсилає відео чи запитання:
1. Вказуй конкретні таймкоди помилок (наприклад, 01:23 - передчасний виїзд без засвіту).
2. Пояснюй тактику на даній карті (Малинівка, Прохорівка тощо) для конкретного типу техніки (ПТ-САУ, СТ, ТТ, ЛТ).
3. Використовуй табличний формат для зведення помилок та порад.
4. Пояснюй механіки броні, пробиття, екранів та вибору обладнання/перків.
5. Відповідай максимально професійно, конструктивно, з гумором та креативом!
"""

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Команда /start
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    welcome_text = (
        "👋 **Вітаю в AI WoT Academy!**\n\n"
        "Я твій персональний AI-Коуч з World of Tanks.\n\n"
        "🎬 **Надішли мені відеозапис чи реплей бою**, і я за 60 секунд зроблю повний розбір:\n"
        "• Таймкоди та аналіз помилок\n"
        "• Розбір дій команди та ворогів\n"
        "• Поради щодо позицій, ТТХ та обладнання\n\n"
        "❓ Також ти можеш поставити будь-яке запитання щодо гри, патчів чи механік!"
    )
    await message.answer(welcome_text, parse_mode="Markdown")

# Обробка відеозаписів
@dp.message(F.video | F.document)
async def handle_gameplay_video(message: types.Message):
    status_msg = await message.answer("📥 **Відео прийнято!** [10%]\nЗавантажую файл на сервер...")
    
    try:
        file_id = message.video.file_id if message.video else message.document.file_id
        file_info = await bot.get_file(file_id)
        file_path = f"temp_{file_id}.mp4"
        
        await bot.download_file(file_info.file_path, file_path)
        await status_msg.edit_text("🧠 **Gemini аналізує бій...** [50%]\nВиявляємо помилки, таймкоди та позиціонування...")

        uploaded_file = client.files.upload(file=file_path)
        prompt = "Проаналізуй цей бій World of Tanks. Вкажи 3 головні помилки гравця з таймкодами, розбери позиціювання та дай підсумкову таблицю порад."
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, 
            lambda: client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[uploaded_file, prompt],
                config=genai_types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT)
            )
        )
        
        await status_msg.edit_text("🎙️ **Генеруємо голосовий коментар...** [85%]")

        tts_text = f"Проаналізовано бій. Ось головний підсумок: {response.text[:300]}"
        voice_path = f"voice_{file_id}.mp3"
        communicate = edge_tts.Communicate(tts_text, "uk-UA-OstapNeural")
        await communicate.save(voice_path)

        await message.answer(response.text, parse_mode="Markdown")
        await message.answer_voice(types.FSInputFile(voice_path))

        if os.path.exists(file_path):
            os.remove(file_path)
        if os.path.exists(voice_path):
            os.remove(voice_path)
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Error processing video: {e}")
        await status_msg.edit_text(f"❌ Сталася помилка під час обробки: {e}")

# Текстовий діалог
@dp.message(F.text)
async def handle_text_questions(message: types.Message):
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model="gemini-2.5-flash",
                contents=message.text,
                config=genai_types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT)
            )
        )
        await message.answer(response.text, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error processing text: {e}")
        await message.answer(f"❌ Виникла помилка: {e}")

# Веб-сервер для утримання порту Render
async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def main():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
