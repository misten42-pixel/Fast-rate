async def get_abcex(session):
    depth_url = "https://gateway.abcex.io/api/v2/exchange/public/orderbook/depth?instrumentCode=USDTRUB"
    rates_url = "https://gateway.abcex.io/api/v2/exchange/public/trade/spot/rates"

    # ===== 1. Пытаемся depth =====
    try:
        async with session.get(depth_url) as response:
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
    except Exception:
        pass

    # ===== 2. Fallback на rates =====
    try:
        async with session.get(rates_url) as response:
            if response.status != 200:
                return "🔵 ABCEX: временно недоступен"

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

    except Exception:
        pass

    return "🔵 ABCEX: временно недоступен"
