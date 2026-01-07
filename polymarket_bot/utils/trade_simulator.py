"""
Trade Simulator for Testing Mode

Logs all potential trades without executing them, then tracks actual outcomes
to verify strategy profitability over time.
"""

import json
import time
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
from ..utils.logger import get_logger

logger = get_logger()


class SimulatedTradeStatus(Enum):
    PENDING = "PENDING"  # Trade logged, waiting for outcome
    MONITORING = "MONITORING"  # Monitoring market for outcome
    RESOLVED = "RESOLVED"  # Market resolved, PnL calculated
    EXPIRED = "EXPIRED"  # Market expired without resolution
    CANCELLED = "CANCELLED"  # Would have been cancelled


@dataclass
class SimulatedTrade:
    """Represents a simulated trade"""
    trade_id: str
    strategy: str
    market_id: str
    token_id: str
    side: str  # BUY or SELL
    entry_price: float
    amount: float
    timestamp: float
    status: SimulatedTradeStatus

    # Market info
    market_question: str
    outcome: str

    # Strategy context
    edge: float
    confidence: float
    metadata: Dict

    # Exit info (filled when resolved)
    exit_price: Optional[float] = None
    exit_timestamp: Optional[float] = None
    resolution_outcome: Optional[str] = None

    # PnL calculation
    gross_pnl: float = 0.0
    fees: float = 0.0
    net_pnl: float = 0.0
    roi_pct: float = 0.0

    # Performance tracking
    holding_time_seconds: Optional[float] = None
    would_have_exited: bool = False
    exit_reason: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['status'] = self.status.value
        data['timestamp'] = self.timestamp
        data['exit_timestamp'] = self.exit_timestamp
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'SimulatedTrade':
        """Create from dictionary"""
        data['status'] = SimulatedTradeStatus(data['status'])
        return cls(**data)


