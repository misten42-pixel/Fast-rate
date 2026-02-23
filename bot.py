import asyncio
import logging
import os
import aiohttp
import xml.etree.ElementTree as ET

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
PROXY_URL = os.getenv("PROXY_URL")

logging.basicConfig(level=logging.INFO)


# ================= RAPIRA =================
async def get_rapira(session):
    url = "https://api.rapira.net/open/market/rates"

    try:
        async with session.get(url, timeout=10) as response:
            data = await response.json()

        for market in data.get("data", []):
            if market.get("symbol") == "USDT/RUB":
                buy = float(market.get("bidPrice", 0))
                sell = float(market.get("askPrice", 0))

                return (
                    "🟦 Rapira\n\n"
                    f"🔴 Продажа: {sell:.2f}\n"
                    f"🟢 Покупка: {buy:.2f}"
                )

        return "🟦 Rapira: нет данных"

    except Exception as e:
        logging.warning(f"Rapira error: {e}")
        return "🟦 Rapira: ошибка"


# ================= ABCEX =================
async def get_abcex(session):
    url = "https://gateway.abcex.io/api/v2/exchange/public/orderbook/depth?instrumentCode=USDTRUB"

    try:
        async with session.get(url, timeout=10) as response:
            data = await response.json()

        bids = data["data"]["bids"]
        asks = data["data"]["asks"]

        buy = float(bids[0][0])
        sell = float(asks[0][0])

        return (
            "🔵 ABCEX\n\n"
            f"🔴 Продажа: {sell:.2f}\n"
            f"🟢 Покупка: {buy:.2f}"
        )

    except Exception as e:
        logging.warning(f"ABCEX error: {e}")
        return "🔵 ABCEX: временно недоступен"


# ================= GRINEX =================
async def get_grinex(session):
    url = "https://grinex.io/rates?offset=0"

    try:
        async with session.get(url, timeout=10) as response:
            data = await response.json()

        pair = data.get("usdta7a5")

        buy = float(pair.get("buy", 0))
        sell = float(pair.get("sell", 0))

        return (
            "🟠 Grinex\n\n"
            f"🔴 Продажа: {sell:.2f}\n"
            f"🟢 Покупка: {buy:.2f}"
        )

    except Exception as e:
        logging.warning(f"Grinex error: {e}")
        return "🟠 Grinex: ошибка"


# ================= BESTCHANGE (через proxy) =================
async def get_bestchange(session):
    try:
        proxy = PROXY_URL

        url = "https://mirror1.bestchange.app/v2/"

        async with session.get(url, proxy=proxy, timeout=10) as response:
            if response.status != 200:
                return "💱 USDT/AED: нет данных"

        return "💱 USDT/AED: соединение есть (API подключено)"

    except Exception as e:
        logging.warning(f"BestChange error: {e}")
        return "💱 USDT/AED: ошибка подключения"


# ================= TELEGRAM =================
async def main():
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Rate USDT/₽")],
            [KeyboardButton(text="💱 USDT/AED")]
        ],
        resize_keyboard=True
    )

    @dp.message(Command("start"))
    async def start_handler(message: types.Message):
        await message.answer(
            "Бот запущен.\nНажмите кнопку ниже:",
            reply_markup=keyboard
        )

    @dp.message(lambda message: message.text == "📊 Rate USDT/₽")
    async def rate_handler(message: types.Message):
        async with aiohttp.ClientSession() as session:
            results = await asyncio.gather(
                get_rapira(session),
                get_abcex(session),
                get_grinex(session)
            )

        await message.answer("\n\n".join(results))

    @dp.message(lambda message: message.text == "💱 USDT/AED")
    async def aed_handler(message: types.Message):
        async with aiohttp.ClientSession() as session:
            result = await get_bestchange(session)

        await message.answer(result)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
