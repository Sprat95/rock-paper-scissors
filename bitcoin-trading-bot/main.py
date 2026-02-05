#!/usr/bin/env python3
"""
Bitcoin Trading Bot - ICT Strategy Backtester
Main entry point for fetching data and running backtests
"""

import argparse
import sys
import os

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import BACKTEST_CONFIG, TRADING_CONFIG
from fetchers.binance_fetcher import BinanceFetcher
from strategies.ict_strategy import ICTStrategy
from backtest.backtester import Backtester


def run_backtest(
    symbol: str = None,
    timeframe: str = None,
    start_date: str = None,
    end_date: str = None,
    verbose: bool = True
):
    """
    Run a complete backtest workflow:
    1. Fetch historical data from Binance
    2. Run ICT strategy analysis
    3. Generate trading signals
    4. Execute backtest
    5. Display results
    """
    # Use defaults from config if not provided
    symbol = symbol or TRADING_CONFIG["symbol"]
    timeframe = timeframe or TRADING_CONFIG["primary_timeframe"]
    start_date = start_date or BACKTEST_CONFIG["start_date"]
    end_date = end_date or BACKTEST_CONFIG["end_date"]

    print("=" * 60)
    print("BITCOIN TRADING BOT - ICT STRATEGY BACKTESTER")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Symbol:     {symbol}")
    print(f"  Timeframe:  {timeframe}")
    print(f"  Period:     {start_date} to {end_date}")
    print(f"  Capital:    ${BACKTEST_CONFIG['initial_capital']:,.2f}")
    print(f"  Risk/Trade: {BACKTEST_CONFIG['position_size_percent']}%")

    # Step 1: Fetch historical data
    print("\n" + "-" * 60)
    print("STEP 1: Fetching Historical Data from Binance")
    print("-" * 60)

    try:
        fetcher = BinanceFetcher()
        df = fetcher.fetch_klines(
            symbol=symbol,
            interval=timeframe,
            start_date=start_date,
            end_date=end_date
        )
        print(f"Fetched {len(df)} candles")
        print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    except Exception as e:
        print(f"Error fetching data: {e}")
        print("\nTip: Make sure you have internet connection and Binance API is accessible.")
        return None

    if df.empty:
        print("No data fetched. Check your date range and symbol.")
        return None

    # Step 2: Run ICT Strategy Analysis
    print("\n" + "-" * 60)
    print("STEP 2: Running ICT Strategy Analysis")
    print("-" * 60)

    strategy = ICTStrategy()
    df_analyzed = strategy.analyze(df)

    summary = strategy.get_analysis_summary(df_analyzed)
    print("\nICT Analysis Summary:")
    print(f"  Bullish FVGs:     {summary['bullish_fvgs']}")
    print(f"  Bearish FVGs:     {summary['bearish_fvgs']}")
    print(f"  Bullish OBs:      {summary['bullish_obs']}")
    print(f"  Bearish OBs:      {summary['bearish_obs']}")
    print(f"  Liquidity Levels: {summary['liquidity_levels']}")
    print(f"  Swept Levels:     {summary['swept_levels']}")
    print(f"  BOS Count:        {summary['bos_count']}")
    print(f"  CHoCH Count:      {summary['choch_count']}")
    print(f"  Current Bias:     {summary['current_bias']}")

    # Step 3: Generate Trading Signals
    print("\n" + "-" * 60)
    print("STEP 3: Generating Trading Signals")
    print("-" * 60)

    signals = strategy.generate_signals(df_analyzed)
    print(f"Generated {len(signals)} trading signals")

    if verbose and signals:
        print("\nSample Signals (first 5):")
        for signal in signals[:5]:
            direction = signal.signal_type.value.upper()
            print(f"  [{signal.timestamp}] {direction}: Entry=${signal.entry_price:.2f}, "
                  f"SL=${signal.stop_loss:.2f}, TP=${signal.take_profit:.2f} "
                  f"(Conf: {signal.confidence:.0%})")

    if not signals:
        print("\nNo trading signals generated. Try adjusting strategy parameters.")
        return None

    # Step 4: Run Backtest
    print("\n" + "-" * 60)
    print("STEP 4: Running Backtest")
    print("-" * 60)

    backtester = Backtester()
    result = backtester.run(df_analyzed, signals)

    # Step 5: Display Results
    backtester.print_results(result)

    return result


