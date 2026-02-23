import asyncio
import logging
import os
import aiohttp
import xml.etree.ElementTree as ET

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
PROXY_URL = os.getenv("PROXY_URL")

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

        return "🟦 Rapira: нет данных"

    except Exception as e:
        logging.warning(f"Rapira error: {e}")
        return "🟦 Rapira: ошибка"


# ================= ABCEX HYBRID =================
async def get_abcex(session):

    depth_url = "https://gateway.abcex.io/api/v2/exchange/public/orderbook/depth?instrumentCode=USDTRUB"
    rates_url = "https://gateway.abcex.io/api/v2/exchange/public/trade/spot/rates"

    # 1️⃣ Пытаемся стакан
    try:
        async with session.get(depth_url, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                orderbook = data.get("data", data)

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
    except Exception as e:
        logging.warning(f"ABCEX depth error: {e}")

    # 2️⃣ fallback XML rates
    try:
        async with session.get(rates_url, timeout=10) as response:
            text = await response.text()

        root = ET.fromstring(text)

        buy = None
        sell = None

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

        return "🔵 ABCEX: временно недоступен"

    except Exception as e:
        logging.warning(f"ABCEX rates error: {e}")
        return "🔵 ABCEX: временно недоступен"


# ================= GRINEX =================
async def get_grinex(session):
    url = "https://grinex.io/rates?offset=0"

    try:
        async with session.get(url, timeout=10) as response:
            data = await response.json()

        pair = data.get("usdta7a5")

        if not pair:
            return "🟠 Grinex: нет данных"

        buy = float(pair.get("buy", 0))
        sell = float(pair.get("sell", 0))

        return (
            "🟠 Grinex\n\n"
            f"🔴 Продажа: {sell:.2f}\n"
            f"🟢 Покупка: {buy:.2f}"
        )

    except Exception as e:
        logging.warning(f"Grinex error: {e}")
        return "🟠 Grinex: ошибка"


# ================= BESTCHANGE (proxy test) =================
from bs4 import BeautifulSoup


async def parse_bestchange(session, url, is_buy=False):
    async with session.get(url, proxy=PROXY_URL, timeout=15) as response:
        html = await response.text()

    soup = BeautifulSoup(html, "html.parser")

    rows = soup.select("table#content_table tbody tr")

    results = []

    for row in rows[:3]:
        try:
            cells = row.find_all("td")
            if len(cells) < 5:
                continue

            name = cells[0].get_text(strip=True)

            if is_buy:
                # 🔥 берём правильную колонку
                rate = cells[2].get_text(strip=True)
            else:
                rate = cells[1].get_text(strip=True)

            reserve = cells[4].get_text(strip=True)

            results.append(f"{name} — {rate} — резерв: {reserve}")

        except:
            continue

    return results


async def get_bestchange(session):
    try:
        buy_url = "https://www.bestchange.com/tether-trc20-to-dirham.html"
        sell_url = "https://www.bestchange.com/dirham-to-tether-trc20.html"

       buy_list = await parse_bestchange(session, buy_url, is_buy=True)
sell_list = await parse_bestchange(session, sell_url, is_buy=False)

        text = "💱 USDT/AED\n\n"

        text += "🔴 Продажа USDT\n"
        for i, item in enumerate(sell_list, 1):
            text += f"{i}. {item}\n"

        text += "\n🟢 Покупка USDT\n"
        for i, item in enumerate(buy_list, 1):
            text += f"{i}. {item}\n"

        return text

    except Exception as e:
        logging.warning(f"BestChange parsing error: {e}")
        return "💱 USDT/AED: нет данных"


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
            "Бот запущен.\nНажмите кнопку ниже:",
            reply_markup=keyboard
        )

    @dp.message(lambda message: message.text == "📊 Rate USDT/₽")
    async def rate_handler(message: types.Message):
        async with aiohttp.ClientSession() as session:
            results = await asyncio.gather(
                get_rapira(session),
                get_abcex(session),
                get_grinex(session)
            )

        await message.answer("\n\n".join(results))

    @dp.message(lambda message: message.text == "💱 USDT/AED")
    async def aed_handler(message: types.Message):
        async with aiohttp.ClientSession() as session:
            result = await get_bestchange(session)

        await message.answer(result)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
