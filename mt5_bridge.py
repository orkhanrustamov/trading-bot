"""
MT5 Bridge
----------
Optional module for executing trades on MetaTrader 5 via MetaAPI.
https://metaapi.cloud  (free tier: 5 accounts, 10 req/sec)

To enable:
1. Sign up at metaapi.cloud
2. Add MT5 account → get ACCOUNT_ID
3. Set META_API_TOKEN and META_API_ACCOUNT_ID in .env

If not configured, the bot still works — it just shows
order details for manual placement.
"""

import os
import requests
from typing import Optional

META_API_TOKEN      = os.getenv("META_API_TOKEN", "")
META_API_ACCOUNT_ID = os.getenv("META_API_ACCOUNT_ID", "")
BASE_URL            = "https://mt-client-api-v1.london.agiliumtrade.ai"

# FX pip sizes for SL/TP distance calculation
PIP_SIZES = {
    "default":  0.00001,   # most FX pairs
    "JPY":      0.001,     # JPY pairs
    "XAU":      0.01,      # Gold
    "XAG":      0.001,     # Silver
    "CL=F":     0.01,      # Oil
    "GC=F":     0.10,      # Gold futures
}


def _headers() -> dict:
    return {
        "Content-Type":  "application/json",
        "auth-token":    META_API_TOKEN,
    }


def _symbol_for_mt5(ticker: str) -> str:
    """Convert Yahoo Finance ticker to MT5 symbol format."""
    conversions = {
        "EURUSD=X": "EURUSD",
        "GBPUSD=X": "GBPUSD",
        "USDJPY=X": "USDJPY",
        "AUDUSD=X": "AUDUSD",
        "USDCAD=X": "USDCAD",
        "USDCHF=X": "USDCHF",
        "NZDUSD=X": "NZDUSD",
        "EURGBP=X": "EURGBP",
        "EURJPY=X": "EURJPY",
        "GBPJPY=X": "GBPJPY",
        "GC=F":     "XAUUSD",
        "CL=F":     "USOIL",
        "SI=F":     "XAGUSD",
        "SPY":      "SPY",
        "QQQ":      "QQQ",
        "GLD":      "GLD",
    }
    return conversions.get(ticker, ticker.replace("=X", "").replace("=F", ""))


def _lot_size(signal: dict) -> float:
    """
    Default 0.01 micro lot — safe starting size.
    Override this with your own risk management logic.
    """
    return 0.01


def place_order(signal: dict) -> dict:
    """
    Place a market order on MT5 via MetaAPI REST.
    Returns dict with success, ticket, or error.
    """
    if not META_API_TOKEN or not META_API_ACCOUNT_ID:
        return {
            "success": False,
            "error":   "MetaAPI not configured. Set META_API_TOKEN and META_API_ACCOUNT_ID in .env"
        }

    symbol    = _symbol_for_mt5(signal["ticker"])
    direction = signal["direction"]   # BUY or SELL
    sl        = round(signal["sl"],  5)
    tp        = round(signal["tp2"], 5)   # 1:2 TP
    lots      = _lot_size(signal)

    payload = {
        "actionType": "ORDER_TYPE_BUY" if direction == "BUY" else "ORDER_TYPE_SELL",
        "symbol":     symbol,
        "volume":     lots,
        "stopLoss":   sl,
        "takeProfit": tp,
        "comment":    f"SMC+Fib {signal['timeframe']} {signal['fib']}",
    }

    try:
        url = f"{BASE_URL}/users/current/accounts/{META_API_ACCOUNT_ID}/trade"
        r   = requests.post(url, json=payload, headers=_headers(), timeout=15)
        r.raise_for_status()
        data = r.json()
        return {
            "success": True,
            "ticket":  data.get("orderId", data.get("positionId", "unknown")),
        }
    except requests.exceptions.HTTPError as e:
        try:
            msg = e.response.json().get("message", str(e))
        except Exception:
            msg = str(e)
        return {"success": False, "error": msg}
    except Exception as e:
        return {"success": False, "error": str(e)}
