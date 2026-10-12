import os
import time
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
TZ = ZoneInfo("Asia/Dubai")

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT",
    "FETUSDT", "PEPEUSDT", "SHIBUSDT", "WIFUSDT", "SUIUSDT",
    "TAOUSDT", "NEARUSDT", "RENDERUSDT", "INJUSDT", "SEIUSDT",
    "APTUSDT", "ONDOUSDT", "ARBUSDT", "OPUSDT", "JUPUSDT",
    "BONKUSDT", "FLOKIUSDT"
]

BASE = "https://data-api.binance.vision"
SESSION = requests.Session()


def send(message):
    if not TOKEN or not CHAT_ID:
        raise RuntimeError("Missing Telegram secrets.")

    response = SESSION.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": message,
            "disable_web_page_preview": True
        },
        timeout=15
    )
    response.raise_for_status()

    result = response.json()
    if not result.get("ok"):
        raise RuntimeError("Telegram did not confirm message delivery.")


def get_json(path, params):
    response = SESSION.get(BASE + path, params=params, timeout=15)
    response.raise_for_status()
    return response.json()


def scan(symbol):
    # Request 26 candles so we can discard the potentially unfinished one.
    candles = get_json(
        "/api/v3/klines",
        {"symbol": symbol, "interval": "15m", "limit": 26}
    )

    # Exclude the currently forming candle.
    candles = candles[:-1]

    if len(candles) < 22:
        raise ValueError("Not enough completed candles for analysis.")

    close = [float(c[4]) for c in candles]
    high = [float(c[2]) for c in candles]
    volume = [float(c[5]) for c in candles]

    price = close[-1]
    ch1 = (price / close[-5] - 1) * 100
    ch4 = (price / close[-17] - 1) * 100

    avg_volume = sum(volume[-21:-1]) / 20
    volume_ratio = volume[-1] / avg_volume if avg_volume else 0

    resistance = max(high[-21:-1])
    breakout = price > resistance

    ticker = get_json("/api/v3/ticker/24hr", {"symbol": symbol})
    change_24h = float(ticker.get("priceChangePercent", 0))

    score = 0
    reasons = []

    if ch1 > 1:
        score += 15
        reasons.append(f"~1h momentum +{ch1:.2f}%")

    if ch4 > 2:
        score += 20
        reasons.append(f"4h momentum +{ch4:.2f}%")

    if volume_ratio >= 1.8:
        score += 25
        reasons.append(f"volume {volume_ratio:.1f}x recent average")

    if breakout:
        score += 25
        reasons.append("price above prior ~5h high")

    if price > sum(close[-5:-1]) / 4:
        score += 10
        reasons.append("above recent short-term average")

    if change_24h > 5:
        score += 5
        reasons.append(f"24h change +{change_24h:.1f}%")

    bearish = ch1 < -2 or (ch4 < -4 and volume_ratio >= 1.8)

    if score < 45 and not bearish:
        return None

    if bearish and score < 45:
        kind = "DOWNSIDE / FAILED-MOMENTUM WARNING"
    elif breakout and volume_ratio >= 1.8:
        kind = "BREAKOUT CANDIDATE"
    else:
        kind = "EARLY MOMENTUM WARNING"

    message = (
        f"{'⚠️' if bearish else '🚨'} CRYPTO BULL RUN RADAR\n"
        f"{kind}\n"
        f"Coin: {symbol}\n"
        f"Score: {score}/100\n"
        f"Price: {price:.8g} USDT\n"
        f"24h: {change_24h:+.2f}% | "
        f"Volume vs average: {volume_ratio:.1f}x\n"
        f"Reference level: {resistance:.8g} USDT\n"
        f"Signals: {', '.join(reasons) if reasons else 'Momentum warning'}\n"
        f"Time: {datetime.now(TZ).strftime('%Y-%m-%d %H:%M GST')}\n\n"
        "Rule-based screening only, not financial advice. "
        "Verify liquidity, candle close and news."
    )

    return score, message


def main():
    if not TOKEN or not CHAT_ID:
        raise SystemExit("Set Telegram secrets in GitHub repository settings.")

    print("Radar scan started:", datetime.now(TZ).isoformat())
    print("Symbols configured:", len(SYMBOLS))

    successful = 0
    failed = 0
    signals = []
    errors = []

    for symbol in SYMBOLS:
        try:
            result = scan(symbol)
            successful += 1

            if result:
                signals.append(result)

        except Exception as error:
            failed += 1
            detail = f"{symbol}: {type(error).__name__}: {error}"
            errors.append(detail)
            print("SCAN ERROR:", detail)

        time.sleep(0.12)

    print(f"Market data scans successful: {successful}/{len(SYMBOLS)}")
    print(f"Market data scans failed: {failed}")
    print(f"Signals detected: {len(signals)}")

    # Never report an apparently quiet market if all data requests failed.
    if successful == 0:
        raise SystemExit(
            "FATAL: No symbols were successfully analysed. "
            "Check the market-data API and the errors above."
        )

    signals.sort(reverse=True, key=lambda item: item[0])

    sent = 0
    send_failed = 0

    for _, message in signals:
        print(message)

        try:
            send(message)
            sent += 1
            print("Telegram alert delivered.")
        except Exception as error:
            send_failed += 1
            print("TELEGRAM SEND ERROR:", type(error).__name__, str(error))

    print(f"Telegram alerts delivered: {sent}")
    print(f"Telegram alert delivery failures: {send_failed}")

    if not signals:
        print("No alert thresholds met among successfully analysed symbols.")

    if failed:
        print("Some symbols failed; see SCAN ERROR messages above.")

    if send_failed:
        raise SystemExit("One or more Telegram alerts could not be delivered.")


if __name__ == "__main__":
    main()
