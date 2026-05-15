"""
Trading Signal Bot
------------------
Telegram bot that scans tickers using Yahoo Finance data,
applies SMC + AutoFib signal logic, and sends buy/sell alerts.
"""

import asyncio
import logging
import os
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
from dotenv import load_dotenv
from scanner import Scanner
from storage import Storage

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_ID  = int(os.getenv("TELEGRAM_CHAT_ID", "0"))  # your personal chat ID

storage = Storage()
scanner = Scanner()

# ─── Auth guard ───────────────────────────────────────────────────────────────

def authorized(update: Update) -> bool:
    uid = update.effective_chat.id
    if ALLOWED_ID and uid != ALLOWED_ID:
        return False
    return True

# ─── /start ───────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    text = (
        "👋 *Trading Signal Bot*\n\n"
        "Commands:\n"
        "• /add `TICKER TF` — add ticker & timeframe\n"
        "  e.g. `/add EURUSD=X 1h` or `/add GC=F 4h`\n"
        "• /remove `TICKER` — remove a ticker\n"
        "• /list — show all watched tickers\n"
        "• /scan — run manual scan now\n"
        "• /status — bot status\n\n"
        "Timeframes: `15m` `30m` `1h` `4h` `1d`\n\n"
        "The bot scans every 15 min automatically."
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ─── /add ─────────────────────────────────────────────────────────────────────

async def cmd_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: `/add TICKER TIMEFRAME`\n"
            "Example: `/add EURUSD=X 1h`\n\n"
            "Common tickers:\n"
            "FX: `EURUSD=X` `GBPUSD=X` `USDJPY=X` `AUDUSD=X`\n"
            "Gold/Oil: `GC=F` `CL=F`\n"
            "ETFs: `SPY` `QQQ` `GLD`",
            parse_mode="Markdown"
        )
        return

    ticker = args[0].upper()
    tf     = args[1].lower()

    valid_tfs = ["15m", "30m", "1h", "4h", "1d"]
    if tf not in valid_tfs:
        await update.message.reply_text(
            f"Invalid timeframe `{tf}`.\nChoose from: {', '.join(valid_tfs)}",
            parse_mode="Markdown"
        )
        return

    # Validate ticker exists
    msg = await update.message.reply_text(f"Checking `{ticker}`...", parse_mode="Markdown")
    valid, name = await asyncio.get_event_loop().run_in_executor(
        None, scanner.validate_ticker, ticker
    )
    if not valid:
        await msg.edit_text(
            f"❌ Ticker `{ticker}` not found on Yahoo Finance.\n"
            "Check the symbol and try again.",
            parse_mode="Markdown"
        )
        return

    storage.add_ticker(ticker, tf, name)
    await msg.edit_text(
        f"✅ Added *{name}* (`{ticker}`) on `{tf}` timeframe.\n"
        "Next scan will check this ticker.",
        parse_mode="Markdown"
    )

# ─── /remove ──────────────────────────────────────────────────────────────────

