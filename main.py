import os
import time
import requests
from flask import Flask
from threading import Thread

app = Flask(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

AMOUNT = 1000
MIN_PROFIT = 1.0

# Предполагаемые расходы на два обмена
# и прочие издержки — 0,6%
ESTIMATED_COST = 0.6

CHECK_INTERVAL = 60

DEXES = [
    "pancakeswap",
    "biswap",
    "apeswap",
    "thena"
]

LINK_ADDRESS = (
    "0xf8a0bf9cf54bb92f17374d9e9a321e6a111a51bd"
)

def send_telegram(message):
    if not TOKEN or not CHAT_ID:
        print("Telegram settings missing")
        return

    url = (
        f"https://api.telegram.org/"
        f"bot{TOKEN}/sendMessage"
    )

    try:
        requests.post(
            url,
            json={
                "chat_id": CHAT_ID,
                "text": message
            },
            timeout=15
        )
    except Exception as e:
        print("Telegram error:", e)


def get_prices():
    url = (
        "https://api.dexscreener.com/"
        f"latest/dex/tokens/{LINK_ADDRESS}"
    )

    response = requests.get(url, timeout=20)
    response.raise_for_status()

    data = response.json()
    prices = []

    for pair in data.get("pairs", []):

        if pair.get("chainId") != "bsc":
            continue

        dex = pair.get("dexId", "").lower()

        if not any(name in dex for name in DEXES):
            continue

        base = pair.get("baseToken", {})
        quote = pair.get("quoteToken", {})

        if base.get("symbol", "").upper() != "LINK":
            continue

        if quote.get("symbol", "").upper() != "USDT":
            continue

        price = pair.get("priceUsd")

        if not price:
            continue

        prices.append({
            "dex": dex,
            "price": float(price),
            "liquidity": pair.get(
                "liquidity", {}
            ).get("usd", 0)
        })

    return prices


def monitor():

    print("LinkBNB monitoring started")

    last_signal = None

    while True:

        try:
            prices = get_prices()

            if len(prices) >= 2:

                cheapest = min(
                    prices,
                    key=lambda x: x["price"]
                )

                highest = max(
                    prices,
                    key=lambda x: x["price"]
                )

                buy_price = cheapest["price"]
                sell_price = highest["price"]

                gross_profit = (
                    (sell_price / buy_price - 1)
                    * 100
                )

                net_profit = (
                    gross_profit - ESTIMATED_COST
                )

                profit_usdt = (
                    AMOUNT * net_profit / 100
                )

                if net_profit >= MIN_PROFIT:

                    signal = (
                        cheapest["dex"],
                        highest["dex"],
                        round(buy_price, 5),
                        round(sell_price, 5)
                    )

                    if signal != last_signal:

                        message = (
                            "🚀 LINK/USDT ARBITRAGE\n\n"
                            f"Сеть: BNB Chain\n\n"
                            f"Купить: {cheapest['dex']}\n"
                            f"Цена: {buy_price:.5f} USDT\n\n"
                            f"Продать: {highest['dex']}\n"
                            f"Цена: {sell_price:.5f} USDT\n\n"
                            f"Сумма: {AMOUNT} USDT\n"
                            f"Расчётная прибыль: "
                            f"{net_profit:.2f}%\n"
                            f"Прибыль: {profit_usdt:.2f} USDT\n\n"
                            "⚠️ Оценка по рыночным ценам. "
                            "Не учитывает фактическое "
                            "проскальзывание и изменение "
                            "котировок при исполнении."
                        )

                        send_telegram(message)

                        last_signal = signal

            else:
                print("Not enough LINK/USDT pairs")

        except Exception as e:
            print("Monitoring error:", e)

        time.sleep(CHECK_INTERVAL)


@app.route("/")
def home():
    return "LinkBNB bot is running"


if __name__ == "__main__":

    thread = Thread(
        target=monitor,
        daemon=True
    )

    thread.start()

    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 10000))
    )
