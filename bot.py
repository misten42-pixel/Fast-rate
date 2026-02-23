import asyncio
import logging
import os
import aiohttp
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

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


# ================= ABCEX (HYBRID) =================
async def get_abcex(session):
    depth_url = "https://gateway.abcex.io/api/v2/exchange/public/orderbook/depth?instrumentCode=USDTRUB"
    rates_url = "https://gateway.abcex.io/api/v2/exchange/public/trade/spot/rates"

    try:
        async with session.get(depth_url, timeout=10) as response:
            data = await response.json()

        orderbook = data.get("data", {})
        bids = orderbook.get("bids", [])
        asks = orderbook.get("asks", [])

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

    # fallback на rates
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


# ================= BESTCHANGE =================
async def parse_bestchange(url, title):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                html = await resp.text()

        soup = BeautifulSoup(html, "lxml")

        rows = soup.select("table tr")  # универсально

        results = []
        count = 0

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 5:
                continue

            name = cols[0].get_text(strip=True)
            rate = cols[1].get_text(strip=True)
            reserve = cols[2].get_text(strip=True)
            limits = cols[3].get_text(strip=True)

            if name and rate:
                results.append(
                    f"{count+1}) {name}\n"
                    f"Курс: {rate}\n"
                    f"Резерв: {reserve}\n"
                    f"Лимиты: {limits}"
                )
                count += 1

            if count == 3:
                break

        if not results:
            return f"{title}: нет данных"

        return f"{title}\n\n" + "\n\n".join(results)

    except Exception as e:
        logging.warning(f"BestChange parse error: {e}")
        return f"{title}: ошибка"


async def get_usdt_aed_buy():
    return await parse_bestchange(
        "https://www.bestchange.com/tether-trc20-to-dirham.html",
        "💱 USDT/AED — Покупка USDT"
    )


async def get_usdt_aed_sell():
    return await parse_bestchange(
        "https://www.bestchange.com/dirham-to-tether-trc20.html",
        "💱 USDT/AED — Продажа USDT"
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
        buy = await get_usdt_aed_buy()
        sell = await get_usdt_aed_sell()

        await message.answer(f"{buy}\n\n{sell}")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