async def cmd_remove(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    if not ctx.args:
        await update.message.reply_text("Usage: `/remove TICKER`", parse_mode="Markdown")
        return

    ticker = ctx.args[0].upper()
    if storage.remove_ticker(ticker):
        await update.message.reply_text(f"✅ Removed `{ticker}`.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ `{ticker}` not in watchlist.", parse_mode="Markdown")

# ─── /list ────────────────────────────────────────────────────────────────────

async def cmd_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    tickers = storage.get_tickers()
    if not tickers:
        await update.message.reply_text(
            "Watchlist is empty.\nUse `/add TICKER TF` to add tickers.",
            parse_mode="Markdown"
        )
        return

    lines = ["📋 *Watchlist:*\n"]
    for t in tickers:
        lines.append(f"• `{t['ticker']}` — {t['name']} — `{t['timeframe']}`")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ─── /scan ────────────────────────────────────────────────────────────────────

async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    tickers = storage.get_tickers()
    if not tickers:
        await update.message.reply_text("Watchlist empty. Add tickers first with `/add`.", parse_mode="Markdown")
        return

    msg = await update.message.reply_text(f"🔍 Scanning {len(tickers)} ticker(s)...")
    await run_scan(ctx.application, manual=True, status_msg=msg)

# ─── /status ──────────────────────────────────────────────────────────────────

async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    tickers  = storage.get_tickers()
    last     = storage.get_last_scan()
    signals  = storage.get_signal_count()
    text = (
        f"🤖 *Bot Status*\n\n"
        f"Watching: {len(tickers)} ticker(s)\n"
        f"Last scan: {last or 'Never'}\n"
        f"Signals sent today: {signals}\n"
        f"Auto-scan: every 15 min"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ─── Signal alert sender ──────────────────────────────────────────────────────

async def send_signal(app, signal: dict):
    """Send a signal alert with approve/skip buttons."""
    direction = signal["direction"]
    ticker    = signal["ticker"]
    name      = signal["name"]
    tf        = signal["timeframe"]
    price     = signal["price"]
    sl        = signal["sl"]
    tp1       = signal["tp1"]
    tp2       = signal["tp2"]
    strength  = signal["strength"]
    reasons   = signal["reasons"]

    emoji = "🟢" if direction == "BUY" else "🔴"
    reason_text = "\n".join(f"  ✦ {r}" for r in reasons)

    text = (
        f"{emoji} *{direction} SIGNAL — {name}*\n"
        f"`{ticker}` • `{tf}` timeframe\n\n"
        f"*Entry:* `{price:.5f}`\n"
        f"*Stop Loss:* `{sl:.5f}`\n"
        f"*TP1 (1:1):* `{tp1:.5f}`\n"
        f"*TP2 (1:2):* `{tp2:.5f}`\n\n"
        f"*Signal strength:* {'⭐' * strength}\n"
        f"*Confluence:*\n{reason_text}\n\n"
        f"_{datetime.now().strftime('%Y-%m-%d %H:%M UTC')}_"
    )

    signal_id = storage.save_signal(signal)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Open Trade", callback_data=f"approve:{signal_id}"),
            InlineKeyboardButton("❌ Skip",       callback_data=f"skip:{signal_id}"),
        ]
    ])

    await app.bot.send_message(
        chat_id=ALLOWED_ID,
        text=text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# ─── Callback handler (approve / skip) ────────────────────────────────────────

async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()

    action, signal_id = query.data.split(":", 1)
    signal = storage.get_signal(signal_id)

    if not signal:
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("⚠️ Signal expired or not found.")
        return

    if action == "skip":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"⏭ Skipped `{signal['ticker']}`.", parse_mode="Markdown")
        storage.mark_signal(signal_id, "skipped")
        return

    if action == "approve":
        await query.edit_message_reply_markup(reply_markup=None)
        # Import here to avoid hard dependency if MT5 not configured
        try:
            from mt5_bridge import place_order
            result = await asyncio.get_event_loop().run_in_executor(
                None, place_order, signal
            )
            if result["success"]:
                await query.message.reply_text(
                    f"✅ *Order placed!*\n"
                    f"Ticket: `{result['ticket']}`\n"
                    f"Entry: `{signal['price']:.5f}`\n"
                    f"SL: `{signal['sl']:.5f}`\n"
                    f"TP: `{signal['tp2']:.5f}`",
                    parse_mode="Markdown"
                )
                storage.mark_signal(signal_id, "executed")
            else:
                await query.message.reply_text(
                    f"❌ Order failed: {result['error']}\n"
                    "Place manually on MT5.",
                    parse_mode="Markdown"
                )
        except ImportError:
            await query.message.reply_text(
                f"📋 *MT5 not configured yet.*\n\n"
                f"Place manually:\n"
                f"• Ticker: `{signal['ticker']}`\n"
                f"• Direction: `{signal['direction']}`\n"
                f"• Entry: `{signal['price']:.5f}`\n"
                f"• SL: `{signal['sl']:.5f}`\n"
                f"• TP: `{signal['tp2']:.5f}`",
                parse_mode="Markdown"
            )
            storage.mark_signal(signal_id, "approved_manual")

# ─── Core scan loop ───────────────────────────────────────────────────────────

async def run_scan(app, manual=False, status_msg=None):
    tickers  = storage.get_tickers()
    if not tickers:
        return

    found    = []
    errors   = []

    for t in tickers:
        try:
            signal = await asyncio.get_event_loop().run_in_executor(
                None, scanner.analyze, t["ticker"], t["timeframe"], t["name"]
            )
            if signal:
                found.append(signal)
                await send_signal(app, signal)
        except Exception as e:
            logger.error(f"Error scanning {t['ticker']}: {e}")
            errors.append(t["ticker"])

    storage.update_last_scan()

    if manual and status_msg:
        summary = (
            f"✅ Scan complete.\n"
            f"Checked: {len(tickers)} ticker(s)\n"
            f"Signals found: {len(found)}\n"
            + (f"Errors: {', '.join(errors)}" if errors else "")
            + ("\nNo signals at this time." if not found else "")
        )
        await status_msg.edit_text(summary)

async def scheduled_scan(ctx: ContextTypes.DEFAULT_TYPE):
    await run_scan(ctx.application)

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    if not BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env file")
    if not ALLOWED_ID:
        raise ValueError("TELEGRAM_CHAT_ID not set in .env file")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("add",    cmd_add))
    app.add_handler(CommandHandler("remove", cmd_remove))
    app.add_handler(CommandHandler("list",   cmd_list))
    app.add_handler(CommandHandler("scan",   cmd_scan))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Auto-scan every 15 minutes
    app.job_queue.run_repeating(scheduled_scan, interval=900, first=60)

    logger.info("Bot started. Listening...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
