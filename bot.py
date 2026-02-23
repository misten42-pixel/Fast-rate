import os
import asyncio
import logging
import requests

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
TIMEOUT = 10

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json"
}


# ================= SAFE REQUEST =================
def safe_get(url):
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)

    if r.status_code != 200:
        logging.warning(f"{url} returned {r.status_code}")
        return None

    if "application/json" not in r.headers.get("Content-Type", ""):
        logging.warning(f"{url} did not return JSON")
        return None

    return r.json()


# ================= GRINEX =================
def fetch_grinex():
    try:
        data = safe_get("https://grinex.io/rates?offset=0")
        if not data:
            return None

        pair = data.get("usdta7a5")
        if not pair:
            return None

        return {
            "buy_price": float(pair.get("sell")),
            "buy_volume": None,
            "sell_price": float(pair.get("buy")),
            "sell_volume": None,
        }

    except Exception as e:
        logging.warning(f"Grinex error: {e}")
        return None


# ================= RAPIRA =================
def fetch_rapira():
    try:
        data = safe_get(
            "https://api.rapira.net/market/exchange-plate-mini?symbol=USDT/RUB"
        )
        if not data:
            return None

        # разные возможные структуры
        asks = data.get("ask") or data.get("asks")
        bids = data.get("bid") or data.get("bids")

        if not asks and "data" in data:
            asks = data["data"].get("ask") or data["data"].get("asks")
            bids = data["data"].get("bid") or data["data"].get("bids")

        if not asks or not bids:
            return None

        return {
            "buy_price": float(asks[0][0]),
            "buy_volume": float(asks[0][1]),
            "sell_price": float(bids[0][0]),
            "sell_volume": float(bids[0][1]),
        }

    except Exception as e:
        logging.warning(f"Rapira error: {e}")
        return None


# ================= ABCEX =================
def fetch_abcex():
    try:
        data = safe_get(
            "https://gateway.abcex.io/api/v2/exchange/public/orderbook/depth?pairCode=USDTRUB"
        )
        if not data:
            return None

        asks = data.get("ask") or data.get("asks")
        bids = data.get("bid") or data.get("bids")

        if not asks and "data" in data:
            asks = data["data"].get("ask") or data["data"].get("asks")
            bids = data["data"].get("bid") or data["data"].get("bids")

        if not asks or not bids:
            return None

        return {
            "buy_price": float(asks[0][0]),
            "buy_volume": float(asks[0][1]),
            "sell_price": float(bids[0][0]),
            "sell_volume": float(bids[0][1]),
        }

    except Exception as e:
        logging.warning(f"ABCEX error: {e}")
        return None


# ================= FORMAT =================
def format_exchange(name, data):
    if not data:
        return f"{name}: — / —\n"

    return (
        f"{name}\n"
        f"  Покупка: {data['buy_price']:.2f} ({data['buy_volume']:.2f} USDT)\n"
        f"  Продажа: {data['sell_price']:.2f} ({data['sell_volume']:.2f} USDT)\n\n"
    )


# ================= KEYBOARD =================
def keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📈 Курс", callback_data="rates")]]
    )


# ================= BOT =================
async def main():
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

    @dp.message(F.text.in_({"/start", "start"}))
    async def start(msg: Message):
        await msg.answer("Нажми «Курс»", reply_markup=keyboard())

    @dp.callback_query(F.data == "rates")
    async def rates(cb: CallbackQuery):
        await cb.answer("Обновляю...")

        loop = asyncio.get_running_loop()

        grinex = await loop.run_in_executor(None, fetch_grinex)
        rapira = await loop.run_in_executor(None, fetch_rapira)
        abcex = await loop.run_in_executor(None, fetch_abcex)

        text = (
            "📊 USDT/RUB — топ стакана\n\n"
            + format_exchange("🟩 Grinex", grinex)
            + format_exchange("🟥 Rapira", rapira)
            + format_exchange("🟨 ABCEX", abcex)
        )

        await cb.message.answer(text, reply_markup=keyboard())

    await dp.start_polling(bot, drop_pending_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
