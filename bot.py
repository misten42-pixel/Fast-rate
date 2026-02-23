import asyncio
import logging
import os
import aiohttp
import xml.etree.ElementTree as ET
import zipfile
import io
import time

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

# ================= RAPIRA =================
async def get_rapira(session):
    url = "https://api.rapira.net/open/market/rates"
    try:
        async with session.get(url, timeout=10) as response:
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
    except:
        pass

    return "🟦 Rapira: нет данных"


# ================= ABCEX HYBRID =================
async def get_abcex(session):
    depth_url = "https://gateway.abcex.io/api/v2/exchange/public/orderbook/depth?instrumentCode=USDTRUB"
    rates_url = "https://gateway.abcex.io/api/v2/exchange/public/trade/spot/rates"

    try:
        async with session.get(depth_url, timeout=10) as response:
            data = await response.json()

        bids = data.get("data", {}).get("bids", [])
        asks = data.get("data", {}).get("asks", [])

        if bids and asks:
            buy = float(bids[0][0])
            sell = float(asks[0][0])

            return (
                "🔵 ABCEX\n\n"
                f"🔴 Продажа: {sell:.2f}\n"
                f"🟢 Покупка: {buy:.2f}"
            )
    except:
        pass

    # fallback
    try:
        async with session.get(rates_url, timeout=10) as response:
            text = await response.text()

        root = ET.fromstring(text)

        buy = None
        sell = None

        for item in root.findall(".//item"):
            f = item.find("from")
            t = item.find("to")
            o = item.find("out")

            if f is not None and t is not None:
                if f.text == "USDT" and t.text == "RUB":
                    sell = float(o.text)
                if f.text == "RUB" and t.text == "USDT":
                    buy = round(1 / float(o.text), 2)

        if buy and sell:
            return (
                "🔵 ABCEX (rates)\n\n"
                f"🔴 Продажа: {sell:.2f}\n"
                f"🟢 Покупка: {buy:.2f}"
            )
    except:
        pass

    return "🔵 ABCEX: нет данных"


# ================= GRINEX =================
async def get_grinex(session):
    url = "https://grinex.io/rates?offset=0"
    try:
        async with session.get(url, timeout=10) as response:
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
    except:
        pass

    return "🟠 Grinex: нет данных"


# ================= BESTCHANGE PRODUCTION =================

# ================= BESTCHANGE FINAL STABLE =================

BESTCHANGE_URL = "https://api.bestchange.ru/info.zip"
CACHE_TTL = 60

_bestchange_cache = {
    "timestamp": 0,
    "rates": None,
    "exch": None,
    "curr": None
}


async def get_bestchange_data():
    now = time.time()

    if (
        _bestchange_cache["rates"] is not None
        and now - _bestchange_cache["timestamp"] < CACHE_TTL
    ):
        return (
            _bestchange_cache["rates"],
            _bestchange_cache["exch"],
            _bestchange_cache["curr"]
        )

    async with aiohttp.ClientSession() as session:
        async with session.get(BESTCHANGE_URL, timeout=20) as resp:
            content = await resp.read()

    z = zipfile.ZipFile(io.BytesIO(content))

    rates_xml = z.read("rates.xml")
    exch_xml = z.read("exch.xml")
    curr_xml = z.read("currencies.xml")

    _bestchange_cache["timestamp"] = now
    _bestchange_cache["rates"] = rates_xml
    _bestchange_cache["exch"] = exch_xml
    _bestchange_cache["curr"] = curr_xml

    return rates_xml, exch_xml, curr_xml


def find_currency_id(curr_xml, keyword):
    root = ET.fromstring(curr_xml)

    for curr in root.findall("currency"):
        name = curr.find("name").text.lower()
        if keyword.lower() in name:
            return curr.find("id").text

    return None


def parse_bestchange(rates_xml, exch_xml, from_id, to_id, title, reverse=False):
    rates_root = ET.fromstring(rates_xml)
    exch_root = ET.fromstring(exch_xml)

    exch_dict = {
        exch.find("id").text: exch.find("name").text
        for exch in exch_root.findall("exchanger")
    }

    results = []

    for rate in rates_root.findall("rate"):
        if (
            rate.find("from").text == from_id
            and rate.find("to").text == to_id
        ):
            exch_id = rate.find("exchanger").text
            price = float(rate.find("in").text)
            reserve = rate.find("reserve").text

            name = exch_dict.get(exch_id, "Unknown")
            results.append((price, name, reserve))

    if not results:
        return f"{title}: нет данных"

    results.sort(key=lambda x: x[0], reverse=reverse)
    top3 = results[:3]

    text = f"{title}\n\n"

    for i, (price, name, reserve) in enumerate(top3, 1):
        text += (
            f"{i}) {name}\n"
            f"Курс: {price:.4f}\n"
            f"Резерв: {reserve}\n\n"
        )

    return text.strip()


async def get_usdt_aed_buy():
    rates_xml, exch_xml, curr_xml = await get_bestchange_data()

    usdt_id = find_currency_id(curr_xml, "Tether TRC20")
    aed_id = find_currency_id(curr_xml, "Dirham")

    if not usdt_id or not aed_id:
        return "💱 USDT/AED: валюты не найдены"

    return parse_bestchange(
        rates_xml,
        exch_xml,
        usdt_id,
        aed_id,
        "💱 USDT/AED — Покупка USDT",
        reverse=False
    )


async def get_usdt_aed_sell():
    rates_xml, exch_xml, curr_xml = await get_bestchange_data()

    usdt_id = find_currency_id(curr_xml, "Tether TRC20")
    aed_id = find_currency_id(curr_xml, "Dirham")

    if not usdt_id or not aed_id:
        return "💱 USDT/AED: валюты не найдены"

    return parse_bestchange(
        rates_xml,
        exch_xml,
        aed_id,
        usdt_id,
        "💱 USDT/AED — Продажа USDT",
        reverse=True
    )


# ================= TELEGRAM =================
async def main():
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
            "Выберите направление:",
            reply_markup=keyboard
        )

    @dp.message(lambda m: m.text == "📊 Rate USDT/₽")
    async def rub_handler(message: types.Message):
        async with aiohttp.ClientSession() as session:
            results = await asyncio.gather(
                get_rapira(session),
                get_abcex(session),
                get_grinex(session)
            )
        await message.answer("\n\n".join(results))

    @dp.message(lambda m: m.text == "💱 USDT/AED")
    async def aed_handler(message: types.Message):
        sell = await get_usdt_aed_sell()
        buy = await get_usdt_aed_buy()
        await message.answer(f"{sell}\n\n{buy}")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
