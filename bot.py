import os
import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.session.aiohttp import AiohttpSession


logging.basicConfig(level=logging.INFO)

# ==========
# ENV
# ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")  # ОБЯЗАТЕЛЬНО в переменных окружения
# Прокси (если нужно): HTTP_PROXY / HTTPS_PROXY (например: http://user:pass@ip:port)
# aiohttp/aiogram возьмут их сами при trust_env=True.

# ==========
# SOURCES
# ==========
GRINEX_RATES_URL = "https://grinex.io/rates?offset=0"
RAPIRA_URL = "https://api.rapira.net/market/exchange-plate-mini?symbol=USDT/RUB"
ABCEX_RATES_URL = "https://gateway.abcex.io/api/v2/exchange/public/trade/spot/rates"

PAIR_HINTS = {"USDTRUB", "USDT/RUB", "USDT_RUB", "USDT-RUB"}


@dataclass
class TopOfBook:
    bid_price: Optional[float] = None
    bid_qty: Optional[float] = None
    ask_price: Optional[float] = None
    ask_qty: Optional[float] = None


def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        # иногда приходит строка "77.27"
        return float(str(x).replace(",", ".").strip())
    except Exception:
        return None


def fmt_price(x: Optional[float]) -> str:
    return "—" if x is None else f"{x:.2f}"


def fmt_qty(x: Optional[float]) -> str:
    return "—" if x is None else f"{x:.2f}"


async def fetch_json(session: aiohttp.ClientSession, url: str, timeout: int = 15) -> Any:
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
        # иногда API отдаёт text/json с неправильным content-type
        text = await r.text()
        try:
            return await r.json(content_type=None)
        except Exception:
            # fallback: попробуем руками
            import json
            return json.loads(text)


# =========================
# Grinex: считаем USDT/RUB
# =========================
async def fetch_grinex(session: aiohttp.ClientSession) -> TopOfBook:
    """
    Grinex /rates отдаёт "usdta7a5" и "a7a5rub" (buy/sell).
    Считаем:
      bid(USDT/RUB) = buy(usdta7a5) * buy(a7a5rub)
      ask(USDT/RUB) = sell(usdta7a5) * sell(a7a5rub)
    Объёма стакана этот endpoint не даёт -> qty = None
    """
    data = await fetch_json(session, GRINEX_RATES_URL)

    # поддержим разные форматы: dict или list
    # ожидаем dict с ключами 'usdta7a5' и 'a7a5rub'
    if not isinstance(data, dict):
        return TopOfBook()

    usdta7a5 = data.get("usdta7a5") or data.get("USDTA7A5") or {}
    a7a5rub = data.get("a7a5rub") or data.get("A7A5RUB") or {}

    u_buy = _to_float(usdta7a5.get("buy"))
    u_sell = _to_float(usdta7a5.get("sell"))
    r_buy = _to_float(a7a5rub.get("buy"))
    r_sell = _to_float(a7a5rub.get("sell"))

    if None in (u_buy, u_sell, r_buy, r_sell):
        return TopOfBook()

    bid = u_buy * r_buy
    ask = u_sell * r_sell
    return TopOfBook(bid_price=bid, bid_qty=None, ask_price=ask, ask_qty=None)


# =========================
# Rapira: топ стакана + qty
# =========================
async def fetch_rapira(session: aiohttp.ClientSession) -> TopOfBook:
    """
    Rapira отдаёт структуру:
      {
        "bid": {"items":[{"price":..., "amount":...}, ...]},
        "ask": {"items":[{"price":..., "amount":...}, ...]}
      }
    Берём items[0].
    """
    data = await fetch_json(session, RAPIRA_URL)
    if not isinstance(data, dict):
        return TopOfBook()

    bid_items = (((data.get("bid") or {}) .get("items")) or [])
    ask_items = (((data.get("ask") or {}) .get("items")) or [])

    bid0 = bid_items[0] if bid_items else {}
    ask0 = ask_items[0] if ask_items else {}

    return TopOfBook(
        bid_price=_to_float(bid0.get("price")),
        bid_qty=_to_float(bid0.get("amount")),
        ask_price=_to_float(ask0.get("price")),
        ask_qty=_to_float(ask0.get("amount")),
    )


