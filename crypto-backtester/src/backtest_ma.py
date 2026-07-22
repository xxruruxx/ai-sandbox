import pandas as pd
from backtesting import Backtest, Strategy
from backtesting.lib import crossover

df = pd.read_csv("btc_15m_180d.csv", parse_dates=["open_time"])
df = df.rename(columns={
    "open_time": "Date", "open": "Open", "high": "High",
    "low": "Low", "close": "Close", "volume": "Volume"
})
df.set_index("Date", inplace=True)


def sma(values, n):
    return pd.Series(values).rolling(n).mean().to_numpy()


class MACrossover(Strategy):
    fast_period = 10
    slow_period = 30

    def init(self):
        self.fast_ma = self.I(sma, self.data.Close, self.fast_period)
        self.slow_ma = self.I(sma, self.data.Close, self.slow_period)

    def next(self):
        if crossover(self.fast_ma, self.slow_ma):
            if not self.position:
                self.buy()
        elif crossover(self.slow_ma, self.fast_ma):
            if self.position:
                self.position.close()


# Real prices, large cash -- quantization drag becomes negligible
# without needing FractionalBacktest at all
bt = Backtest(df, MACrossover, cash=100_000_000, commission=0.001, finalize_trades=True)
results = bt.run()

print(results)
pd.Series(results).to_csv("ma_crossover_results.csv")
bt.plot(filename="ma_crossover_plot.html", open_browser=False)
print("\nSaved: ma_crossover_results.csv, ma_crossover_plot.html")
