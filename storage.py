"""
Storage
-------
Simple JSON-based persistence for watchlist and signals.
No database needed — everything lives in data/ folder.
"""

import json
import os
import uuid
from datetime import datetime, date
from typing import Optional

DATA_DIR     = os.path.join(os.path.dirname(__file__), "data")
TICKERS_FILE = os.path.join(DATA_DIR, "tickers.json")
SIGNALS_FILE = os.path.join(DATA_DIR, "signals.json")
STATE_FILE   = os.path.join(DATA_DIR, "state.json")


def _load(path: str) -> dict | list:
    if not os.path.exists(path):
        return {} if path == STATE_FILE else []
    with open(path, "r") as f:
        return json.load(f)

def _save(path: str, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


class Storage:

    # ── Watchlist ─────────────────────────────────────────────────────────────

    def get_tickers(self) -> list:
        return _load(TICKERS_FILE)

    def add_ticker(self, ticker: str, timeframe: str, name: str):
        tickers = self.get_tickers()
        # Remove existing entry for same ticker if any
        tickers = [t for t in tickers if t["ticker"] != ticker]
        tickers.append({"ticker": ticker, "timeframe": timeframe, "name": name})
        _save(TICKERS_FILE, tickers)

    def remove_ticker(self, ticker: str) -> bool:
        tickers = self.get_tickers()
        new = [t for t in tickers if t["ticker"] != ticker]
        if len(new) == len(tickers):
            return False
        _save(TICKERS_FILE, new)
        return True

    # ── Signals ───────────────────────────────────────────────────────────────

    def save_signal(self, signal: dict) -> str:
        signals = _load(SIGNALS_FILE)
        sid = str(uuid.uuid4())[:8]
        signals.append({
            "id":        sid,
            "status":    "pending",
            "timestamp": datetime.utcnow().isoformat(),
            **signal
        })
        _save(SIGNALS_FILE, signals)
        return sid

    def get_signal(self, signal_id: str) -> Optional[dict]:
        for s in _load(SIGNALS_FILE):
            if s["id"] == signal_id:
                return s
        return None

    def mark_signal(self, signal_id: str, status: str):
        signals = _load(SIGNALS_FILE)
        for s in signals:
            if s["id"] == signal_id:
                s["status"] = status
                s["updated"] = datetime.utcnow().isoformat()
                break
        _save(SIGNALS_FILE, signals)

    def get_signal_count(self) -> int:
        today = date.today().isoformat()
        return sum(
            1 for s in _load(SIGNALS_FILE)
            if s.get("timestamp", "").startswith(today)
        )

    # ── State ─────────────────────────────────────────────────────────────────

    def update_last_scan(self):
        state = _load(STATE_FILE)
        state["last_scan"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        _save(STATE_FILE, state)

    def get_last_scan(self) -> Optional[str]:
        return _load(STATE_FILE).get("last_scan")
