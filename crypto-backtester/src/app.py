import streamlit as st
import pandas as pd
import requests
from backtesting import Backtest, Strategy
from backtesting.lib import crossover

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


def run_backtest(df, fast, slow):
    class MACrossover(Strategy):
        fast_period = fast
        slow_period = slow

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

    bt = Backtest(df, MACrossover, cash=100_000_000, commission=0.001, finalize_trades=True)
    return bt.run(), bt


def get_narration(results):
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

    facts_block = f"""Trades: {trade_count} (~{trades_per_day:.1f}/day)
Average trade duration: {avg_duration}
Win rate: {win_rate:.2f}%
Strategy return: {strategy_return:.2f}%
Buy & hold return: {buy_hold_return:.2f}%
Commissions paid: ${commissions:,.0f}
Sharpe ratio: {sharpe:.2f}"""

    if trade_count == 0:
        return facts_block, "No trades were executed with these parameters — the strategy never triggered a crossover signal in this data."

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

st.sidebar.header("Strategy Parameters")
fast = st.sidebar.slider("Fast MA period", 5, 50, 10)
slow = st.sidebar.slider("Slow MA period", 20, 100, 30)

if st.sidebar.button("Run Backtest") or "results" not in st.session_state:
    with st.spinner("Running backtest..."):
        results, bt = run_backtest(df, fast, slow)
        st.session_state["results"] = results
        st.session_state["bt"] = bt

results = st.session_state["results"]
bt = st.session_state["bt"]

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
    facts, interpretation = get_narration(results)

col_a, col_b = st.columns([1, 1.5])
with col_a:
    st.code(facts, language=None)
with col_b:
    st.write(interpretation)

with st.expander("Full stats"):
    st.dataframe(pd.Series(results).drop(['_strategy', '_equity_curve', '_trades']).astype(str))