class TradeSimulator:
    """
    Simulates trades without executing them

    Tracks what would have happened if trades were executed,
    monitors actual outcomes, and calculates hypothetical PnL
    """

    def __init__(self, output_dir: str = "simulation_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.simulated_trades: List[SimulatedTrade] = []
        self.session_id = f"sim_{int(time.time())}"
        self.session_file = self.output_dir / f"{self.session_id}.jsonl"

        # Performance tracking
        self.total_trades = 0
        self.resolved_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0

        logger.info(f"🧪 Testing Mode Active - Simulation session: {self.session_id}")
        logger.info(f"📊 Results will be saved to: {self.session_file}")

    def log_trade(
        self,
        strategy: str,
        market_id: str,
        token_id: str,
        side: str,
        entry_price: float,
        amount: float,
        market_question: str,
        outcome: str,
        edge: float,
        confidence: float,
        metadata: Dict = None
    ) -> SimulatedTrade:
        """
        Log a potential trade without executing it

        Args:
            strategy: Strategy name
            market_id: Market condition ID
            token_id: Token ID
            side: BUY or SELL
            entry_price: Entry price
            amount: Position size
            market_question: Market question text
            outcome: Predicted outcome
            edge: Calculated edge
            confidence: Confidence level
            metadata: Additional metadata

        Returns:
            SimulatedTrade object
        """
        trade_id = f"{strategy}_{int(time.time() * 1000)}"

        trade = SimulatedTrade(
            trade_id=trade_id,
            strategy=strategy,
            market_id=market_id,
            token_id=token_id,
            side=side,
            entry_price=entry_price,
            amount=amount,
            timestamp=time.time(),
            status=SimulatedTradeStatus.PENDING,
            market_question=market_question,
            outcome=outcome,
            edge=edge,
            confidence=confidence,
            metadata=metadata or {}
        )

        self.simulated_trades.append(trade)
        self.total_trades += 1

        # Log to file immediately
        self._write_trade_to_file(trade)

        logger.info(
            f"📝 SIMULATED TRADE: {strategy} - {side} {outcome} @ {entry_price:.3f} "
            f"(Edge: {edge:.2%}, Amount: ${amount * entry_price:.2f})"
        )
        logger.info(f"   Market: {market_question[:80]}")

        return trade

    def update_trade_exit(
        self,
        trade: SimulatedTrade,
        exit_price: float,
        exit_reason: str
    ):
        """
        Update a trade with exit information (when it would have been closed)

        Args:
            trade: SimulatedTrade object
            exit_price: Price at which position would have exited
            exit_reason: Reason for exit
        """
        trade.would_have_exited = True
        trade.exit_price = exit_price
        trade.exit_timestamp = time.time()
        trade.exit_reason = exit_reason
        trade.status = SimulatedTradeStatus.MONITORING

        # Calculate holding time
        trade.holding_time_seconds = trade.exit_timestamp - trade.timestamp

        # Calculate PnL (preliminary - will be updated on resolution)
        cost_basis = trade.entry_price * trade.amount

        if trade.side == "BUY":
            trade.gross_pnl = (exit_price - trade.entry_price) * trade.amount
        else:
            trade.gross_pnl = (trade.entry_price - exit_price) * trade.amount

        # Estimate fees (2% on winning positions)
        if trade.gross_pnl > 0:
            trade.fees = trade.gross_pnl * 0.02

        trade.net_pnl = trade.gross_pnl - trade.fees
        trade.roi_pct = (trade.net_pnl / cost_basis) * 100 if cost_basis > 0 else 0

        self._write_trade_to_file(trade)

        logger.info(
            f"📤 SIMULATED EXIT: {trade.trade_id} - {exit_reason} @ {exit_price:.3f} "
            f"(PnL: ${trade.net_pnl:.2f}, ROI: {trade.roi_pct:+.2f}%)"
        )

    def resolve_trade(
        self,
        trade: SimulatedTrade,
        actual_outcome: str,
        final_price: float
    ):
        """
        Resolve a trade based on actual market outcome

        Args:
            trade: SimulatedTrade object
            actual_outcome: Actual outcome (YES/NO or specific outcome)
            final_price: Final settlement price (0 or 1 typically)
        """
        trade.status = SimulatedTradeStatus.RESOLVED
        trade.resolution_outcome = actual_outcome

        # Calculate actual PnL based on resolution
        cost_basis = trade.entry_price * trade.amount

        if trade.side == "BUY":
            # If we bought and it resolved to our outcome, we win
            gross_value = final_price * trade.amount
            trade.gross_pnl = gross_value - cost_basis
        else:
            # If we sold, inverse logic
            gross_value = (1 - final_price) * trade.amount
            trade.gross_pnl = gross_value - cost_basis

        # Calculate fees (2% on winners)
        if trade.gross_pnl > 0:
            trade.fees = gross_value * 0.02
        else:
            trade.fees = 0

        trade.net_pnl = trade.gross_pnl - trade.fees
        trade.roi_pct = (trade.net_pnl / cost_basis) * 100 if cost_basis > 0 else 0

        # Update statistics
        self.resolved_trades += 1
        self.total_pnl += trade.net_pnl

        if trade.net_pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1

        self._write_trade_to_file(trade)

        logger.info(
            f"✅ TRADE RESOLVED: {trade.trade_id} - Outcome: {actual_outcome} "
            f"(PnL: ${trade.net_pnl:.2f}, ROI: {trade.roi_pct:+.2f}%)"
        )

    def _write_trade_to_file(self, trade: SimulatedTrade):
        """Write trade to JSONL file"""
        with open(self.session_file, 'a') as f:
            f.write(json.dumps(trade.to_dict()) + '\n')

    def get_pending_trades(self) -> List[SimulatedTrade]:
        """Get all pending trades"""
        return [t for t in self.simulated_trades if t.status == SimulatedTradeStatus.PENDING]

    def get_monitoring_trades(self) -> List[SimulatedTrade]:
        """Get all trades being monitored"""
        return [t for t in self.simulated_trades if t.status == SimulatedTradeStatus.MONITORING]

    def get_statistics(self) -> Dict:
        """Get current simulation statistics"""
        win_rate = (self.winning_trades / self.resolved_trades * 100) if self.resolved_trades > 0 else 0
        avg_pnl = self.total_pnl / self.resolved_trades if self.resolved_trades > 0 else 0

        return {
            'session_id': self.session_id,
            'total_trades': self.total_trades,
            'pending_trades': len(self.get_pending_trades()),
            'monitoring_trades': len(self.get_monitoring_trades()),
            'resolved_trades': self.resolved_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'total_pnl': self.total_pnl,
            'avg_pnl_per_trade': avg_pnl
        }

    def generate_report(self) -> str:
        """Generate a detailed performance report"""
        stats = self.get_statistics()

        report = []
        report.append("\n" + "=" * 70)
        report.append("SIMULATION PERFORMANCE REPORT")
        report.append("=" * 70)
        report.append(f"Session ID: {stats['session_id']}")
        report.append(f"Duration: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        report.append("Overall Statistics:")
        report.append(f"  Total Simulated Trades: {stats['total_trades']}")
        report.append(f"  Resolved Trades: {stats['resolved_trades']}")
        report.append(f"  Pending/Monitoring: {stats['pending_trades'] + stats['monitoring_trades']}")
        report.append("")
        report.append(f"  Winning Trades: {stats['winning_trades']}")
        report.append(f"  Losing Trades: {stats['losing_trades']}")
        report.append(f"  Win Rate: {stats['win_rate']:.2f}%")
        report.append("")
        report.append(f"  Total PnL: ${stats['total_pnl']:.2f}")
        report.append(f"  Average PnL/Trade: ${stats['avg_pnl_per_trade']:.2f}")
        report.append("")

        # Strategy breakdown
        strategy_stats = {}
        for trade in self.simulated_trades:
            if trade.status == SimulatedTradeStatus.RESOLVED:
                if trade.strategy not in strategy_stats:
                    strategy_stats[trade.strategy] = {
                        'trades': 0,
                        'wins': 0,
                        'losses': 0,
                        'total_pnl': 0.0
                    }

                strategy_stats[trade.strategy]['trades'] += 1
                strategy_stats[trade.strategy]['total_pnl'] += trade.net_pnl

                if trade.net_pnl > 0:
                    strategy_stats[trade.strategy]['wins'] += 1
                else:
                    strategy_stats[trade.strategy]['losses'] += 1

        if strategy_stats:
            report.append("Strategy Performance:")
            for strategy, stats in strategy_stats.items():
                win_rate = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0
                report.append(f"\n  {strategy}:")
                report.append(f"    Trades: {stats['trades']}")
                report.append(f"    Win Rate: {win_rate:.2f}%")
                report.append(f"    Total PnL: ${stats['total_pnl']:.2f}")

        report.append("")
        report.append("=" * 70)

        return "\n".join(report)

    def save_final_report(self):
        """Save final report to file"""
        report = self.generate_report()

        report_file = self.output_dir / f"{self.session_id}_report.txt"
        with open(report_file, 'w') as f:
            f.write(report)

        logger.info(f"\n📊 Final report saved to: {report_file}")
        logger.info(report)

    def export_to_csv(self):
        """Export all trades to CSV for analysis"""
        import csv

        csv_file = self.output_dir / f"{self.session_id}_trades.csv"

        with open(csv_file, 'w', newline='') as f:
            if not self.simulated_trades:
                return

            # Get fieldnames from first trade
            fieldnames = list(self.simulated_trades[0].to_dict().keys())

            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for trade in self.simulated_trades:
                writer.writerow(trade.to_dict())

        logger.info(f"📈 Trades exported to CSV: {csv_file}")
