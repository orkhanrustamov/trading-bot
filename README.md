# Trading Signal Bot — Setup Guide

## What this bot does
- Watches any ticker list you define (FX pairs, commodities, ETFs)
- Scans every 15 minutes using Yahoo Finance data
- Applies Smart Money Concepts (SMC) + Auto Fibonacci signal logic
- Sends a Telegram alert with Entry / SL / TP (1:2 ratio) when both align
- You tap ✅ or ❌ to approve or skip
- Optionally executes on MetaTrader 5 automatically via MetaAPI

---

## Step 1 — Prerequisites

Make sure you have Python 3.11+ installed:
```bash
python3 --version
```

If not, install from https://python.org

---

## Step 2 — Install dependencies

Open Terminal, navigate to the bot folder:
```bash
cd trading_bot
pip3 install -r requirements.txt
```

---

## Step 3 — Configure your bot token

1. Copy the example env file:
```bash
cp .env.example .env
```

2. Open `.env` in any text editor and fill in:

```
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
TELEGRAM_CHAT_ID=987654321
```

**Getting your bot token:**
- Message @BotFather on Telegram
- Send `/newbot`, follow prompts
- Copy the token it gives you

**Getting your chat ID:**
- Message @userinfobot on Telegram
- It replies with your numeric ID
- Paste that number into TELEGRAM_CHAT_ID

---

## Step 4 — Run the bot

```bash
python3 bot.py
```

You should see:
```
INFO - Bot started. Listening...
```

---

## Step 5 — Use the bot in Telegram

Open your bot in Telegram and send:

### Add tickers to watch:
```
/add EURUSD=X 1h
/add GBPUSD=X 4h
/add GC=F 1d
/add SPY 1d
/add QQQ 4h
```

### Common ticker symbols:
| Asset        | Yahoo Symbol |
|--------------|-------------|
| EUR/USD      | EURUSD=X    |
| GBP/USD      | GBPUSD=X    |
| USD/JPY      | USDJPY=X    |
| AUD/USD      | AUDUSD=X    |
| USD/CAD      | USDCAD=X    |
| USD/CHF      | USDCHF=X    |
| NZD/USD      | NZDUSD=X    |
| EUR/GBP      | EURGBP=X    |
| EUR/JPY      | EURJPY=X    |
| GBP/JPY      | GBPJPY=X    |
| Gold         | GC=F        |
| Crude Oil    | CL=F        |
| Silver       | SI=F        |
| S&P 500 ETF  | SPY         |
| Nasdaq ETF   | QQQ         |
| Gold ETF     | GLD         |

### Other commands:
```
/list       — see all watched tickers
/scan       — run a manual scan right now
/remove EURUSD=X  — stop watching a ticker
/status     — bot info and last scan time
```

---

## Step 6 — Receiving signals

When a signal fires, you'll get a message like:

```
🟢 BUY SIGNAL — Euro / U.S. Dollar
EURUSD=X • 1h timeframe

Entry:    1.08423
Stop Loss: 1.08201
TP1 (1:1): 1.08645
TP2 (1:2): 1.08867

Signal strength: ⭐⭐⭐
Confluence:
  ✦ SMC trend: Bullish structure
  ✦ AutoFib: price at 61.8% retracement
  ✦ Order block confluence (support)
  ✦ Golden ratio fib zone — high probability reversal

[✅ Open Trade]  [❌ Skip]
```

Tap **✅ Open Trade** to execute (requires MetaAPI setup) or **❌ Skip** to dismiss.

---

## Step 7 (Optional) — Connect MetaTrader 5 for auto-execution

1. Sign up free at https://metaapi.cloud
2. Click "Add Account" → connect your MT5 broker credentials
3. Copy your API Token and Account ID
4. Add to `.env`:
```
META_API_TOKEN=your_metaapi_token
META_API_ACCOUNT_ID=your_account_id
```
5. Restart the bot

When you tap ✅, it will place a market order with SL and TP automatically.

---

## Running 24/7 on your Mac

To keep the bot running even when Terminal is closed:

```bash
# Run in background, log to file
nohup python3 bot.py > bot.log 2>&1 &

# Check it's running
ps aux | grep bot.py

# View logs
tail -f bot.log

# Stop the bot
pkill -f bot.py
```

**Better option — run as a Mac Launch Agent (auto-starts on login):**

Create `/Library/LaunchAgents/com.tradingbot.plist` with the path to your bot.
Or simply keep a Terminal tab open — it's the easiest approach.

---

## Signal logic explained

A signal fires only when **both** conditions are true simultaneously:

**1. SMC (Smart Money Concepts):**
- Detects swing highs and lows
- Confirms a Break of Structure (BOS) or Change of Character (CHoCH)
- Identifies bullish or bearish trend bias
- Looks for Order Block confluence near current price

**2. Auto Fibonacci:**
- Calculates fib levels from recent swing high/low (last 100 bars)
- Fires only when price is within 3% of key levels: 38.2%, 50%, 61.8%, 78.6%
- Higher weight given to 61.8% (Golden Ratio) and 78.6% zones

**SL/TP calculation:**
- Stop Loss = 1.5 × ATR(14) from entry
- TP1 = 1:1 risk/reward
- TP2 = 1:2 risk/reward (used for MT5 execution)

---

## Troubleshooting

**Bot doesn't respond:**
- Check your TELEGRAM_BOT_TOKEN is correct
- Make sure TELEGRAM_CHAT_ID matches your account

**No signals appearing:**
- Use `/scan` to force a scan and check for errors
- Some timeframes need more data — `1d` is most reliable
- Not every candle has a signal — this is normal

**Yahoo Finance errors:**
- Yahoo Finance occasionally rate-limits; the bot will retry next scan
- If a ticker fails consistently, check the symbol is correct

---

## File structure
```
trading_bot/
├── bot.py          — Telegram bot, commands, approval flow
├── scanner.py      — SMC + AutoFib signal logic
├── storage.py      — Watchlist and signal persistence
├── mt5_bridge.py   — MetaTrader 5 execution (optional)
├── requirements.txt
├── .env            — Your tokens (never share this file)
└── data/
    ├── tickers.json  — Your watchlist
    ├── signals.json  — Signal history
    └── state.json    — Bot state
```
