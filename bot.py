import asyncio
import logging
import os
import aiohttp
import xml.etree.ElementTree as ET
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)


# ================= RAPIRA (JSON) =================
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

                if bid and ask:
                    return f"🔵 Rapira\nBid: {bid:.2f}\nAsk: {ask:.2f}"

        return "🔵 Rapira: пара не найдена"

    except Exception as e:
        logging.warning(f"Rapira error: {e}")
        return "🔵 Rapira: ошибка"


# ================= ABCEX (XML) =================
async def get_abcex(session):
    url = "https://gateway.abcex.io/api/v2/exchange/public/trade/spot/rates"

    try:
        async with session.get(url, timeout=10) as response:
            text = await response.text()

        if not text or not text.strip():
            return "🟣 ABCEX: нет данных"

        root = ET.fromstring(text)

        bid = None
        ask = None

        for item in root.findall(".//item"):
            from_currency = item.find("from")
            to_currency = item.find("to")
            out_value = item.find("out")

            if (
                from_currency is not None
                and to_currency is not None
                and out_value is not None
            ):
                if from_currency.text == "USDT" and to_currency.text == "RUB":
                    ask = float(out_value.text)

                if from_currency.text == "RUB" and to_currency.text == "USDT":
                    bid = round(1 / float(out_value.text), 2)

        if bid is not None and ask is not None:
            return f"🟣 ABCEX\nBid: {bid:.2f}\nAsk: {ask:.2f}"

        return "🟣 ABCEX: нет данных"

    except Exception as e:
        logging.warning(f"ABCEX error: {e}")
        return "🟣 ABCEX: ошибка"


# ================= GRINEX (JSON) =================
async def get_grinex(session):
    url = "https://grinex.io/rates?offset=0"

    try:
        async with session.get(url, timeout=10) as response:
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
