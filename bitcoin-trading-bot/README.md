# Bitcoin Trading Bot - ICT Strategy Backtester

A backtesting framework for Bitcoin trading using Inner Circle Trader (ICT) concepts on Binance.

## Features

- **Data Fetching**: Automated historical OHLCV data retrieval from Binance API
- **ICT Strategy Implementation**:
  - Fair Value Gaps (FVG)
  - Order Blocks (OB)
  - Liquidity Sweeps
  - Market Structure (BOS, CHoCH)
  - Kill Zones (Asian, London, New York sessions)
- **Backtesting Engine**: Full simulation with commission, slippage, and risk management
- **Performance Metrics**: Win rate, profit factor, Sharpe ratio, max drawdown, and more

## Installation

```bash
cd bitcoin-trading-bot
pip install -r requirements.txt
```

## Quick Start

### Run Backtest with Default Settings
```bash
python main.py
```

### Custom Configuration
```bash
# Different trading pair
python main.py --symbol ETHUSDT

# Different timeframe
python main.py --timeframe 4h

# Custom date range
python main.py --start 2024-01-01 --end 2024-06-30

# Analysis only (no backtest)
python main.py --analyze
```

## Configuration

Edit `config.py` to customize:

- **Trading Parameters**: Symbol, timeframes
- **ICT Settings**: FVG thresholds, order block detection, liquidity settings
- **Backtest Settings**: Initial capital, position sizing, commission rates
- **Risk Management**: Risk/reward ratios, max drawdown limits

## Project Structure

```
bitcoin-trading-bot/
├── main.py              # Main entry point
├── config.py            # Configuration settings
├── requirements.txt     # Dependencies
├── data/
│   └── binance_fetcher.py    # Binance API data fetcher
├── strategies/
│   └── ict_strategy.py       # ICT strategy implementation
├── backtest/
│   └── backtester.py         # Backtesting engine
└── utils/
```

## ICT Concepts Implemented

### Fair Value Gaps (FVG)
Imbalances in price where the market moved too quickly, leaving gaps that price often returns to fill.

### Order Blocks (OB)
The last candle before a significant move, representing institutional order flow.

### Liquidity Sweeps
Areas where stop losses cluster (above swing highs / below swing lows) that institutions target.

### Market Structure
- **Break of Structure (BOS)**: Continuation of trend
- **Change of Character (CHoCH)**: Potential reversal signal

### Kill Zones
Optimal trading times when institutional activity is highest:
- Asian: 00:00-08:00 UTC
- London: 07:00-16:00 UTC
- New York: 12:00-21:00 UTC

## Output Example

```
============================================================
BACKTEST RESULTS
============================================================

               PERFORMANCE SUMMARY
------------------------------------------------------------
Initial Capital:      $     10,000.00
Final Capital:        $     12,450.00
Total Return:         $      2,450.00
Total Return %:               24.50%

               TRADE STATISTICS
------------------------------------------------------------
Total Trades:                      45
Winning Trades:                    28
Losing Trades:                     17
Win Rate:                       62.22%
Profit Factor:                   1.85
```

## Disclaimer

This software is for educational and research purposes only. Trading cryptocurrencies involves significant risk. Past performance does not guarantee future results. Always do your own research and never trade with money you cannot afford to lose.
