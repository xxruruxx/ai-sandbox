import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

def fetch_binance_klines(symbol="BTCUSDT", interval="15m", days_back=180):
    url = "https://api.binance.com/api/v3/klines"
    end_time = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_time = int((datetime.now(timezone.utc) - timedelta(days=days_back)).timestamp()*1000)

    all_candles = []
    current_start = start_time

    while current_start < end_time:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current_start,
            "limit": 1000
        }
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        if not data:
            break
        all_candles.extend(data)
        current_start = data[-1][6] + 1
        print(f"    Fetched {len(all_candles)} candles so far...")

    df = pd.DataFrame(all_candles, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ])
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
    return df[["open_time", "open", "high", "low", "close", "volume"]]

if __name__ == "__main__":
    print("Fetching BTC 15-minute candles, last 180 days...")
    df = fetch_binance_klines("BTCUSDT", "15m", 180)
    df.to_csv("btc_15m_180d.csv", index=False)
    print(f"\nSaved {len(df)} candles to btc_15m_180d.csv")
    print(df.head())
    print(df.tail())

