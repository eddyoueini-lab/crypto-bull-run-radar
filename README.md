# Crypto Bull Run Radar

A lightweight Python background worker that scans a watchlist of Binance spot pairs and sends Telegram alerts.

## What it does
- Checks 15-minute price candles and 24-hour ticker data.
- Looks for momentum, volume spikes, and breakouts above recent highs.
- Sends early-momentum, breakout-candidate, and downside-warning alerts.
- Default scan interval: 5 minutes.
- Default alert cooldown: 60 minutes per coin and alert type.

## Important limitations
- These are rule-based screening signals, not predictions or financial advice.
- A “confirmed breakout candidate” is a technical condition, not confirmation that a bull market has begun.
- Data comes from Binance public spot endpoints. Some pairs may be unavailable in some jurisdictions or may be delisted; remove unavailable symbols from `SYMBOLS`.
- This basic version does not detect wallet-level whale movements or use a news feed.
- The free public API can rate-limit requests. If errors appear frequently, reduce the watchlist or increase the scan interval.
- The Render worker is configured as a paid `starter` worker; check current Render pricing before deploying.

## Deploy on Render
1. Push these files to a private GitHub repository.
2. In Render, choose **New + → Blueprint** and select the repository, or create a **Background Worker** from the repo.
3. Add environment variables:
   - `TELEGRAM_BOT_TOKEN` = your BotFather token
   - `TELEGRAM_CHAT_ID` = your Telegram chat ID
   - `CHECK_INTERVAL_SECONDS` = `300`
   - `COOLDOWN_MINUTES` = `60`
4. Deploy and check logs for `Crypto Bull Run Radar started.`.
5. You should receive an online message in Telegram.

Never publish the bot token in your repository or share it in public.
