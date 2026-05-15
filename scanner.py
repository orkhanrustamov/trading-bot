import yfinance as yf
import pandas as pd
import numpy as np

TF_PARAMS = {
    "15m": {"period": "5d",  "interval": "15m"},
    "30m": {"period": "10d", "interval": "30m"},
    "1h":  {"period": "30d", "interval": "1h"},
    "4h":  {"period": "60d", "interval": "1h"},
    "1d":  {"period": "1y",  "interval": "1d"},
}
ATR_PERIOD = 14

class Scanner:
    def validate_ticker(self, ticker):
        return True, ticker

    def analyze(self, ticker, timeframe, name):
        df = self._fetch(ticker, timeframe)
        if df is None or len(df) < 30:
            return None
        atr   = self._atr(df)
        trend = self._smc_trend(df)
        fib   = self._autofib(df)
        ob    = self._order_block(df, trend)
        price = float(df["Close"].iloc[-1])
        return self._evaluate(ticker, name, timeframe, price, atr, trend, fib, ob)

    def _fetch(self, ticker, timeframe):
        params = TF_PARAMS.get(timeframe, TF_PARAMS["1h"])
        try:
            df = yf.download(ticker, period=params["period"], interval=params["interval"], progress=False, auto_adjust=True)
            if df.empty:
                return None
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df[["Open","High","Low","Close","Volume"]].dropna()
            if timeframe == "4h":
                df = df.resample("4h").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()
            return df
        except:
            return None

    def _atr(self, df):
        h, l, c = df["High"], df["Low"], df["Close"]
        tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
        return float(tr.rolling(ATR_PERIOD).mean().iloc[-1])

    def _smc_trend(self, df):
        # Use EMA cross for reliable trend detection
        close = df["Close"]
        ema20 = close.ewm(span=20).mean()
        ema50 = close.ewm(span=50).mean()
        current_close = float(close.iloc[-1])
        current_20    = float(ema20.iloc[-1])
        current_50    = float(ema50.iloc[-1])
        prev_20       = float(ema20.iloc[-2])
        prev_50       = float(ema50.iloc[-2])

        # Bullish: EMA20 crossed above EMA50
        if prev_20 <= prev_50 and current_20 > current_50:
            return 1
        # Bearish: EMA20 crossed below EMA50
        if prev_20 >= prev_50 and current_20 < current_50:
            return -1
        # Strong trend already in place
        if current_20 > current_50 and current_close > current_20:
            return 1
        if current_20 < current_50 and current_close < current_20:
            return -1
        return 0

    def _autofib(self, df, length=100):
        window = df.tail(length)
        h = float(window["High"].max())
        l = float(window["Low"].min())
        span = h - l if h != l else 1
        current = float(df["Close"].iloc[-1])
        # Calculate fib retracement from top
        retrace = (h - current) / span
        fib_levels = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
        nearest = min(fib_levels, key=lambda f: abs(f - retrace))
        at_key_level = nearest in {0.382, 0.5, 0.618, 0.786} and abs(nearest - retrace) < 0.08
        return {
            "nearest": nearest,
            "at_key_level": at_key_level,
            "retrace": retrace,
            "high": h,
            "low": l
        }

    def _order_block(self, df, trend):
        n = len(df)
        opens  = df["Open"].values
        closes = df["Close"].values
        highs  = df["High"].values
        lows   = df["Low"].values
        for i in range(n-3, max(20,n-30), -1):
            if trend == 1 and closes[i] < opens[i]:
                if all(closes[j] > opens[j] for j in range(i+1, min(i+4,n))):
                    return {"high": highs[i], "low": lows[i]}
            elif trend == -1 and closes[i] > opens[i]:
                if all(closes[j] < opens[j] for j in range(i+1, min(i+4,n))):
                    return {"high": highs[i], "low": lows[i]}
        return None

    def _evaluate(self, ticker, name, timeframe, price, atr, trend, fib, ob):
        # Must have a trend
        if trend == 0:
            return None

        direction = "BUY" if trend == 1 else "SELL"
        reasons   = []
        strength  = 1

        if trend == 1:
            reasons.append("Bullish trend — EMA20 above EMA50")
        else:
            reasons.append("Bearish trend — EMA20 below EMA50")

        # Bonus: fib confluence
        if fib["at_key_level"]:
            pct = int(fib["nearest"] * 1000) / 10
            reasons.append(f"AutoFib: price near {pct}% retracement level")
            strength += 1

        # Bonus: order block
        if ob:
            reasons.append(f"Order block zone detected ({'support' if trend==1 else 'resistance'})")
            strength = min(3, strength + 1)

        # SL / TP at 1:2
        if direction == "BUY":
            sl  = price - (atr * 1.5)
            tp1 = price + (price - sl)
            tp2 = price + (price - sl) * 2
        else:
            sl  = price + (atr * 1.5)
            tp1 = price - (sl - price)
            tp2 = price - (sl - price) * 2

        return {
            "ticker":    ticker,
            "name":      name,
            "timeframe": timeframe,
            "direction": direction,
            "price":     price,
            "sl":        sl,
            "tp1":       tp1,
            "tp2":       tp2,
            "atr":       atr,
            "strength":  strength,
            "reasons":   reasons,
            "fib":       fib["nearest"],
            "trend":     trend,
        }
