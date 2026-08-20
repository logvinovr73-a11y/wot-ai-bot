import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
import google.generativeai as genai

# Отримання ключів з змінних оточення
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Обробник команди /start
@dp.message(flags={"command": "start"})
async def start_handler(message: types.Message):
    await message.answer("👋 Вітаю в AI WoT Academy!\nЯ твій персональний AI-Коуч з World of Tanks.")

# Обробник усіх текстових повідомлень
@dp.message()
async def text_handler(message: types.Message):
    try:
        response = model.generate_content(message.text)
        await message.answer(response.text)
    except Exception as e:
        await message.answer(f"Помилка при обробці запиту: {e}")

# Веб-сервер для заглушки порту Render
async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def main():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    
    # Запуск бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
