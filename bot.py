import os
import re
import time
import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Tuple, Dict

import requests

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from telethon import TelegramClient
from telethon.sessions import StringSession


logging.basicConfig(level=logging.INFO)

# --- URLs (как ты дал) ---
MOSCA_BOT = "https://t.me/Mosca67_bot"
GRINEX_URL = "https://grinex.io/trading/usdta7a5"
ABCEX_URL = "https://m.abcex.io/spot/USDTRUB/view/open-orders"

# Rapira: если у тебя есть точная ссылка на страницу с buy/sell как в боте — скажи, заменю.
RAPIRA_URLS = [
    "https://rapira.net/exchange/USDT_RUB",
    "https://rapira.net/exchange",
    "https://rapira.org/exchange/USDT_RUB",
]

HTTP_TIMEOUT = 12

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Telethon (для Mosca)
TG_API_ID = os.getenv("TG_API_ID", "").strip()
TG_API_HASH = os.getenv("TG_API_HASH", "").strip()
TG_STRING_SESSION = os.getenv("TG_STRING_SESSION", "").strip()

USER_AGENT = "Mozilla/5.0 (compatible; RatesBot/1.0; +https://t.me/)"

# --- helpers ---
def to_float(x: str) -> float:
    return float(x.replace(" ", "").replace(",", ".").strip())

def fmt(x: Optional[float]) -> str:
    return "—" if x is None else f"{x:.2f}"

@dataclass
class Rate:
    buy: Optional[float]   # RUB за 1 USDT (купить USDT)
    sell: Optional[float]  # RUB за 1 USDT (продать USDT)
    ts: int

def _best_bid_ask_from_numbers(nums: list[float]) -> Tuple[Optional[float], Optional[float]]:
    """
    Эвристика:
    - если нашли много цен: берём две наиболее «ранние» адекватные.
    - обычно buy >= sell (спред), но на некоторых UI может быть наоборот — поправим.
    """
    if len(nums) < 2:
        return None, None
    a, b = nums[0], nums[1]
    # хотим buy >= sell
    buy, sell = (a, b) if a >= b else (b, a)
    return buy, sell

def _extract_prices_from_html(html: str) -> list[float]:
    # достаём все числа вида 77.53 / 77,53
    raw = re.findall(r"(\d{2,3}[.,]\d{2})", html)
    out = []
    for s in raw:
        try:
            v = to_float(s)
            if 40.0 < v < 200.0:  # фильтр диапазона
                out.append(v)
        except:
            pass
    return out

