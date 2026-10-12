import os
import time
import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "300"))
COOLDOWN_MINUTES = int(os.getenv("COOLDOWN_MINUTES", "60"))
TZ = ZoneInfo("Asia/Dubai")

# Binance spot symbols. Expand this list whenever you want.
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT",
    "KASUSDT", "AKTUSDT", "FETUSDT", "PEPEUSDT", "SHIBUSDT",
    "WIFUSDT", "SUIUSDT", "TAOUSDT", "NEARUSDT", "RENDERUSDT",
    "INJUSDT", "SEIUSDT", "APTUSDT", "ONDOUSDT", "ARBUSDT",
    "OPUSDT", "JUPUSDT", "BONKUSDT", "FLOKIUSDT"
]
BASE_URL = "https://api.binance.com"

# Prevent repeat alerts for the same coin/signal type.
last_alert = {}

def now_local():
    return datetime.now(TZ)

def telegram_send(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials are missing; message not sent.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    response = requests.post(
        url,
        json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "disable_web_page_preview": True},
        timeout=15,
    )
    response.raise_for_status()

def get_klines(symbol, interval="15m", limit=30):
    response = requests.get(
        f"{BASE_URL}/api/v3/klines",
        params={"symbol": symbol, "interval": interval, "limit": limit},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()

def get_ticker(symbol):
    response = requests.get(
        f"{BASE_URL}/api/v3/ticker/24hr",
        params={"symbol": symbol},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()

def evaluate(symbol):
    # Use 15-minute candles; the last candle may still be forming.
    candles = get_klines(symbol, "15m", 25)
    if len(candles) < 22:
        return None

    # Each kline: open time, open, high, low, close, volume, ...
    closes = [float(c[4]) for c in candles]
    highs = [float(c[2]) for c in candles]
    volumes = [float(c[5]) for c in candles]

    latest_close = closes[-1]
    prior_closes = closes[-5:-1]
    previous_highs = highs[-21:-1]
    recent_volumes = volumes[-21:-1]
    avg_volume = sum(recent_volumes) / len(recent_volumes) if recent_volumes else 0
    volume_ratio = volumes[-1] / avg_volume if avg_volume else 0
    change_1h = ((latest_close / closes[-5]) - 1) * 100 if closes[-5] else 0
    change_4h = ((latest_close / closes[-17]) - 1) * 100 if closes[-17] else 0
    resistance = max(previous_highs) if previous_highs else latest_close
    breakout = latest_close > resistance
    momentum = latest_close > sum(prior_closes) / len(prior_closes)
    ticker = get_ticker(symbol)
    change_24h = float(ticker.get("priceChangePercent", 0))
    quote_volume = float(ticker.get("quoteVolume", 0))

    score = 0
    reasons = []
    if change_1h > 1.0:
        score += 15
        reasons.append(f"15m momentum: +{change_1h:.2f}% over ~1h")
    if change_4h > 2.0:
        score += 20
        reasons.append(f"4h momentum: +{change_4h:.2f}%")
    if volume_ratio >= 1.8:
        score += 25
        reasons.append(f"volume spike: {volume_ratio:.1f}× recent average")
    if breakout:
        score += 25
        reasons.append("15m close above the prior 5h high")
    if momentum:
        score += 10
        reasons.append("short-term price above recent average")
    if change_24h > 5:
        score += 5
        reasons.append(f"24h change: +{change_24h:.1f}%")

    # A simple warning flag; this is a screening signal, not a prediction.
    bearish = change_1h < -2.0 or (change_4h < -4.0 and volume_ratio >= 1.8)
    if score >= 45:
        kind = "CONFIRMED BREAKOUT CANDIDATE" if breakout and volume_ratio >= 1.8 else "EARLY MOMENTUM WARNING"
        return {
            "kind": kind, "score": score, "symbol": symbol,
            "price": latest_close, "change_24h": change_24h,
            "volume_ratio": volume_ratio, "quote_volume": quote_volume,
            "reasons": reasons, "bearish": bearish, "resistance": resistance
        }
    if bearish:
        return {
            "kind": "DOWNSIDE / FAILED-MOMENTUM WARNING", "score": score,
            "symbol": symbol, "price": latest_close, "change_24h": change_24h,
            "volume_ratio": volume_ratio, "quote_volume": quote_volume,
            "reasons": [f"1h change {change_1h:.2f}%; 4h change {change_4h:.2f}%"],
            "bearish": True, "resistance": resistance
        }
    return None

def format_alert(signal):
    stamp = now_local().strftime("%Y-%m-%d %H:%M GST")
    direction = "⚠️" if signal["bearish"] else "🚨"
    reasons = "\n".join(f"• {r}" for r in signal["reasons"])
    return (
        f"{direction} CRYPTO BULL RUN RADAR\n"
        f"{signal['kind']}\n"
        f"Coin: {signal['symbol']}\n"
        f"Score: {signal['score']}/100\n"
        f"Price: {signal['price']:.8g} USDT\n"
        f"24h: {signal['change_24h']:+.2f}% | Volume vs avg: {signal['volume_ratio']:.1f}×\n"
        f"Approx. 24h quote volume: ${signal['quote_volume']:,.0f}\n"
        f"Signals:\n{reasons}\n"
        f"Reference level: {signal['resistance']:.8g} USDT\n"
        f"Time: {stamp}\n\n"
        "Screening alert only—not financial advice. Confirm liquidity, news, and candle close before acting."
    )

def should_send(signal):
    key = (signal["symbol"], signal["kind"])
    now = time.time()
    previous = last_alert.get(key, 0)
    if now - previous < COOLDOWN_MINUTES * 60:
        return False
    last_alert[key] = now
    return True

def run_scan():
    signals = []
    for symbol in SYMBOLS:
        try:
            result = evaluate(symbol)
            if result:
                signals.append(result)
        except requests.HTTPError as exc:
            print(f"{symbol}: HTTP error: {exc}")
        except Exception as exc:
            print(f"{symbol}: scan error: {exc}")
        time.sleep(0.15)  # be gentle with public API rate limits

    signals.sort(key=lambda item: item["score"], reverse=True)
    for signal in signals:
        if should_send(signal):
            message = format_alert(signal)
            print(message)
            try:
                telegram_send(message)
            except Exception as exc:
                print(f"Telegram send failed: {exc}")

    if not signals:
        print(f"{now_local().isoformat()} — scan complete; no alert thresholds met.")

def main():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ERROR: Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables.")
        raise SystemExit(1)

    print("Crypto Bull Run Radar started.")
    print(f"Checking {len(SYMBOLS)} symbols every {CHECK_INTERVAL_SECONDS}s.")
    telegram_send(
        "✅ Crypto Bull Run Radar is online.\n"
        f"Monitoring {len(SYMBOLS)} crypto pairs; scan interval {CHECK_INTERVAL_SECONDS // 60} minutes.\n"
        "Signals are technical screening alerts, not guaranteed predictions."
    )
    while True:
        started = time.time()
        run_scan()
        elapsed = time.time() - started
        time.sleep(max(10, CHECK_INTERVAL_SECONDS - elapsed))

if __name__ == "__main__":
    main()
