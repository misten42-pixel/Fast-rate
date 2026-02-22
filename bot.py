import os
import re
import time
import json
import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Tuple

import requests
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from telethon import TelegramClient
from telethon.sessions import StringSession

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# ---- Mosca (Telethon) ----
MOSCA_USERNAME = "@Mosca67_bot"  # из твоей ссылки https://t.me/Mosca67_bot
TG_API_ID = os.getenv("TG_API_ID", "").strip()
TG_API_HASH = os.getenv("TG_API_HASH", "").strip()
TG_STRING_SESSION = os.getenv("TG_STRING_SESSION", "").strip()

# ---- API endpoints (укажи в Railway ENV) ----
# Готовые дефолты (можно оставить, но если у биржи другой хост API — просто поменяешь ENV)
GRINEX_ORDERBOOK_URL = os.getenv(
    "GRINEX_ORDERBOOK_URL",
    "https://api.grinex.io/api/v2/order_book?market=usdta7a5"
)

ABCEX_ORDERBOOK_URL = os.getenv(
    "ABCEX_ORDERBOOK_URL",
    "https://api.abcex.io/api/v1/depth?symbol=USDTRUB&limit=5"
)

RAPIRA_ORDERBOOK_URL = os.getenv(
    "RAPIRA_ORDERBOOK_URL",
    "https://rapira.net/api/v2/order_book?market=usdt_rub"
)

HTTP_TIMEOUT = 12
UA = "Mozilla/5.0 (compatible; RatesBot/2.0; +https://t.me/)"

@dataclass
class Rate:
    buy: Optional[float]   # RUB за 1 USDT (покупка USDT) -> best ask
    sell: Optional[float]  # RUB за 1 USDT (продажа USDT) -> best bid
    ts: int

def fmt(x: Optional[float]) -> str:
    return "—" if x is None else f"{x:.2f}"

def to_float(s: str) -> float:
    return float(str(s).replace(" ", "").replace(",", "."))

def http_get_json(url: str) -> dict:
    r = requests.get(url, timeout=HTTP_TIMEOUT, headers={"User-Agent": UA, "Accept": "application/json"})
    r.raise_for_status()
    # иногда возвращают json как text
    return r.json()

def parse_orderbook_generic(data: dict) -> Tuple[Optional[float], Optional[float]]:
    """
    Пробует распарсить best_ask / best_bid из популярных форматов:
    1) {"asks":[["77.42","100"],...], "bids":[["77.41","50"],...]}
    2) {"data":{"asks":[...],"bids":[...]}}
    3) {"a":[[".."]], "b":[[".."]]} (некоторые биржи)
    Возвращаем: (buy, sell) = (best_ask, best_bid)
    """
    # распакуем возможный "data"
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
        data = data["data"]

    asks = data.get("asks") or data.get("a")
    bids = data.get("bids") or data.get("b")

    def first_price(side):
        if not side:
            return None
        p = side[0][0] if isinstance(side[0], (list, tuple)) else side[0].get("price")
        return to_float(p)

    best_ask = first_price(asks)
    best_bid = first_price(bids)
    return best_ask, best_bid

def fetch_grinex() -> Rate:
    ts = int(time.time())
    try:
        data = http_get_json(GRINEX_ORDERBOOK_URL)
        best_ask, best_bid = parse_orderbook_generic(data)
        return Rate(buy=best_ask, sell=best_bid, ts=ts)
    except Exception as e:
        logging.warning(f"Grinex API failed: {e}")
        return Rate(None, None, ts)

def fetch_abcex() -> Rate:
    ts = int(time.time())
    try:
        data = http_get_json(ABCEX_ORDERBOOK_URL)
        best_ask, best_bid = parse_orderbook_generic(data)
        return Rate(buy=best_ask, sell=best_bid, ts=ts)
    except Exception as e:
        logging.warning(f"ABCEX API failed: {e}")
        return Rate(None, None, ts)

