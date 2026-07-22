import pandas as pd
import requests

results = pd.read_csv("ma_crossover_results.csv", index_col=0).squeeze()


def build_report(results):
    trades_per_day = float(results['# Trades']) / 180
    win_rate = float(results['Win Rate [%]'])
    strategy_return = float(results['Return [%]'])
    buy_hold_return = float(results['Buy & Hold Return [%]'])
    commissions = float(results['Commissions [$]'])
    sharpe = float(results['Sharpe Ratio'])
    trade_count = int(results['# Trades'])
    avg_duration_raw = pd.Timedelta(results['Avg. Trade Duration'])
    avg_duration_hours = avg_duration_raw.total_seconds() / 3600
    avg_duration = f"{avg_duration_hours:.1f} hours"

    # Facts are pure Python formatting -- zero LLM involvement,
    # zero chance of a misquoted number
    facts_block = f"""Trades: {trade_count} (~{trades_per_day:.1f}/day)
Average trade duration: {avg_duration}
Win rate: {win_rate:.2f}%
Strategy return: {strategy_return:.2f}%
Buy & hold return: {buy_hold_return:.2f}%
Commissions paid: ${commissions:,.0f}
Sharpe ratio: {sharpe:.2f}"""

    # LLM only writes interpretation -- never reproduces a number,
    # so it can't misquote one
    prompt = f"""Given these backtest facts:
{facts_block}

In 3-4 sentences, explain what this means in plain language: did the 
strategy work, why (tie to trade frequency/commissions), and whether the 
trade count represents independent evidence or clustered/repetitive 
signals given the trades/day and average duration shown. Do not restate 
the numbers -- assume the reader can already see them. Focus only on 
interpretation."""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": "qwen2.5:3b", "prompt": prompt, "stream": False},
        timeout=120
    )
    interpretation = response.json()["response"]

    full_report = f"=== Facts ===\n{facts_block}\n\n=== Interpretation ===\n{interpretation}"
    return full_report


if __name__ == "__main__":
    report = build_report(results)
    print(report)
    with open("narration_output.txt", "w") as f:
        f.write(report)
    print("\nSaved to narration_output.txt")