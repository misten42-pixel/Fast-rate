import os
import re
import asyncio
import logging
import requests
from dataclasses import dataclass
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")

UA = "Mozilla/5.0"
TIMEOUT = 10

@dataclass
class Rate:
    buy: Optional[float]
    sell: Optional[float]

def fmt(x):
    return "—" if x is None else f"{x:.2f}"

# ---------------- GRINEX ----------------
def fetch_grinex():
    try:
        r = requests.get(
            "https://exchange-api.grinex.io/public/orderbook/usdta7a5",
            timeout=TIMEOUT,
            headers={"User-Agent": UA}
        )
        data = r.json()
        return Rate(
            float(data["asks"][0][0]),
            float(data["bids"][0][0])
        )
    except Exception as e:
        logging.warning(f"Grinex error: {e}")
        return Rate(None, None)

# ---------------- RAPIRA ----------------
def fetch_rapira():
    try:
        r = requests.get(
            "https://rapira.net/api/public/ticker",
            timeout=TIMEOUT,
            headers={"User-Agent": UA}
        )
        data = r.json()

        for item in data:
            if item.get("symbol") == "USDT_RUB":
                return Rate(float(item["ask"]), float(item["bid"]))

        return Rate(None, None)
    except Exception as e:
        logging.warning(f"Rapira error: {e}")
        return Rate(None, None)

# ---------------- ABCEX ----------------
def fetch_abcex():
    try:
        r = requests.get(
            "https://m.abcex.io/spot/USDTRUB/view/open-orders",
            timeout=TIMEOUT,
            headers={"User-Agent": UA}
        )
        html = r.text
        prices = re.findall(r"\d{2,3}\.\d{2}", html)
        if len(prices) >= 2:
            return Rate(float(prices[0]), float(prices[1]))
        return Rate(None, None)
    except Exception as e:
        logging.warning(f"ABCEX error: {e}")
        return Rate(None, None)

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
            "📊 USDT/RUB — покупка / продажа\n\n"
            f"🟩 Grinex: {fmt(grinex.buy)} / {fmt(grinex.sell)}\n"
            f"🟥 Rapira: {fmt(rapira.buy)} / {fmt(rapira.sell)}\n"
            f"🟨 ABCEX: {fmt(abcex.buy)} / {fmt(abcex.sell)}"
        )

        await cb.message.answer(text, reply_markup=keyboard())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
