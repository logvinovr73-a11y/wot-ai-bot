import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
import google.generativeai as genai
import edge_tts

# Налаштування логування
logging.basicConfig(level=logging.INFO)

# Зчитування ключів з налаштувань сервера (ENV variables)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Ініціалізація Gemini API
genai.configure(api_key=GEMINI_API_KEY)

# Використовуємо високошвидкісну мультимодальну модель Gemini 1.5 Flash
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

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction=SYSTEM_PROMPT
)

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

        # Передача файлу в Gemini File API
        uploaded_file = genai.upload_file(file_path)
        
        prompt = "Проаналізуй цей бій World of Tanks. Вкажи 3 головні помилки гравця з таймкодами, розбери позиціювання та дай підсумкову таблицю порад."
        response = model.generate_content([uploaded_file, prompt])
        
        await status_msg.edit_text("🎙️ **Генеруємо голосовий коментар...** [85%]")

        # Генерація голосового резюме (Edge-TTS)
        tts_text = f"Проаналізовано бій. Ось головний підсумок: {response.text[:300]}"
        voice_path = f"voice_{file_id}.mp3"
        communicate = edge_tts.Communicate(tts_text, "uk-UA-OstapNeural")
        await communicate.save(voice_path)

        # Надсилання тексту + аудіо
        await message.answer(response.text, parse_mode="Markdown")
        await message.answer_voice(types.FSInputFile(voice_path))

        # Очищення тимчасових файлів
        os.remove(file_path)
        os.remove(voice_path)
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Error processing video: {e}")
        await status_msg.edit_text("❌ Сталася помилка під час обробки відео. Переконайся, що файл не пошкоджений.")

# Текстовий діалог та відповіді на питання (Реплаї, ТТХ, Патчі)
@dp.message(F.text)
async def handle_text_questions(message: types.Message):
    response = model.generate_content(message.text)
    await message.answer(response.text, parse_mode="Markdown")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