def fetch_rapira() -> Rate:
    ts = int(time.time())
    try:
        data = http_get_json(RAPIRA_ORDERBOOK_URL)
        best_ask, best_bid = parse_orderbook_generic(data)
        return Rate(buy=best_ask, sell=best_bid, ts=ts)
    except Exception as e:
        logging.warning(f"Rapira API failed: {e}")
        return Rate(None, None, ts)

async def fetch_mosca(tg_client: TelegramClient) -> Rate:
    ts = int(time.time())
    try:
        await tg_client.send_message(MOSCA_USERNAME, "Курсы")
        await asyncio.sleep(2.0)
        msgs = await tg_client.get_messages(MOSCA_USERNAME, limit=10)

        text = ""
        for m in msgs:
            if m.message and ("Купить 1 USDT" in m.message) and ("Продать 1 USDT" in m.message):
                text = m.message
                break

        if not text:
            text = msgs[0].message if msgs and msgs[0].message else ""

        m_buy = re.search(r"Купить\s*1\s*USDT\s*=\s*(\d+[.,]\d+)\s*RUB", text, re.I)
        m_sell = re.search(r"Продать\s*1\s*USDT\s*=\s*(\d+[.,]\d+)\s*RUB", text, re.I)

        buy = to_float(m_buy.group(1)) if m_buy else None
        sell = to_float(m_sell.group(1)) if m_sell else None
        return Rate(buy=buy, sell=sell, ts=ts)
    except Exception as e:
        logging.warning(f"Mosca (Telethon) failed: {e}")
        return Rate(None, None, ts)

def kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📈 Курс", callback_data="rates")]])

def build_text(mosca: Rate, abcex: Rate, grinex: Rate, rapira: Rate) -> str:
    return (
        "📊 *USDT/RUB — покупка / продажа*\n\n"
        f"🟦 *Mosca*: {fmt(mosca.buy)} / {fmt(mosca.sell)}\n"
        f"🟨 *ABCEX*: {fmt(abcex.buy)} / {fmt(abcex.sell)}\n"
        f"🟩 *Grinex*: {fmt(grinex.buy)} / {fmt(grinex.sell)}\n"
        f"🟥 *Rapira*: {fmt(rapira.buy)} / {fmt(rapira.sell)}\n\n"
        "_Если где-то «—», значит не настроен API URL или биржа блокирует запросы._"
    )

async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is empty")

    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

    tg_client: Optional[TelegramClient] = None
    if TG_API_ID and TG_API_HASH and TG_STRING_SESSION:
        tg_client = TelegramClient(StringSession(TG_STRING_SESSION), int(TG_API_ID), TG_API_HASH)
        await tg_client.start()
        logging.info("Telethon started: Mosca enabled.")
    else:
        logging.warning("Telethon not configured: Mosca will be '—'.")

    @dp.message(F.text.in_({"/start", "start", "Старт"}))
    async def start_handler(m: Message):
        await m.answer("Нажми кнопку «Курс», чтобы получить покупку/продажу USDT → RUB.", reply_markup=kb())

    @dp.callback_query(F.data == "rates")
    async def rates_handler(cb: CallbackQuery):
        await cb.answer("Обновляю…", show_alert=False)

        loop = asyncio.get_running_loop()
        abcex_task = loop.run_in_executor(None, fetch_abcex)
        grinex_task = loop.run_in_executor(None, fetch_grinex)
        rapira_task = loop.run_in_executor(None, fetch_rapira)

        if tg_client:
            mosca_task = asyncio.create_task(fetch_mosca(tg_client))
        else:
            mosca_task = None

        abcex = await abcex_task
        grinex = await grinex_task
        rapira = await rapira_task
        mosca = await mosca_task if mosca_task else Rate(None, None, int(time.time()))

        await cb.message.answer(build_text(mosca, abcex, grinex, rapira), parse_mode="Markdown", reply_markup=kb())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
