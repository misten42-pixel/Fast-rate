import asyncio
import logging
import os
import aiohttp
import json
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)


# ================= RAPIRA DIAGNOSTIC =================
async def get_rapira(session):
    url = "https://api.rapira.net/market/exchange-plate-mini?symbol=USDT/RUB"
    try:
        async with session.get(url, timeout=10) as resp:
            logging.info(f"RAPIRA STATUS: {resp.status}")
            text = await resp.text()
            logging.info(f"RAPIRA RAW RESPONSE:\n{text}")

        return "🔵 Rapira: смотри логи Railway"

    except Exception as e:
        logging.warning(f"Rapira error: {e}")
        return "🔵 Rapira: ошибка"


# ================= ABCEX DIAGNOSTIC =================
async def get_abcex(session):
    url = "https://gateway.abcex.io/api/v2/exchange/public/trade/spot/rates"
    try:
        async with session.get(url, timeout=10) as resp:
            logging.info(f"ABCEX STATUS: {resp.status}")
            text = await resp.text()
            logging.info(f"ABCEX RAW RESPONSE:\n{text}")

        return "🟣 ABCEX: смотри логи Railway"

    except Exception as e:
        logging.warning(f"ABCEX error: {e}")
        return "🟣 ABCEX: ошибка"


# ================= GRINEX (рабочий JSON) =================
async def get_grinex(session):
    url = "https://grinex.io/rates?offset=0"
    try:
        async with session.get(url, timeout=10) as resp:
            data = await resp.json()

        pair = data.get("usdta7a5")

        if not pair:
            return "🟢 Grinex: пара не найдена"

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
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не установлен")

    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

    @dp.message(Command("start"))
    async def start_handler(message: types.Message):
        await message.answer("Диагностический режим.\nКоманда: /rate")

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
