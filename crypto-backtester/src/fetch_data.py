import requests
import pandas as pd
import os

MAIN_CSV = "btc_15m_180d.csv"


def fetch_kraken_ohlc(pair="XBTUSD", interval=15):
    """Kraken's public OHLC endpoint -- free, no API key, not geo-blocked
    (unlike Binance, which blocks US-region IPs -- our Oracle VM is 
    hosted in Ashburn, VA, so this is a hard requirement, not a preference).
    Returns up to 720 most recent candles (7.5 days at 15m interval) --
    no historical pagination available on this endpoint."""
    url = "https://api.kraken.com/0/public/OHLC"
    params = {"pair": pair, "interval": interval}
    response = requests.get(url, params=params, timeout=15)
    data = response.json()

    if data.get("error"):
        raise Exception(f"Kraken API error: {data['error']}")

    result_key = list(data["result"].keys())[0]
    candles = data["result"][result_key]

    df = pd.DataFrame(candles, columns=[
        "time", "open", "high", "low", "close", "vwap", "volume", "count"
    ])
    df["open_time"] = pd.to_datetime(df["time"], unit="s")
    df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
    return df[["open_time", "open", "high", "low", "close", "volume"]]


def merge_and_save(new_df):
    """Append new candles onto existing history, deduping by timestamp,
    so the dataset genuinely grows over time rather than staying a
    fixed rolling window."""
    if os.path.exists(MAIN_CSV):
        existing = pd.read_csv(MAIN_CSV, parse_dates=["open_time"])
        combined = pd.concat([existing, new_df])
        combined = combined.drop_duplicates(subset="open_time", keep="last")
        combined = combined.sort_values("open_time").reset_index(drop=True)
    else:
        combined = new_df

    combined.to_csv(MAIN_CSV, index=False)
    return len(combined)


if __name__ == "__main__":
    print("Fetching latest BTC 15-minute candles from Kraken...")
    new_df = fetch_kraken_ohlc()
    print(f"Fetched {len(new_df)} recent candles (up to {new_df['open_time'].max()})")

    total = merge_and_save(new_df)
    print(f"Merged into {MAIN_CSV}: {total} total candles now stored")