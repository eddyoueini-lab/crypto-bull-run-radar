import os, time, requests
from datetime import datetime
from zoneinfo import ZoneInfo

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
TZ = ZoneInfo("Asia/Dubai")
SYMBOLS = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","ADAUSDT","DOGEUSDT","AVAXUSDT","LINKUSDT","DOTUSDT","KASUSDT","AKTUSDT","FETUSDT","PEPEUSDT","SHIBUSDT","WIFUSDT","SUIUSDT","TAOUSDT","NEARUSDT","RENDERUSDT","INJUSDT","SEIUSDT","APTUSDT","ONDOUSDT","ARBUSDT","OPUSDT","JUPUSDT","BONKUSDT","FLOKIUSDT"]
BASE = "https://data-api.binance.vision"

def send(text):
    if not TOKEN or not CHAT_ID:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID GitHub secret.")
    r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True}, timeout=15)
    r.raise_for_status()

def get_json(path, params):
    r = requests.get(BASE + path, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

def scan(symbol):
    candles = get_json("/api/v3/klines", {"symbol":symbol, "interval":"15m", "limit":25})
    if len(candles) < 22: return None
    close = [float(c[4]) for c in candles]
    high = [float(c[2]) for c in candles]
    vol = [float(c[5]) for c in candles]
    price = close[-1]
    ch1 = (price / close[-5] - 1) * 100
    ch4 = (price / close[-17] - 1) * 100
    avgvol = sum(vol[-21:-1]) / 20
    vr = vol[-1] / avgvol if avgvol else 0
    resistance = max(high[-21:-1])
    breakout = price > resistance
    ticker = get_json("/api/v3/ticker/24hr", {"symbol":symbol})
    ch24 = float(ticker.get("priceChangePercent", 0))
    score, reasons = 0, []
    if ch1 > 1: score += 15; reasons.append(f"~1h momentum +{ch1:.2f}%")
    if ch4 > 2: score += 20; reasons.append(f"4h momentum +{ch4:.2f}%")
    if vr >= 1.8: score += 25; reasons.append(f"volume {vr:.1f}x recent average")
    if breakout: score += 25; reasons.append("price above prior ~5h high")
    if price > sum(close[-5:-1])/4: score += 10; reasons.append("above recent short-term average")
    if ch24 > 5: score += 5; reasons.append(f"24h change +{ch24:.1f}%")
    bearish = ch1 < -2 or (ch4 < -4 and vr >= 1.8)
    if score < 45 and not bearish: return None
    kind = ("DOWNSIDE / FAILED-MOMENTUM WARNING" if bearish and score < 45 else
            "BREAKOUT CANDIDATE" if breakout and vr >= 1.8 else "EARLY MOMENTUM WARNING")
    return (score, f"{'⚠️' if bearish else '🚨'} CRYPTO BULL RUN RADAR\n{kind}\n"
        f"Coin: {symbol}\nScore: {score}/100\nPrice: {price:.8g} USDT\n"
        f"24h: {ch24:+.2f}% | Volume vs average: {vr:.1f}x\n"
        f"Reference level: {resistance:.8g} USDT\nSignals: " + (", ".join(reasons) if reasons else f"1h {ch1:.2f}%; 4h {ch4:.2f}%") +
        f"\nTime: {datetime.now(TZ).strftime('%Y-%m-%d %H:%M GST')}\n\n"
        "Rule-based screening only, not financial advice. Verify candle close, liquidity and news.")

def main():
    if not TOKEN or not CHAT_ID: raise SystemExit("Set Telegram secrets in GitHub repository settings.")
    print("Radar scan started", datetime.now(TZ).isoformat())
    signals = []
    for symbol in SYMBOLS:
        try:
            result = scan(symbol)
            if result: signals.append(result)
        except Exception as e:
            print(symbol, "scan error:", e)
        time.sleep(0.12)
    signals.sort(reverse=True, key=lambda x: x[0])
    for _, message in signals:
        print(message)
        try: send(message)
        except Exception as e: print("Telegram send error:", e)
    if not signals: print("No alert thresholds met.")

if __name__ == "__main__": main()
