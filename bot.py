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
TIMEOUT = 15

@dataclass
class Rate:
    buy: Optional[float]
    sell: Optional[float]

def fmt(x):
    return "—" if x is None else f"{x:.2f}"

# --------------------------------------------------
# Универсальный HTML-парсер (ищет первые 2 цены 70-100)
# --------------------------------------------------
def extract_prices_from_html(html: str) -> Rate:
    prices = re.findall(r"\d{2,3}\.\d{2}", html)

    filtered = []
    for p in prices:
        try:
            value = float(p)
            if 60 < value < 120:  # разумный диапазон для USDT/RUB
                filtered.append(value)
        except:
            pass

    if len(filtered) >= 2:
        buy = max(filtered[0], filtered[1])
        sell = min(filtered[0], filtered[1])
        return Rate(buy, sell)

    return Rate(None, None)

# --------------------------------------------------
# GRINEX
# --------------------------------------------------
def fetch_grinex():
    try:
        r = requests.get(
            "https://grinex.io/trading/usdta7a5",
            timeout=TIMEOUT,
            headers={"User-Agent": UA}
        )
        return extract_prices_from_html(r.text)
    except Exception as e:
        logging.error(f"Grinex error: {e}")
        return Rate(None, None)

# --------------------------------------------------
# RAPIRA
# --------------------------------------------------
def fetch_rapira():
    try:
        r = requests.get(
            "https://rapira.net/exchange/USDT_RUB",
            timeout=TIMEOUT,
            headers={"User-Agent": UA}
        )
        return extract_prices_from_html(r.text)
    except Exception as e:
        logging.error(f"Rapira error: {e}")
        return Rate(None, None)

# --------------------------------------------------
# ABCEX (mobile версия)
# --------------------------------------------------
def fetch_abcex():
    try:
        r = requests.get(
            "https://m.abcex.io/spot/USDTRUB/view/open-orders",
            timeout=TIMEOUT,
            headers={"User-Agent": UA}
        )
        return extract_prices_from_html(r.text)
    except Exception as e:
        logging.error(f"ABCEX error: {e}")
        return Rate(None, None)

# --------------------------------------------------
# BOT
# --------------------------------------------------
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
