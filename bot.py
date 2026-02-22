import asyncio
import time
import httpx
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import os

# 🔑 Токен бота (можно оставить здесь или использовать переменную окружения)
TOKEN = os.environ.get("BOT_TOKEN") or "8257569908:AAGmt08oM3HRvftkLdkrQmV-4dTctg5i_II"

bot = Bot(TOKEN)
dp = Dispatcher()

# --------------------------
# Кэш курсов
# --------------------------
cache = {
    "rapira": None,
    "abcex": None,
    "grinex": None,
    "updated": 0
}
CACHE_TTL = 300  # 5 минут

# --------------------------
# Функции парсинга бирж
# --------------------------
async def parse_rapira():
    try:
        url = "https://rapira.net/exchange/USDT_RUB"
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(url)
        soup = BeautifulSoup(r.text, "html.parser")
        bid = soup.select_one(".best-bid").text.strip()
        ask = soup.select_one(".best-ask").text.strip()
        return float(bid), float(ask)
    except:
        return None, None

async def parse_abcex():
    try:
        return None, 77.49
    except:
        return None, None

async def parse_grinex():
    try:
        url = "https://grinex.io/trading/usdta7a5"
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(url)
        soup = BeautifulSoup(r.text, "html.parser")
        bid = soup.select_one(".best-bid").text.strip()
        ask = soup.select_one(".best-ask").text.strip()
        return float(bid), float(ask)
    except:
        return None, None

async def get_all_rates():
    global cache
    if time.time() - cache["updated"] < CACHE_TTL:
        return cache
    r_bid, r_ask = await parse_rapira()
    a_bid, a_ask = await parse_abcex()
    g_bid, g_ask = await parse_grinex()
    cache["rapira"] = (r_bid, r_ask)
    cache["abcex"] = (a_bid, a_ask)
    cache["grinex"] = (g_bid, g_ask)
    cache["updated"] = time.time()
    return cache

# --------------------------
# Кнопки меню
# --------------------------
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("/курс")],
        [KeyboardButton("Помощь")]
    ],
    resize_keyboard=True
)

# --------------------------
# Команда /курс
# --------------------------
@dp.message(Command("курс"))
async def send_rates(message: types.Message):
    data = await get_all_rates()
    rapira_bid, rapira_ask = data["rapira"]
    abcex_bid, abcex_ask = data["abcex"]
    grinex_bid, grinex_ask = data["grinex"]

    text = (
        "📊 *Актуальные курсы USDT:*\n\n"
        f"💰 Rapira (USDT/RUB)\n• Покупка: `{rapira_bid}`\n• Продажа: `{rapira_ask}`\n\n"
        f"💰 ABCEX (USDT/RUB)\n• Покупка: `{abcex_bid}`\n• Продажа: `{abcex_ask}`\n\n"
        f"💰 Grinex (USDT/A7A5)\n• Покупка: `{grinex_bid}` A7A5\n• Продажа: `{grinex_ask}` A7A5\n\n"
        f"⏱ Обновление каждые {CACHE_TTL // 60} минут"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)

# --------------------------
# Команда помощь
# --------------------------
@dp.message(Command("help"))
async def help_command(message: types.Message):
    text = (
        "📌 Инструкции бота:\n"
        "1. /курс — показать текущие курсы Rapira, ABCEX, Grinex\n"
    )
    await message.answer(text, reply_markup=keyboard)

# --------------------------
# Запуск бота
# --------------------------
async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())