# =========================
# ABCEX: публичные rates
# =========================
def _extract_abcex_pair(obj: Any) -> Optional[Dict[str, Any]]:
    """
    На практике ответы у разных API бывают:
      - {"data":[...]}
      - {"result":[...]}
      - просто список [...]
      - {"data":{"list":[...]}} и т.п.
    Ищем любую запись, где встречается USDTRUB / USDT_RUB / USDT/RUB...
    """
    candidates = []

    if isinstance(obj, list):
        candidates = obj
    elif isinstance(obj, dict):
        # варианты вложенности
        for k in ("data", "result", "items", "list"):
            v = obj.get(k)
            if isinstance(v, list):
                candidates = v
                break
            if isinstance(v, dict):
                # иногда list внутри data
                for kk in ("data", "result", "items", "list"):
                    vv = v.get(kk)
                    if isinstance(vv, list):
                        candidates = vv
                        break
                if candidates:
                    break

    for it in candidates:
        if not isinstance(it, dict):
            continue

        # возможные поля названия пары
        name_fields = [
            it.get("pairCode"),
            it.get("symbol"),
            it.get("instrumentCode"),
            it.get("code"),
            it.get("name"),
            it.get("pair"),
        ]
        s = " ".join([str(x) for x in name_fields if x])

        for p in PAIR_HINTS:
            if p in s:
                return it

    return None


async def fetch_abcex(session: aiohttp.ClientSession) -> TopOfBook:
    """
    Публичный rates endpoint (у тебя он есть).
    Не у всех ответов есть объёмы. Если qty не найден — будет None.
    """
    data = await fetch_json(session, ABCEX_RATES_URL)
    it = _extract_abcex_pair(data)
    if not it:
        return TopOfBook()

    # возможные поля цены (бывают разные)
    bid = _to_float(it.get("bid") or it.get("buy") or it.get("bestBid") or it.get("bidPrice"))
    ask = _to_float(it.get("ask") or it.get("sell") or it.get("bestAsk") or it.get("askPrice"))

    # возможные поля объёма
    bid_qty = _to_float(it.get("bidQty") or it.get("bidAmount") or it.get("bestBidQty"))
    ask_qty = _to_float(it.get("askQty") or it.get("askAmount") or it.get("bestAskQty"))

    return TopOfBook(bid_price=bid, bid_qty=bid_qty, ask_price=ask, ask_qty=ask_qty)


# =========================
# UI
# =========================
kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📈 Курс")]],
    resize_keyboard=True
)


def format_line(name: str, tob: TopOfBook) -> str:
    # Покупка/продажа + объём
    return (
        f"{name}:\n"
        f"Покупка: {fmt_price(tob.bid_price)} ({fmt_qty(tob.bid_qty)} USDT)\n"
        f"Продажа: {fmt_price(tob.ask_price)} ({fmt_qty(tob.ask_qty)} USDT)"
    )


async def handle_rate(message: Message, http: aiohttp.ClientSession):
    # параллельно тянем все источники
    grinex_task = fetch_grinex(http)
    rapira_task = fetch_rapira(http)
    abcex_task = fetch_abcex(http)

    grinex, rapira, abcex = await asyncio.gather(
        grinex_task, rapira_task, abcex_task, return_exceptions=True
    )

    def safe(v) -> TopOfBook:
        if isinstance(v, Exception):
            logging.warning("Fetch error: %s", v)
            return TopOfBook()
        return v

    grinex = safe(grinex)
    rapira = safe(rapira)
    abcex = safe(abcex)

    text = (
        "📊 USDT/RUB — топ стакана\n\n"
        "🟩 Grinex\n" + format_line("", grinex).replace(":\n", ":\n", 1).replace(":\n", ":\n") + "\n\n"
        "🟥 Rapira\n" + format_line("", rapira).replace(":\n", ":\n", 1).replace(":\n", ":\n") + "\n\n"
        "🟨 ABCEX\n" + format_line("", abcex).replace(":\n", ":\n", 1).replace(":\n", ":\n") + "\n\n"
        "Если где-то «—», значит источник не дал данные или заблокировал запрос."
    )

    # маленький хак, чтобы не было пустого имени
    text = text.replace("\n\n🟩 Grinex\n:\n", "\n\n🟩 Grinex:\n")
    text = text.replace("\n\n🟥 Rapira\n:\n", "\n\n🟥 Rapira:\n")
    text = text.replace("\n\n🟨 ABCEX\n:\n", "\n\n🟨 ABCEX:\n")

    await message.answer(text, reply_markup=kb)


async def main():
    if not isinstance(BOT_TOKEN, str) or not BOT_TOKEN.strip():
        raise RuntimeError("BOT_TOKEN не задан. Добавь переменную окружения BOT_TOKEN.")

    # aiogram session + proxy from env (trust_env=True)
    aio_session = AiohttpSession(trust_env=True)
    bot = Bot(token=BOT_TOKEN, session=aio_session)
    dp = Dispatcher()

    # общий http session для наших запросов (тоже trust_env=True)
    http = aiohttp.ClientSession(trust_env=True)

    @dp.message(CommandStart())
    async def start(m: Message):
        await m.answer(
            "Привет 👋\nНажми кнопку «Курс», чтобы получить покупку/продажу USDT → RUB.",
            reply_markup=kb
        )

    @dp.message(F.text.in_({"📈 Курс", "Курс", "/rate", "rate"}))
    async def rate(m: Message):
        await handle_rate(m, http)

    try:
        await dp.start_polling(bot)
    finally:
        await http.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
