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

    except Exception:
        return "🟦 Rapira: ошибка"


# ================= ABCEX =================
async def get_abcex(session):
    depth_url = "https://gateway.abcex.io/api/v2/exchange/public/orderbook/depth?instrumentCode=USDTRUB"

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
    except Exception:
        pass

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

    except Exception:
        return "🟠 Grinex: ошибка"


# ================= BESTCHANGE API =================
async def get_bestchange_usdt_aed(session):
    try:
        url = "https://bestchange.app/api/v1/exchange"

        params = {
            "from": "tether-trc20",
            "to": "cash-aed",
            "limit": 3
        }

        async with session.get(url, params=params) as response:
            if response.status != 200:
                return "💱 USDT/AED: нет данных"

            data = await response.json()

        if not data.get("data"):
            return "💱 USDT/AED: нет данных"

        text = "💱 USDT/AED (Top 3)\n\n"

        for i, item in enumerate(data["data"], 1):
            rate = float(item["rate"])
            reserve = item.get("reserve", "—")
            exchanger = item.get("name", "Unknown")

            text += (
                f"{i}) {exchanger}\n"
                f"Курс: {rate:.4f}\n"
                f"Резерв: {reserve}\n\n"
            )

        return text.strip()

    except Exception as e:
        logging.warning(f"BestChange error: {e}")
        return "💱 USDT/AED: ошибка"


# ================= TELEGRAM =================
async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не установлен")

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
            "Бот запущен.\nВыберите направление:",
            reply_markup=keyboard
        )

    # ===== RUB кнопка =====
    @dp.message(lambda message: message.text == "📊 Rate USDT/₽")
    async def rub_handler(message: types.Message):

        timeout = aiohttp.ClientTimeout(total=8)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            results = await asyncio.gather(
                get_rapira(session),
                get_abcex(session),
                get_grinex(session),
                return_exceptions=True
            )

        await message.answer("\n\n".join(results))


    # ===== AED кнопка =====
    @dp.message(lambda message: message.text == "💱 USDT/AED")
    async def aed_handler(message: types.Message):

        timeout = aiohttp.ClientTimeout(total=8)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            result = await get_bestchange_usdt_aed(session)

        await message.answer(result)


    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
