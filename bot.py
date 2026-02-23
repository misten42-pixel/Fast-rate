import os
import asyncio
import logging
import requests

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
UA = "Mozilla/5.0"
TIMEOUT = 10


# ---------------- GRINEX ----------------
def fetch_grinex():
    try:
        url = "https://grinex.io/rates?offset=0"
        r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": UA})
        data = r.json()

        pair = data.get("usdta7a5")
        if pair:
            buy_price = float(pair["sell"])  # ты покупаешь USDT
            sell_price = float(pair["buy"])  # ты продаёшь USDT

            return {
                "buy_price": buy_price,
                "buy_volume": None,
                "sell_price": sell_price,
                "sell_volume": None,
            }

        return None
    except Exception as e:
        logging.warning(f"Grinex error: {e}")
        return None


# ---------------- RAPIRA ----------------
def fetch_rapira():
    try:
        url = "https://api.rapira.net/market/exchange-plate-mini?symbol=USDT/RUB"
        r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": UA})
        data = r.json()

        asks = data.get("data", {}).get("asks", [])
        bids = data.get("data", {}).get("bids", [])

        if asks and bids:
            return {
                "buy_price": float(asks[0][0]),
                "buy_volume": float(asks[0][1]),
                "sell_price": float(bids[0][0]),
                "sell_volume": float(bids[0][1]),
            }

        return None
    except Exception as e:
        logging.warning(f"Rapira error: {e}")
        return None


# ---------------- ABCEX ----------------
def fetch_abcex():
    try:
        url = "https://gateway.abcex.io/api/v2/exchange/public/orderbook/depth?pairCode=USDTRUB"
        r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": UA})
        data = r.json()

        asks = data.get("asks", [])
        bids = data.get("bids", [])

        if asks and bids:
            return {
                "buy_price": float(asks[0][0]),
                "buy_volume": float(asks[0][1]),
                "sell_price": float(bids[0][0]),
                "sell_volume": float(bids[0][1]),
            }

        return None
    except Exception as e:
        logging.warning(f"ABCEX error: {e}")
        return None


# ---------------- FORMAT ----------------
def format_exchange(name, data):
    if not data:
        return f"{name}: — / —"

    buy = f"{data['buy_price']:.2f}"
    sell = f"{data['sell_price']:.2f}"

    buy_vol = f"{data['buy_volume']:.2f}" if data["buy_volume"] else "—"
    sell_vol = f"{data['sell_volume']:.2f}" if data["sell_volume"] else "—"

    return (
        f"{name}\n"
        f"  Покупка: {buy} ({buy_vol} USDT)\n"
        f"  Продажа: {sell} ({sell_vol} USDT)\n"
    )


# ---------------- BOT ----------------
def keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📈 Курс", callback_data="rates")]]
    )


async def main():
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

    @dp.message(F.text.in_({"/start", "start"}))
    async def start(msg: Message):
        await msg.answer("Нажми «Курс»", reply_markup=keyboard())

    @dp.callback_query(F.data == "rates")
    async def rates(cb: CallbackQuery):
        await cb.answer("Обновляю…")

        loop = asyncio.get_running_loop()

        grinex = await loop.run_in_executor(None, fetch_grinex)
        rapira = await loop.run_in_executor(None, fetch_rapira)
        abcex = await loop.run_in_executor(None, fetch_abcex)

        text = (
            "📊 USDT/RUB — топ стакана\n\n"
            + format_exchange("🟩 Grinex", grinex) + "\n"
            + format_exchange("🟥 Rapira", rapira) + "\n"
            + format_exchange("🟨 ABCEX", abcex)
        )

        await cb.message.answer(text, reply_markup=keyboard())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
