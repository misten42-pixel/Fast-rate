import asyncio
import logging
import os
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)


# ================= RAPIRA =================
async def get_rapira(session):
    url = "https://api.rapira.net/open/market/rates"

    try:
        async with session.get(url, timeout=10) as response:
            if response.status != 200:
                return "🔵 Rapira: нет данных"

            data = await response.json()

        markets = data.get("data", [])

        for market in markets:
            if market.get("symbol") == "USDT/RUB":
                bid = float(market.get("bidPrice", 0))
                ask = float(market.get("askPrice", 0))

                return f"🔵 Rapira\nBid: {bid:.2f}\nAsk: {ask:.2f}"

        return "🔵 Rapira: пара не найдена"

    except Exception as e:
        logging.warning(f"Rapira error: {e}")
        return "🔵 Rapira: ошибка"


# ================= ABCEX (REAL ORDERBOOK) =================
async def get_abcex(session):
    url = "https://gateway.abcex.io/api/v2/exchange/public/orderbook/depth?instrumentCode=USDTRUB"

    try:
        async with session.get(url, timeout=10) as response:
            if response.status != 200:
                return "🟣 ABCEX: нет данных"

            data = await response.json()

        # Иногда структура вложена в data
        if "data" in data:
            data = data["data"]

        bids = data.get("bids", [])
        asks = data.get("asks", [])

        if not bids or not asks:
            return "🟣 ABCEX: нет данных"

        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])

        return f"🟣 ABCEX\nBid: {best_bid:.2f}\nAsk: {best_ask:.2f}"

    except Exception as e:
        logging.warning(f"ABCEX error: {e}")
        return "🟣 ABCEX: ошибка"


# ================= GRINEX =================
async def get_grinex(session):
    url = "https://grinex.io/rates?offset=0"

    try:
        async with session.get(url, timeout=10) as response:
            if response.status != 200:
                return "🟢 Grinex: нет данных"

            data = await response.json()

        pair = data.get("usdta7a5")

        if not pair:
            return "🟢 Grinex: нет данных"

        bid = float(pair.get("buy", 0))
        ask = float(pair.get("sell", 0))

        return f"🟢 Grinex\nBid: {bid:.2f}\nAsk: {ask:.2f}"

    except Exception as e:
        logging.warning(f"Grinex error: {e}")
        return "🟢 Grinex: ошибка"


# ================= TELEGRAM =================
async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не установлен")

    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

    @dp.message(Command("start"))
    async def start_handler(message: types.Message):
        await message.answer("Бот запущен.\nКоманда: /rate")

    @dp.message(Command("rate"))
    async def rate_handler(message: types.Message):
        async with aiohttp.ClientSession() as session:
            results = await asyncio.gather(
                get_rapira(session),
                get_abcex(session),
                get_grinex(session)
            )

        await message.answer("\n\n".join(results))

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
