"""
Backtesting Engine for ICT Strategy
Simulates trading based on generated signals and calculates performance metrics
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BACKTEST_CONFIG, RISK_CONFIG
from strategies.ict_strategy import TradeSignal, SignalType


class TradeStatus(Enum):
    OPEN = "open"
    CLOSED_TP = "closed_tp"
    CLOSED_SL = "closed_sl"
    CLOSED_MANUAL = "closed_manual"


@dataclass
class Trade:
    """Represents a single trade"""
    id: int
    signal: TradeSignal
    entry_time: datetime
    entry_price: float
    position_size: float
    direction: str  # 'long' or 'short'
    stop_loss: float
    take_profit: float
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    status: TradeStatus = TradeStatus.OPEN
    pnl: float = 0.0
    pnl_percent: float = 0.0
    fees: float = 0.0


@dataclass
class BacktestResult:
    """Results from a backtest run"""
    initial_capital: float
    final_capital: float
    total_return: float
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    avg_trade_duration: float
    trades: list = field(default_factory=list)
    equity_curve: list = field(default_factory=list)


class Backtester:
    """
    Backtesting engine for trading strategies
    """

    def __init__(self, config: dict = None):
        self.config = config or BACKTEST_CONFIG
        self.risk_config = RISK_CONFIG
        self.trades: list[Trade] = []
        self.equity_curve: list[tuple[datetime, float]] = []
        self.trade_id_counter = 0

    def run(self, df: pd.DataFrame, signals: list[TradeSignal]) -> BacktestResult:
        """
        Run backtest on historical data with generated signals

        Args:
            df: DataFrame with OHLCV data
            signals: List of trade signals from strategy

        Returns:
            BacktestResult with performance metrics
        """
        capital = self.config["initial_capital"]
        position = None
        self.trades = []
        self.equity_curve = [(df["timestamp"].iloc[0], capital)]

        commission_pct = self.config["commission_percent"] / 100
        slippage_pct = self.config["slippage_percent"] / 100
        position_size_pct = self.config["position_size_percent"] / 100

        # Create a signal lookup by index for faster access
        signal_lookup = {s.index: s for s in signals}

        print(f"\nRunning backtest...")
        print(f"Initial capital: ${capital:,.2f}")
        print(f"Period: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
        print(f"Total candles: {len(df)}")
        print(f"Total signals: {len(signals)}")

        for i in range(len(df)):
            row = df.iloc[i]
            current_time = row["timestamp"]
            current_price = row["close"]
            high = row["high"]
            low = row["low"]

            # Check if we have an open position
            if position:
                # Check for stop loss hit
                if position.direction == "long":
                    if low <= position.stop_loss:
                        # Stop loss hit
                        exit_price = position.stop_loss * (1 - slippage_pct)
                        position = self._close_trade(
                            position, current_time, exit_price,
                            TradeStatus.CLOSED_SL, commission_pct
                        )
                        capital += position.pnl
                    elif high >= position.take_profit:
                        # Take profit hit
                        exit_price = position.take_profit * (1 - slippage_pct)
                        position = self._close_trade(
                            position, current_time, exit_price,
                            TradeStatus.CLOSED_TP, commission_pct
                        )
                        capital += position.pnl
                        position = None
                    else:
                        position = None  # Reset for next iteration check

                elif position.direction == "short":
                    if high >= position.stop_loss:
                        # Stop loss hit
                        exit_price = position.stop_loss * (1 + slippage_pct)
                        position = self._close_trade(
                            position, current_time, exit_price,
                            TradeStatus.CLOSED_SL, commission_pct
                        )
                        capital += position.pnl
                    elif low <= position.take_profit:
                        # Take profit hit
                        exit_price = position.take_profit * (1 + slippage_pct)
                        position = self._close_trade(
                            position, current_time, exit_price,
                            TradeStatus.CLOSED_TP, commission_pct
                        )
                        capital += position.pnl
                        position = None
                    else:
                        position = None

            # Check for new signal (only if no position)
            if position is None and i in signal_lookup:
                signal = signal_lookup[i]

                # Calculate position size
                risk_amount = capital * position_size_pct
                entry_price = signal.entry_price * (
                    1 + slippage_pct if signal.signal_type == SignalType.LONG
                    else 1 - slippage_pct
                )

                # Calculate position size based on risk
                if signal.signal_type == SignalType.LONG:
                    risk_per_unit = entry_price - signal.stop_loss
                else:
                    risk_per_unit = signal.stop_loss - entry_price

                if risk_per_unit > 0:
                    position_size = risk_amount / risk_per_unit

                    # Create new trade
                    self.trade_id_counter += 1
                    position = Trade(
                        id=self.trade_id_counter,
                        signal=signal,
                        entry_time=current_time,
                        entry_price=entry_price,
                        position_size=position_size,
                        direction="long" if signal.signal_type == SignalType.LONG else "short",
                        stop_loss=signal.stop_loss,
                        take_profit=signal.take_profit,
                        fees=entry_price * position_size * commission_pct
                    )

            # Record equity
            self.equity_curve.append((current_time, capital))

        # Close any remaining position at the end
        if position and position.status == TradeStatus.OPEN:
            final_price = df["close"].iloc[-1]
            position = self._close_trade(
                position, df["timestamp"].iloc[-1], final_price,
                TradeStatus.CLOSED_MANUAL, commission_pct
            )
            capital += position.pnl

        # Calculate results
        return self._calculate_results(capital)

    def _close_trade(
        self,
        trade: Trade,
        exit_time: datetime,
        exit_price: float,
        status: TradeStatus,
        commission_pct: float
    ) -> Trade:
        """Close a trade and calculate PnL"""
        trade.exit_time = exit_time
        trade.exit_price = exit_price
        trade.status = status

        # Calculate PnL
        if trade.direction == "long":
            trade.pnl = (exit_price - trade.entry_price) * trade.position_size
        else:
            trade.pnl = (trade.entry_price - exit_price) * trade.position_size

        # Subtract fees
        exit_fees = exit_price * trade.position_size * commission_pct
        trade.fees += exit_fees
        trade.pnl -= trade.fees

        # Calculate percentage return
        trade.pnl_percent = (trade.pnl / (trade.entry_price * trade.position_size)) * 100

        self.trades.append(trade)
        return trade

    def _calculate_results(self, final_capital: float) -> BacktestResult:
        """Calculate backtest performance metrics"""
        initial_capital = self.config["initial_capital"]

        # Basic metrics
        total_return = final_capital - initial_capital
        total_return_pct = (total_return / initial_capital) * 100

        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl <= 0]

        win_rate = len(winning_trades) / len(self.trades) * 100 if self.trades else 0

        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = abs(np.mean([t.pnl for t in losing_trades])) if losing_trades else 0

        # Profit factor
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Maximum drawdown
        equity_values = [e[1] for e in self.equity_curve]
        max_drawdown, max_drawdown_pct = self._calculate_max_drawdown(equity_values)

        # Sharpe and Sortino ratios
        returns = self._calculate_returns(equity_values)
        sharpe_ratio = self._calculate_sharpe_ratio(returns)
        sortino_ratio = self._calculate_sortino_ratio(returns)

        # Average trade duration
        durations = []
        for trade in self.trades:
            if trade.exit_time and trade.entry_time:
                duration = (trade.exit_time - trade.entry_time).total_seconds() / 3600
                durations.append(duration)
        avg_duration = np.mean(durations) if durations else 0

        return BacktestResult(
            initial_capital=initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            total_return_pct=total_return_pct,
            total_trades=len(self.trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            avg_trade_duration=avg_duration,
            trades=self.trades,
            equity_curve=self.equity_curve
        )

    def _calculate_max_drawdown(self, equity: list) -> tuple[float, float]:
        """Calculate maximum drawdown"""
        peak = equity[0]
        max_dd = 0
        max_dd_pct = 0

        for value in equity:
            if value > peak:
                peak = value
            dd = peak - value
            dd_pct = (dd / peak) * 100 if peak > 0 else 0

            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct

        return max_dd, max_dd_pct

    def _calculate_returns(self, equity: list) -> list:
        """Calculate period returns from equity curve"""
        returns = []
        for i in range(1, len(equity)):
            if equity[i - 1] > 0:
                ret = (equity[i] - equity[i - 1]) / equity[i - 1]
                returns.append(ret)
        return returns

    def _calculate_sharpe_ratio(self, returns: list, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio (annualized)"""
        if not returns or len(returns) < 2:
            return 0

        excess_returns = [r - risk_free_rate / 252 for r in returns]  # Daily risk-free rate
        mean_return = np.mean(excess_returns)
        std_return = np.std(excess_returns)

        if std_return == 0:
            return 0

        # Annualize (assuming hourly data, ~8760 hours per year)
        sharpe = (mean_return / std_return) * np.sqrt(8760)
        return sharpe

    def _calculate_sortino_ratio(self, returns: list, risk_free_rate: float = 0.02) -> float:
        """Calculate Sortino ratio (annualized)"""
        if not returns or len(returns) < 2:
            return 0

        excess_returns = [r - risk_free_rate / 252 for r in returns]
        mean_return = np.mean(excess_returns)

        # Only consider downside deviation
        negative_returns = [r for r in excess_returns if r < 0]
        if not negative_returns:
            return float('inf')

        downside_std = np.std(negative_returns)
        if downside_std == 0:
            return 0

        sortino = (mean_return / downside_std) * np.sqrt(8760)
        return sortino

    def print_results(self, result: BacktestResult):
        """Print formatted backtest results"""
        print("\n" + "=" * 60)
        print("BACKTEST RESULTS")
        print("=" * 60)

        print(f"\n{'PERFORMANCE SUMMARY':^60}")
        print("-" * 60)
        print(f"Initial Capital:      ${result.initial_capital:>15,.2f}")
        print(f"Final Capital:        ${result.final_capital:>15,.2f}")
        print(f"Total Return:         ${result.total_return:>15,.2f}")
        print(f"Total Return %:        {result.total_return_pct:>15.2f}%")

        print(f"\n{'TRADE STATISTICS':^60}")
        print("-" * 60)
        print(f"Total Trades:          {result.total_trades:>15}")
        print(f"Winning Trades:        {result.winning_trades:>15}")
        print(f"Losing Trades:         {result.losing_trades:>15}")
        print(f"Win Rate:              {result.win_rate:>15.2f}%")
        print(f"Avg Win:              ${result.avg_win:>15,.2f}")
        print(f"Avg Loss:             ${result.avg_loss:>15,.2f}")
        print(f"Profit Factor:         {result.profit_factor:>15.2f}")

        print(f"\n{'RISK METRICS':^60}")
        print("-" * 60)
        print(f"Max Drawdown:         ${result.max_drawdown:>15,.2f}")
        print(f"Max Drawdown %:        {result.max_drawdown_pct:>15.2f}%")
        print(f"Sharpe Ratio:          {result.sharpe_ratio:>15.2f}")
        print(f"Sortino Ratio:         {result.sortino_ratio:>15.2f}")

        print(f"\n{'TIMING':^60}")
        print("-" * 60)
        print(f"Avg Trade Duration:    {result.avg_trade_duration:>15.2f} hours")

        print("\n" + "=" * 60)

        # Print individual trades
        if result.trades:
            print(f"\n{'TRADE LOG (Last 10 Trades)':^60}")
            print("-" * 60)
            for trade in result.trades[-10:]:
                direction = "LONG" if trade.direction == "long" else "SHORT"
                status = trade.status.value.upper()
                print(
                    f"#{trade.id:03d} | {direction:5} | "
                    f"Entry: ${trade.entry_price:,.2f} | "
                    f"Exit: ${trade.exit_price:,.2f} | "
                    f"PnL: ${trade.pnl:+,.2f} | "
                    f"{status}"
                )


def main():
    """Test the backtester with sample data"""
    from strategies.ict_strategy import ICTStrategy, SignalType

    # Generate sample data
    dates = pd.date_range(start="2024-01-01", periods=500, freq="1h")
    np.random.seed(42)

    price = 42000
    prices = [price]
    for _ in range(499):
        change = np.random.randn() * 150
        price = max(price + change, 30000)
        prices.append(price)

    df = pd.DataFrame({
        "timestamp": dates,
        "open": prices,
        "high": [p + abs(np.random.randn() * 80) for p in prices],
        "low": [p - abs(np.random.randn() * 80) for p in prices],
        "close": [p + np.random.randn() * 50 for p in prices],
        "volume": [np.random.randint(100, 1000) for _ in prices]
    })

    # Run ICT strategy
    print("Running ICT Strategy analysis...")
    strategy = ICTStrategy()
    df_analyzed = strategy.analyze(df)

    # Generate signals
    signals = strategy.generate_signals(df_analyzed)
    print(f"Generated {len(signals)} signals")

    # Run backtest
    backtester = Backtester()
    result = backtester.run(df_analyzed, signals)

    # Print results
    backtester.print_results(result)


if __name__ == "__main__":
    main()
