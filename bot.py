import asyncio
import logging
import os
import aiohttp
import zipfile
import io
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
                return (
                    "🟦 Rapira\n\n"
                    f"🔴 Продажа: {float(market['askPrice']):.2f}\n"
                    f"🟢 Покупка: {float(market['bidPrice']):.2f}"
                )

    except Exception as e:
        logging.warning(f"Rapira error: {e}")

    return "🟦 Rapira: ошибка"


# ================= ABCEX HYBRID =================
async def get_abcex(session):
    depth_url = "https://gateway.abcex.io/api/v2/exchange/public/orderbook/depth?instrumentCode=USDTRUB"
    rates_url = "https://gateway.abcex.io/api/v2/exchange/public/trade/spot/rates"

    # --- depth ---
    try:
        async with session.get(depth_url) as response:
            if response.status == 200:
                data = await response.json()
                orderbook = data.get("data", data)

                bids = orderbook.get("bids", [])
                asks = orderbook.get("asks", [])

                if bids and asks:
                    return (
                        "🔵 ABCEX\n\n"
                        f"🔴 Продажа: {float(asks[0][0]):.2f}\n"
                        f"🟢 Покупка: {float(bids[0][0]):.2f}"
                    )
    except Exception as e:
        logging.warning(f"ABCEX depth error: {e}")

    # --- fallback rates ---
    try:
        async with session.get(rates_url) as response:
            if response.status != 200:
                return "🔵 ABCEX: временно недоступен"

            text = await response.text()

        root = ET.fromstring(text)

        buy = sell = None

        for item in root.findall(".//item"):
            from_currency = item.find("from")
            to_currency = item.find("to")
            out_value = item.find("out")

            if from_currency is not None and to_currency is not None:
                if from_currency.text == "USDT" and to_currency.text == "RUB":
                    sell = float(out_value.text)
                if from_currency.text == "RUB" and to_currency.text == "USDT":
                    buy = round(1 / float(out_value.text), 2)

        if buy and sell:
            return (
                "🔵 ABCEX (rates)\n\n"
                f"🔴 Продажа: {sell:.2f}\n"
                f"🟢 Покупка: {buy:.2f}"
            )

    except Exception as e:
        logging.warning(f"ABCEX rates error: {e}")

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
            return (
                "🟠 Grinex\n\n"
                f"🔴 Продажа: {float(pair['sell']):.2f}\n"
                f"🟢 Покупка: {float(pair['buy']):.2f}"
            )

    except Exception as e:
        logging.warning(f"Grinex error: {e}")

    return "🟠 Grinex: ошибка"


# ================= BESTCHANGE PUBLIC MIRRORS =================async def get_bestchange(session):

    async def get_bestchange(session):

    proxy = os.getenv("PROXY_URL")

    urls = [
        "http://mirror1.bestchange.app/info.zip",
        "http://mirror2.bestchange.app/info.zip",
        "http://mirror3.bestchange.app/info.zip",
        "http://mirror4.bestchange.app/info.zip",
        "http://api.bestchange.ru/info.zip",
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "*/*",
        "Connection": "keep-alive",
    }

    for url in urls:
        try:
            async with session.get(
                url,
                headers=headers,
                timeout=15,
                proxy=proxy  # ← ВОТ ОНО
            ) as response:

                if response.status != 200:
                    continue

                data = await response.read()

            with zipfile.ZipFile(io.BytesIO(data)) as z:
                rates_xml = z.read("rates.xml")
                exch_xml = z.read("exchangers.xml")
                curr_xml = z.read("currencies.xml")

            rates_root = ET.fromstring(rates_xml)
            exch_root = ET.fromstring(exch_xml)
            curr_root = ET.fromstring(curr_xml)

            usdt_id = None
            aed_id = None

            for item in curr_root.findall("item"):
                name = item.find("name").text.lower()
                cid = item.find("id").text

                if "trc20" in name and "tether" in name:
                    usdt_id = cid

                if "aed" in name:
                    aed_id = cid

            if not usdt_id or not aed_id:
                continue

            exchangers = {
                item.find("id").text: item.find("name").text
                for item in exch_root.findall("item")
            }

            results = []

            for rate in rates_root.findall("item"):
                if (
                    rate.find("from").text == usdt_id and
                    rate.find("to").text == aed_id
                ):
                    exch_id = rate.find("exchange").text
                    price = float(rate.find("in").text)

                    results.append(
                        (exchangers.get(exch_id, "Unknown"), price)
                    )

            results = sorted(results, key=lambda x: x[1])[:3]

            if results:
                text = "💱 USDT/AED (Top 3)\n\n"
                for i, (name, price) in enumerate(results, 1):
                    text += f"{i}) {name}\nКурс: {price:.4f}\n\n"
                return text.strip()

        except Exception as e:
            logging.warning(f"BestChange proxy error: {e}")
            continue

    return "💱 USDT/AED: нет данных"


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
            "Выберите направление:",
            reply_markup=keyboard
        )

    # --- RUB ---
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

        clean_results = [
            r if not isinstance(r, Exception) else "⚠ Ошибка получения данных"
            for r in results
        ]

        await message.answer("\n\n".join(clean_results))

    # --- AED ---
    @dp.message(lambda message: message.text == "💱 USDT/AED")
    async def aed_handler(message: types.Message):

        timeout = aiohttp.ClientTimeout(total=10)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            result = await get_bestchange(session)

        await message.answer(result)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