def analyze_only(
    symbol: str = None,
    timeframe: str = None,
    start_date: str = None,
    end_date: str = None
):
    """
    Run ICT analysis without backtesting
    Useful for understanding market structure
    """
    symbol = symbol or TRADING_CONFIG["symbol"]
    timeframe = timeframe or TRADING_CONFIG["primary_timeframe"]
    start_date = start_date or BACKTEST_CONFIG["start_date"]
    end_date = end_date or BACKTEST_CONFIG["end_date"]

    print("=" * 60)
    print("ICT MARKET ANALYSIS")
    print("=" * 60)

    # Fetch data
    fetcher = BinanceFetcher()
    df = fetcher.fetch_klines(
        symbol=symbol,
        interval=timeframe,
        start_date=start_date,
        end_date=end_date
    )

    # Run analysis
    strategy = ICTStrategy()
    df_analyzed = strategy.analyze(df)

    # Print detailed analysis
    summary = strategy.get_analysis_summary(df_analyzed)

    print(f"\n{'MARKET STRUCTURE ANALYSIS':^60}")
    print("-" * 60)
    for key, value in summary.items():
        print(f"  {key.replace('_', ' ').title():30} {value}")

    # Print recent FVGs
    print(f"\n{'RECENT FAIR VALUE GAPS':^60}")
    print("-" * 60)
    for fvg in strategy.fvg_list[-10:]:
        status = "FILLED" if fvg.filled else "ACTIVE"
        print(f"  [{fvg.timestamp}] {fvg.type.upper():7} | "
              f"Range: ${fvg.bottom:.2f} - ${fvg.top:.2f} | {status}")

    # Print recent Order Blocks
    print(f"\n{'RECENT ORDER BLOCKS':^60}")
    print("-" * 60)
    for ob in strategy.order_blocks[-10:]:
        status = "MITIGATED" if ob.mitigated else "ACTIVE"
        print(f"  [{ob.timestamp}] {ob.type.upper():7} | "
              f"Range: ${ob.low:.2f} - ${ob.high:.2f} | {status}")

    return df_analyzed


def main():
    """Main entry point with CLI argument parsing"""
    parser = argparse.ArgumentParser(
        description="Bitcoin Trading Bot - ICT Strategy Backtester",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                              # Run with default settings
  python main.py --symbol ETHUSDT             # Test on Ethereum
  python main.py --timeframe 4h               # Use 4-hour candles
  python main.py --start 2024-01-01 --end 2024-06-30  # Custom date range
  python main.py --analyze                    # Analysis only (no backtest)
        """
    )

    parser.add_argument(
        "--symbol", "-s",
        type=str,
        default=TRADING_CONFIG["symbol"],
        help=f"Trading pair (default: {TRADING_CONFIG['symbol']})"
    )

    parser.add_argument(
        "--timeframe", "-t",
        type=str,
        default=TRADING_CONFIG["primary_timeframe"],
        choices=["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"],
        help=f"Candle timeframe (default: {TRADING_CONFIG['primary_timeframe']})"
    )

    parser.add_argument(
        "--start", "-S",
        type=str,
        default=BACKTEST_CONFIG["start_date"],
        help=f"Start date YYYY-MM-DD (default: {BACKTEST_CONFIG['start_date']})"
    )

    parser.add_argument(
        "--end", "-E",
        type=str,
        default=BACKTEST_CONFIG["end_date"],
        help=f"End date YYYY-MM-DD (default: {BACKTEST_CONFIG['end_date']})"
    )

    parser.add_argument(
        "--analyze", "-a",
        action="store_true",
        help="Run analysis only (no backtest)"
    )

    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Reduce output verbosity"
    )

    args = parser.parse_args()

    try:
        if args.analyze:
            analyze_only(
                symbol=args.symbol,
                timeframe=args.timeframe,
                start_date=args.start,
                end_date=args.end
            )
        else:
            run_backtest(
                symbol=args.symbol,
                timeframe=args.timeframe,
                start_date=args.start,
                end_date=args.end,
                verbose=not args.quiet
            )
    except KeyboardInterrupt:
        print("\n\nBacktest interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
