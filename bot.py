import asyncio
import time
import os
import re
import httpx
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# 🔐 Берем токен из Railway Variables
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не установлен")

bot = Bot(TOKEN)
dp = Dispatcher()

# --------------------------
# Кэш курсов
# --------------------------
cache = {}
CACHE_TTL = 10  # секунд


async def get_usdt_rate():
    url = "https://www.bestchange.ru/tether-trc20-to-sberbank.html"

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()

    text = BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)
    candidates = re.findall(r"\b\d{2,4}[.,]\d{1,4}\b", text)

    return candidates[0].replace(",", ".") if candidates else None


async def get_cached_rate():
    now = time.time()
    if cache.get("rate") and now - cache.get("ts", 0) < CACHE_TTL:
        return cache["rate"]

    rate = await get_usdt_rate()
    cache["rate"] = rate
    cache["ts"] = now
    return rate


# ✅ Клавиатура с кнопкой "Курс"
def main_keyboard():
    keyboard = [
        [KeyboardButton(text="Курс")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True
    )


# 🔹 Команда /start
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "Привет 👋\nНажми кнопку «Курс», чтобы узнать курс USDT → RUB",
        reply_markup=main_keyboard()
    )


# 🔹 Обработка кнопки "Курс"
@dp.message(lambda message: message.text == "Курс")
async def course_button_handler(message: types.Message):
    rate = await get_cached_rate()
    if rate:
        await message.answer(f"💰 Курс USDT → RUB: {rate}")
    else:
        await message.answer("Не удалось получить курс. Попробуй позже.")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
