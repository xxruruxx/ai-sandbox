import streamlit as st
import pandas as pd
import requests
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
import ta

st.set_page_config(page_title="Crypto Backtester", page_icon="📈", layout="wide")

st.title("Crypto Strategy Backtester")
st.caption("Real BTC data, classical strategies, AI narration that can't misquote its own numbers")


@st.cache_data
def load_data():
    df = pd.read_csv("src/btc_15m_180d.csv", parse_dates=["open_time"])
    df = df.rename(columns={
        "open_time": "Date", "open": "Open", "high": "High",
        "low": "Low", "close": "Close", "volume": "Volume"
    })
    df.set_index("Date", inplace=True)
    return df


def sma(values, n):
    return pd.Series(values).rolling(n).mean().to_numpy()


def rsi(values, n):
    return ta.momentum.RSIIndicator(pd.Series(values), window=n).rsi().to_numpy()


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
                self.position.close()   # assume only LONG position (spot)


class RSIStrategy(Strategy):
    rsi_period = 14
    oversold = 30
    overbought = 70

    def init(self):
        self.rsi = self.I(rsi, self.data.Close, self.rsi_period)

    def next(self):
        if self.rsi[-1] < self.oversold:
            if not self.position:
                self.buy()
        elif self.rsi[-1] > self.overbought:
            if self.position:
                self.position.close()


class Combined(Strategy):
    fast_period = 10
    slow_period = 30
    rsi_period = 14
    oversold = 30
    overbought = 70

    def init(self):
        self.fast_ma = self.I(sma, self.data.Close, self.fast_period)
        self.slow_ma = self.I(sma, self.data.Close, self.slow_period)
        self.rsi = self.I(rsi, self.data.Close, self.rsi_period)

    def next(self):
        # Require BOTH signals to agree -- MA trend direction AND RSI confirming
        # not-overbought/not-oversold, a stricter entry than either alone
        ma_bullish = self.fast_ma[-1] > self.slow_ma[-1]
        if ma_bullish and self.rsi[-1] < self.overbought:
            if not self.position:
                self.buy()
        elif not ma_bullish or self.rsi[-1] > self.overbought:
            if self.position:
                self.position.close()


STRATEGIES = {
    "MA Crossover": MACrossover,
    "RSI": RSIStrategy,
    "Combined (MA + RSI)": Combined,
}


def run_backtest(df, strategy_class, **params):
    for key, val in params.items():
        setattr(strategy_class, key, val)
    bt = Backtest(df, strategy_class, cash=100_000_000, commission=0.001, finalize_trades=True)
    return bt.run(), bt


def get_narration(results, strategy_name):
    trades_per_day = float(results['# Trades']) / 180 if float(results['# Trades']) > 0 else 0
    win_rate = float(results['Win Rate [%]'])
    strategy_return = float(results['Return [%]'])
    buy_hold_return = float(results['Buy & Hold Return [%]'])
    commissions = float(results['Commissions [$]'])
    sharpe = float(results['Sharpe Ratio']) if pd.notna(results['Sharpe Ratio']) else 0
    trade_count = int(results['# Trades'])

    avg_dur = results['Avg. Trade Duration']
    try:
        avg_duration_hours = pd.Timedelta(avg_dur).total_seconds() / 3600
        avg_duration = f"{avg_duration_hours:.1f} hours"
    except Exception:
        avg_duration = "N/A"

    facts_block = f"""Strategy: {strategy_name}
Trades: {trade_count} (~{trades_per_day:.1f}/day)
Average trade duration: {avg_duration}
Win rate: {win_rate:.2f}%
Strategy return: {strategy_return:.2f}%
Buy & hold return: {buy_hold_return:.2f}%
Commissions paid: ${commissions:,.0f}
Sharpe ratio: {sharpe:.2f}"""

    if trade_count == 0:
        return facts_block, "No trades were executed with these parameters."

    prompt = f"""Given these backtest facts:
{facts_block}

In 3-4 sentences, explain what this means in plain language: did the 
strategy work, why (tie to trade frequency/commissions), and whether the 
trade count represents independent evidence or clustered/repetitive 
signals given the trades/day and average duration shown. Do not restate 
the numbers -- assume the reader can already see them. Focus only on 
interpretation."""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "qwen2.5:3b", "prompt": prompt, "stream": False},
            timeout=60
        )
        interpretation = response.json()["response"]
    except Exception as e:
        interpretation = f"(AI narration unavailable: {e})"

    return facts_block, interpretation


df = load_data()

st.sidebar.header("Strategy")
strategy_name = st.sidebar.selectbox("Choose strategy", list(STRATEGIES.keys()))

st.sidebar.header("Parameters")
params = {}
if strategy_name in ["MA Crossover", "Combined (MA + RSI)"]:
    params["fast_period"] = st.sidebar.slider("Fast MA period", 5, 50, 10)
    params["slow_period"] = st.sidebar.slider("Slow MA period", 20, 100, 30)
if strategy_name in ["RSI", "Combined (MA + RSI)"]:
    params["rsi_period"] = st.sidebar.slider("RSI period", 5, 30, 14)
    params["oversold"] = st.sidebar.slider("Oversold threshold", 10, 40, 30)
    params["overbought"] = st.sidebar.slider("Overbought threshold", 60, 90, 70)

run_clicked = st.sidebar.button("Run Backtest")

if run_clicked or "results" not in st.session_state:
    with st.spinner("Running backtest..."):
        strategy_class = STRATEGIES[strategy_name]
        results, bt = run_backtest(df, strategy_class, **params)
        st.session_state["results"] = results
        st.session_state["bt"] = bt
        st.session_state["strategy_name"] = strategy_name

results = st.session_state["results"]
bt = st.session_state["bt"]
active_strategy = st.session_state.get("strategy_name", strategy_name)

st.subheader(f"Results — {active_strategy}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Return", f"{float(results['Return [%]']):.2f}%")
col2.metric("Buy & Hold", f"{float(results['Buy & Hold Return [%]']):.2f}%")
col3.metric("Win Rate", f"{float(results['Win Rate [%]']):.2f}%")
col4.metric("Trades", int(results['# Trades']))

st.subheader("Equity Curve")
equity_curve = results['_equity_curve']
st.line_chart(equity_curve['Equity'])

st.subheader("AI Interpretation")
with st.spinner("Generating narration..."):
    facts, interpretation = get_narration(results, active_strategy)

col_a, col_b = st.columns([1, 1.5])
with col_a:
    st.code(facts, language=None)
with col_b:
    st.write(interpretation)

with st.expander("Full stats"):
    st.dataframe(pd.Series(results).drop(['_strategy', '_equity_curve', '_trades']).astype(str))