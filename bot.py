import asyncio
import time
import os
import httpx
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# ✅ Берем токен ТОЛЬКО из переменной окружения
TOKEN = os.environ.get("BOT_TOKEN")

if not TOKEN:
    raise ValueError("❌ Переменная окружения BOT_TOKEN не установлена!")

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

    soup = BeautifulSoup(r.text, "html.parser")

    import re
    text = soup.get_text(" ", strip=True)
    candidates = re.findall(r"\b\d{2,4}[.,]\d{1,4}\b", text)

    if candidates:
        return candidates[0].replace(",", ".")

    return None


async def get_cached_rate():
    now = time.time()
    if "rate" in cache and now - cache.get("ts", 0) < CACHE_TTL:
        return cache["rate"]

    rate = await get_usdt_rate()
    cache["rate"] = rate
    cache["ts"] = now
    return rate


def main_keyboard():
    kb = [
        [KeyboardButton(text="/курс")],
        [KeyboardButton(text="Помощь")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "Привет! Я показываю курс USDT → RUB.\nНажми /курс.",
        reply_markup=main_keyboard(),
    )


@dp.message(Command("курс"))
async def rate_handler(message: types.Message):
    rate = await get_cached_rate()
    if rate:
        await message.answer(f"Курс USDT → RUB: {rate}")
    else:
        await message.answer("Не удалось получить курс. Попробуй позже.")


@dp.message()
async def any_text(message: types.Message):
    text = (message.text or "").lower()

    if text in ["/курс", "курс"]:
        await rate_handler(message)
    elif text == "помощь":
        await message.answer("Команды:\n/start\n/курс")
    else:
        await message.answer("Нажми /курс 🙂")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())