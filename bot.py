import os
import asyncio
import aiohttp
from bs4 import BeautifulSoup

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command

BOT_TOKEN = os.getenv("BOT_TOKEN")
PROXY_URL = os.getenv("PROXY_URL")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не установлен")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==============================
# КНОПКИ
# ==============================

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Rate USDT/₽")],
        [KeyboardButton(text="💱 USDT/AED")]
    ],
    resize_keyboard=True
)

# ==============================
# START
# ==============================

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "Бот запущен.\nНажмите кнопку ниже:",
        reply_markup=keyboard
    )

# ==============================
# RAPIRA (БЕЗ PROXY)
# ==============================

async def get_rapira(session):
    try:
        url = "https://api.rapira.net/market/exchange-plate-mini?symbol=USDT/RUB"
        async with session.get(url, timeout=10) as response:
            data = await response.json()

        sell = float(data["data"]["asks"][0][0])
        buy = float(data["data"]["bids"][0][0])

        return f"🟦 Rapira\n🔴 Продажа: {sell}\n🟢 Покупка: {buy}\n"

    except:
        return "🟦 Rapira: нет данных\n"

# ==============================
# ABCEX (БЕЗ PROXY)
# ==============================

async def get_abcex(session):
    try:
        url = "https://gateway.abcex.io/api/v2/exchange/public/trade/spot/rates"
        async with session.get(url, timeout=10) as response:
            data = await response.json()

        pair = next((x for x in data if x["symbol"] == "USDTRUB"), None)

        if not pair:
            return "🔵 ABCEX: нет данных\n"

        sell = float(pair["sell"])
        buy = float(pair["buy"])

        return f"🔵 ABCEX\n🔴 Продажа: {sell}\n🟢 Покупка: {buy}\n"

    except:
        return "🔵 ABCEX: временно недоступен\n"

# ==============================
# GRINEX (БЕЗ PROXY)
# ==============================

async def get_grinex(session):
    try:
        url = "https://grinex.io/api/spot/depth?symbol=usdta7a5"
        async with session.get(url, timeout=10) as response:
            data = await response.json()

        sell = float(data["asks"][0][0])
        buy = float(data["bids"][0][0])

        return f"🟠 Grinex\n🔴 Продажа: {sell}\n🟢 Покупка: {buy}\n"

    except:
        return "🟠 Grinex: нет данных\n"

# ==============================
# USDT/RUB
# ==============================

@dp.message(lambda message: message.text == "📊 Rate USDT/₽")
async def rub_handler(message: types.Message):

    async with aiohttp.ClientSession() as session:

        rapira = await get_rapira(session)
        abcex = await get_abcex(session)
        grinex = await get_grinex(session)

        result = f"{rapira}\n{abcex}\n{grinex}"

        await message.answer(result)

# ==============================
# BESTCHANGE (ЧЕРЕЗ PROXY)
# ==============================

async def get_bestchange(session):

    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        url = "https://www.bestchange.com/tether-trc20-to-cash-aed-in-dubai.html"

        async with session.get(
            url,
            headers=headers,
            proxy=PROXY_URL,
            timeout=20
        ) as response:

            html = await response.text()

        soup = BeautifulSoup(html, "html.parser")

        rows = soup.select("#content_table tr")

        results = []

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 5:
                continue

            name = cols[1].get_text(strip=True)
            rate = cols[3].get_text(strip=True)
            reserve = cols[4].get_text(strip=True)

            if name and rate and reserve:
                results.append(
                    f"{name} — {rate} AED — резерв: {reserve}"
                )

        if not results:
            return "💱 USDT/AED: нет данных"

        message = "🔴 Продажа USDT (Dubai)\n\n"
        message += "\n".join(results[:3])

        return message

    except Exception as e:
        return f"💱 USDT/AED ошибка: {str(e)}"

# ==============================
# USDT/AED
# ==============================

@dp.message(lambda message: message.text == "💱 USDT/AED")
async def aed_handler(message: types.Message):

    async with aiohttp.ClientSession() as session:
        result = await get_bestchange(session)
        await message.answer(result)

# ==============================
# RUN
# ==============================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
