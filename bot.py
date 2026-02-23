import asyncio
import aiohttp
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from bs4 import BeautifulSoup

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не установлен")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ================== KEYBOARD ==================

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Rate USDT/₽")],
        [KeyboardButton(text="💱 USDT/AED")],
    ],
    resize_keyboard=True
)

# ================== RAPIRA ==================

async def get_rapira():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.rapira.net/market/exchange-plate-mini?symbol=USDT/RUB",
                timeout=10
            ) as resp:
                data = await resp.json()

        bid = data["bids"][0][0]
        ask = data["asks"][0][0]

        return (
            "🟦 Rapira\n\n"
            f"🔴 Продажа: {ask}\n"
            f"🟢 Покупка: {bid}"
        )
    except:
        return "🟦 Rapira\n\nВременно недоступно"

# ================== ABCEX ==================

async def get_abcex():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://gateway.abcex.io/api/v2/exchange/public/trade/spot/rates",
                timeout=10
            ) as resp:
                data = await resp.json()

        for pair in data["data"]:
            if pair["symbol"] == "USDT/RUB":
                bid = pair["bidPrice"]
                ask = pair["askPrice"]

                return (
                    "🟦 ABCEX\n\n"
                    f"🔴 Продажа: {ask}\n"
                    f"🟢 Покупка: {bid}"
                )

        return "🟦 ABCEX\n\nНет данных"

    except:
        return "🟦 ABCEX\n\nВременно недоступно"

# ================== GRINEX ==================

async def get_grinex():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://grinex.io/trading/usdta7a5",
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0"}
            ) as resp:
                html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")
        prices = soup.find_all("span", class_="price")

        if len(prices) >= 2:
            ask = prices[0].text.strip()
            bid = prices[1].text.strip()

            return (
                "🟧 Grinex\n\n"
                f"🔴 Продажа: {ask}\n"
                f"🟢 Покупка: {bid}"
            )

        return "🟧 Grinex\n\nНет данных"

    except:
        return "🟧 Grinex\n\nВременно недоступно"

# ================== BESTCHANGE HTML ==================

BESTCHANGE_BUY = "https://www.bestchange.com/tether-trc20-to-dirham.html"
BESTCHANGE_SELL = "https://www.bestchange.com/dirham-to-tether-trc20.html"

async def parse_bestchange(url, title):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0"}
            ) as resp:
                html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", id="content_table")

        if not table:
            return f"{title}\n\nНет данных"

        rows = table.find_all("tr", class_="bj")[:3]

        if not rows:
            return f"{title}\n\nНет данных"

        text = f"{title}\n\n"

        for i, row in enumerate(rows, 1):
            name = row.find("td", class_="bjname").text.strip()
            rate = row.find("td", class_="bjrate").text.strip()
            reserve = row.find("td", class_="bjreserve").text.strip()

            text += (
                f"{i}) {name}\n"
                f"Курс: {rate}\n"
                f"Резерв: {reserve}\n\n"
            )

        return text.strip()

    except:
        return f"{title}\n\nВременно недоступно"

async def get_usdt_aed():
    buy = await parse_bestchange(
        BESTCHANGE_BUY,
        "💱 USDT/AED — Покупка USDT"
    )

    sell = await parse_bestchange(
        BESTCHANGE_SELL,
        "💱 USDT/AED — Продажа USDT"
    )

    return f"{buy}\n\n{sell}"

# ================== HANDLERS ==================

@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("Выберите направление:", reply_markup=keyboard)

@dp.message(F.text == "📊 Rate USDT/₽")
async def rub_handler(message: Message):
    rapira = await get_rapira()
    abcex = await get_abcex()
    grinex = await get_grinex()

    await message.answer(f"{rapira}\n\n{abcex}\n\n{grinex}")

@dp.message(F.text == "💱 USDT/AED")
async def aed_handler(message: Message):
    result = await get_usdt_aed()
    await message.answer(result)

# ================== RUN ==================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
