import asyncio
import logging
import os
import aiohttp
import xml.etree.ElementTree as ET

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)


# ================= RAPIRA =================
async def get_rapira(session):
    try:
        url = "https://api.rapira.net/open/market/rates"
        async with session.get(url) as response:
            if response.status != 200:
                return "🟦 Rapira: нет данных"

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


# ================= ABCEX (HYBRID STABLE) =================
async def get_abcex(session):
    depth_url = "https://gateway.abcex.io/api/v2/exchange/public/orderbook/depth?instrumentCode=USDTRUB"
    rates_url = "https://gateway.abcex.io/api/v2/exchange/public/trade/spot/rates"

    # ===== 1. Пытаемся стакан =====
    try:
        async with session.get(depth_url) as response:
            if response.status == 200:
                data = await response.json()
                orderbook = data.get("data", data)

                bids = orderbook.get("bids", [])
                asks = orderbook.get("asks", [])

                if bids and asks:
                    buy = float(bids[0][0])
                    sell = float(asks[0][0])

                    return (
                        "🔵 ABCEX\n\n"
                        f"🔴 Продажа: {sell:.2f}\n"
                        f"🟢 Покупка: {buy:.2f}"
                    )
    except Exception as e:
        logging.warning(f"ABCEX depth error: {e}")

    # ===== 2. Fallback на rates =====
    try:
        async with session.get(rates_url) as response:
            if response.status != 200:
                return "🔵 ABCEX: временно недоступен"

            text = await response.text()

        root = ET.fromstring(text)

        buy = None
        sell = None

        for item in root.findall(".//item"):
            from_currency = item.find("from")
            to_currency = item.find("to")
            out_value = item.find("out")

            if from_currency is not None and to_currency is not None:
                if from_currency.text == "USDT" and to_currency.text == "RUB":
                    sell = float(out_value.text)
                if from_currency.text == "RUB" and to_currency.text == "USDT":
                    buy = round(1 / float(out_value.text), 2)

        if buy and sell:
            return (
                "🔵 ABCEX (rates)\n\n"
                f"🔴 Продажа: {sell:.2f}\n"
                f"🟢 Покупка: {buy:.2f}"
            )

    except Exception as e:
        logging.warning(f"ABCEX rates error: {e}")

    return "🔵 ABCEX: временно недоступен"


# ================= GRINEX =================
async def get_grinex(session):
    try:
        url = "https://grinex.io/rates?offset=0"
        async with session.get(url) as response:
            if response.status != 200:
                return "🟠 Grinex: нет данных"

            data = await response.json()

        pair = data.get("usdta7a5")

        if pair:
            buy = float(pair.get("buy", 0))
            sell = float(pair.get("sell", 0))

            return (
                "🟠 Grinex\n\n"
                f"🔴 Продажа: {sell:.2f}\n"
                f"🟢 Покупка: {buy:.2f}"
            )

        return "🟠 Grinex: нет данных"

    except Exception as e:
        logging.warning(f"Grinex error: {e}")
        return "🟠 Grinex: ошибка"


# ================= TELEGRAM =================
async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не установлен")

    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📊 Rate USDT/₽")]],
        resize_keyboard=True
    )

    @dp.message(Command("start"))
    async def start_handler(message: types.Message):
        await message.answer(
            "Бот запущен.\nНажмите кнопку ниже:",
            reply_markup=keyboard
        )

    @dp.message(Command("rate"))
    @dp.message(lambda message: message.text == "📊 Rate USDT/₽")
    async def rate_handler(message: types.Message):

        timeout = aiohttp.ClientTimeout(total=8)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            tasks = [
                get_rapira(session),
                get_abcex(session),
                get_grinex(session)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

        formatted = []
        for r in results:
            if isinstance(r, Exception):
                formatted.append("⚠️ Ошибка получения данных")
            else:
                formatted.append(r)

        await message.answer("\n\n".join(formatted))

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
