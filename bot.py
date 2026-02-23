import asyncio
import logging
import os
import aiohttp
import xml.etree.ElementTree as ET
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)


# ================= RAPIRA =================
async def get_rapira(session):
    url = "https://api.rapira.net/market/exchange-plate-mini?symbol=USDT/RUB"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    try:
        async with session.get(url, headers=headers, timeout=10) as resp:
            text = await resp.text()

            if not text.strip():
                return "🔵 Rapira: пустой ответ (возможно блокировка IP)"

            return "🔵 Rapira: получен ответ (смотри логи)"

    except Exception as e:
        logging.warning(f"Rapira error: {e}")
        return "🔵 Rapira: ошибка"


# ================= ABCEX (XML) =================
async def get_abcex(session):
    url = "https://gateway.abcex.io/api/v2/exchange/public/trade/spot/rates"

    try:
        async with session.get(url, timeout=10) as resp:
            text = await resp.text()

        root = ET.fromstring(text)

        buy = None
        sell = None

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
                    sell = float(out_value.text)

                if from_currency.text == "RUB" and to_currency.text == "USDT":
                    buy = 1 / float(out_value.text)

        if buy and sell:
            return (
                f"🟣 ABCEX\n"
                f"Bid: {buy:.2f}\n"
                f"Ask: {sell:.2f}"
            )

        return "🟣 ABCEX: пара не найдена"

    except Exception as e:
        logging.warning(f"ABCEX error: {e}")
        return "🟣 ABCEX: ошибка"


# ================= GRINEX =================
async def get_grinex(session):
    url = "https://grinex.io/rates?offset=0"

    try:
        async with session.get(url, timeout=10) as resp:
            data = await resp.json()

        pair = data.get("usdta7a5")

        buy = float(pair.get("buy", 0))
        sell = float(pair.get("sell", 0))

        return (
            f"🟢 Grinex\n"
            f"Bid: {buy:.2f}\n"
            f"Ask: {sell:.2f}"
        )

    except Exception as e:
        logging.warning(f"Grinex error: {e}")
        return "🟢 Grinex: ошибка"


# ================= TELEGRAM =================
async def main():
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

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
