import os
import asyncio
import logging
import requests

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
PROXY_URL = os.getenv("PROXY_URL")
TIMEOUT = 10

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

PROXIES = {
    "http": PROXY_URL,
    "https": PROXY_URL,
} if PROXY_URL else None


# ================= SAFE REQUEST =================
def safe_get(url):
    try:
        r = requests.get(
            url,
            headers=HEADERS,
            proxies=PROXIES,
            timeout=TIMEOUT,
        )

        print("URL:", url)
        print("STATUS:", r.status_code)

        if r.status_code != 200:
            print(r.text[:200])
            return None

        return r.json()

    except Exception as e:
        print("Request error:", e)
        return None


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

    buy_price = f"{data['buy_price']:.2f}"
    sell_price = f"{data['sell_price']:.2f}"

    buy_vol = f"{data['buy_volume']:.2f}" if data["buy_volume"] else "—"
    sell_vol = f"{data['sell_volume']:.2f}" if data["sell_volume"] else "—"

    return (
        f"{name}\n"
        f"  Покупка: {buy_price} ({buy_vol} USDT)\n"
        f"  Продажа: {sell_price} ({sell_vol} USDT)\n\n"
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