# --- Grinex ---
def fetch_grinex() -> Rate:
    try:
        r = requests.get(GRINEX_URL, timeout=HTTP_TIMEOUT, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        html = r.text

        # Часто в HTML есть стакан/котировки — вытащим первые адекватные цены.
        nums = _extract_prices_from_html(html)
        buy, sell = _best_bid_ask_from_numbers(nums)

        return Rate(buy=buy, sell=sell, ts=int(time.time()))
    except Exception as e:
        logging.warning(f"Grinex parse failed: {e}")
        return Rate(buy=None, sell=None, ts=int(time.time()))

# --- ABCEX ---
def fetch_abcex() -> Rate:
    try:
        r = requests.get(ABCEX_URL, timeout=HTTP_TIMEOUT, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        html = r.text

        # На mobile open-orders обычно есть список ордеров; вытащим цены.
        nums = _extract_prices_from_html(html)
        buy, sell = _best_bid_ask_from_numbers(nums)

        return Rate(buy=buy, sell=sell, ts=int(time.time()))
    except Exception as e:
        logging.warning(f"ABCEX parse failed: {e}")
        return Rate(buy=None, sell=None, ts=int(time.time()))

# --- Rapira ---
def fetch_rapira() -> Rate:
    last_err = None
    for url in RAPIRA_URLS:
        try:
            r = requests.get(url, timeout=HTTP_TIMEOUT, headers={"User-Agent": USER_AGENT})
            r.raise_for_status()
            html = r.text

            # Пытаемся найти явно "Купить/Продать USDT"
            m_buy = re.search(r"(Купить\s*USDT|Buy\s*USDT)[^\d]{0,30}(\d+[.,]\d+)", html, re.I)
            m_sell = re.search(r"(Продать\s*USDT|Sell\s*USDT)[^\d]{0,30}(\d+[.,]\d+)", html, re.I)
            if m_buy and m_sell:
                buy = to_float(m_buy.group(2))
                sell = to_float(m_sell.group(2))
                if buy < sell:
                    buy, sell = sell, buy
                return Rate(buy=buy, sell=sell, ts=int(time.time()))

            # fallback: просто по цифрам
            nums = _extract_prices_from_html(html)
            buy, sell = _best_bid_ask_from_numbers(nums)
            if buy is not None and sell is not None:
                return Rate(buy=buy, sell=sell, ts=int(time.time()))
        except Exception as e:
            last_err = e
            continue

    logging.warning(f"Rapira parse failed: {last_err}")
    return Rate(buy=None, sell=None, ts=int(time.time()))

# --- Mosca (Telethon user session) ---
def _mosca_entity() -> str:
    # Telethon любит @username. Из ссылки сделаем @Mosca67_bot
    return "@Mosca67_bot"

async def fetch_mosca(tg_client: TelegramClient) -> Rate:
    """
    Просим "Курсы", парсим:
      Купить 1 USDT = 77.53 RUB
      Продать 1 USDT = 77.22 RUB
    """
    ts = int(time.time())
    try:
        entity = _mosca_entity()
        await tg_client.send_message(entity, "Курсы")
        await asyncio.sleep(2.0)

        msgs = await tg_client.get_messages(entity, limit=8)
        text = ""
        for m in msgs:
            if m.message and ("Купить 1 USDT" in m.message) and ("Продать 1 USDT" in m.message):
                text = m.message
                break
        if not text and msgs and msgs[0].message:
            text = msgs[0].message

        m_buy = re.search(r"Купить\s*1\s*USDT\s*=\s*(\d+[.,]\d+)\s*RUB", text, re.I)
        m_sell = re.search(r"Продать\s*1\s*USDT\s*=\s*(\d+[.,]\d+)\s*RUB", text, re.I)

        buy = to_float(m_buy.group(1)) if m_buy else None
        sell = to_float(m_sell.group(1)) if m_sell else None

        return Rate(buy=buy, sell=sell, ts=ts)
    except Exception as e:
        logging.warning(f"Mosca parse failed: {e}")
        return Rate(buy=None, sell=None, ts=ts)

# --- UI ---
def kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📈 Курс", callback_data="rates")]]
    )

def build_text(mosca: Rate, abcex: Rate, grinex: Rate, rapira: Rate) -> str:
    return (
        "📊 *USDT/RUB — покупка / продажа*\n\n"
        f"🟦 *Mosca*: {fmt(mosca.buy)} / {fmt(mosca.sell)}\n"
        f"🟨 *ABCEX*: {fmt(abcex.buy)} / {fmt(abcex.sell)}\n"
        f"🟩 *Grinex*: {fmt(grinex.buy)} / {fmt(grinex.sell)}\n"
        f"🟥 *Rapira*: {fmt(rapira.buy)} / {fmt(rapira.sell)}\n\n"
        "_Если где-то «—», значит источник не удалось прочитать (таймаут/защита/изменили страницу)._"
    )

async def main():
    if not BOT_TOKEN:
        raise RuntimeError("ENV BOT_TOKEN is empty")

    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

    # Telethon для Mosca
    tg_client: Optional[TelegramClient] = None
    if TG_API_ID and TG_API_HASH and TG_STRING_SESSION:
        tg_client = TelegramClient(StringSession(TG_STRING_SESSION), int(TG_API_ID), TG_API_HASH)
        await tg_client.start()
        logging.info("Telethon started (Mosca enabled).")
    else:
        logging.warning("Telethon not configured -> Mosca will show '—'.")

    @dp.message(F.text.in_({"/start", "start", "Старт"}))
    async def start(m: Message):
        await m.answer("Нажми «Курс».", reply_markup=kb())

    @dp.callback_query(F.data == "rates")
    async def rates(cb: CallbackQuery):
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
