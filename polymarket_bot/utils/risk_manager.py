"""
Risk management module
"""

from typing import List, Optional, Dict
from datetime import datetime, timedelta
from ..models.position import Position, StrategyPerformance
from ..utils.logger import get_logger

logger = get_logger()


class RiskManager:
    """Risk management for the trading bot"""

    def __init__(
        self,
        max_total_exposure_usd: float = 10000,
        max_positions: int = 20,
        max_loss_per_day_usd: float = 500,
        emergency_stop_loss_pct: float = 0.1,
        max_position_size_usd: float = 1000,
        risk_per_trade: float = 0.02
    ):
        self.max_total_exposure_usd = max_total_exposure_usd
        self.max_positions = max_positions
        self.max_loss_per_day_usd = max_loss_per_day_usd
        self.emergency_stop_loss_pct = emergency_stop_loss_pct
        self.max_position_size_usd = max_position_size_usd
        self.risk_per_trade = risk_per_trade

        self.daily_pnl: List[Dict] = []
        self.total_exposure = 0.0
        self.emergency_stop_triggered = False

    def can_open_position(
        self,
        position_size_usd: float,
        current_positions: List[Position]
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a new position can be opened

        Returns:
            (can_open, reason)
        """
        # Check emergency stop
        if self.emergency_stop_triggered:
            return False, "Emergency stop triggered"

        # Check position count
        if len(current_positions) >= self.max_positions:
            return False, f"Max positions reached ({self.max_positions})"

        # Check position size
        if position_size_usd > self.max_position_size_usd:
            return False, f"Position size exceeds max ({self.max_position_size_usd})"

        # Check total exposure
        current_exposure = sum(p.cost_basis for p in current_positions)
        if current_exposure + position_size_usd > self.max_total_exposure_usd:
            return False, f"Total exposure would exceed max ({self.max_total_exposure_usd})"

        # Check daily loss limit
        today_pnl = self.get_today_pnl()
        if today_pnl < -self.max_loss_per_day_usd:
            return False, f"Daily loss limit reached ({self.max_loss_per_day_usd})"

        return True, None

    def calculate_position_size(
        self,
        account_balance: float,
        edge: float,
        risk_per_trade: Optional[float] = None
    ) -> float:
        """
        Calculate optimal position size using Kelly Criterion (simplified)

        Args:
            account_balance: Current account balance
            edge: Expected edge (e.g., 0.03 for 3%)
            risk_per_trade: Risk percentage per trade
        """
        if risk_per_trade is None:
            risk_per_trade = self.risk_per_trade

        # Simple fixed percentage risk
        position_size = account_balance * risk_per_trade

        # Cap at max position size
        position_size = min(position_size, self.max_position_size_usd)

        return position_size

    def record_pnl(self, pnl: float, strategy: str):
        """Record PnL for a closed position"""
        self.daily_pnl.append({
            'pnl': pnl,
            'strategy': strategy,
            'timestamp': datetime.now()
        })

        # Clean old records (keep only last 7 days)
        cutoff = datetime.now() - timedelta(days=7)
        self.daily_pnl = [
            record for record in self.daily_pnl
            if record['timestamp'] >= cutoff
        ]

    def get_today_pnl(self) -> float:
        """Get total PnL for today"""
        today = datetime.now().date()

        today_pnl = sum(
            record['pnl'] for record in self.daily_pnl
            if record['timestamp'].date() == today
        )

        return today_pnl

    def get_total_pnl(self) -> float:
        """Get total PnL across all recorded trades"""
        return sum(record['pnl'] for record in self.daily_pnl)

    def check_emergency_stop(self, account_balance: float, starting_balance: float):
        """
        Check if emergency stop should be triggered

        Args:
            account_balance: Current account balance
            starting_balance: Initial account balance
        """
        if starting_balance == 0:
            return

        drawdown = (starting_balance - account_balance) / starting_balance

        if drawdown >= self.emergency_stop_loss_pct:
            self.emergency_stop_triggered = True
            logger.error(
                f"EMERGENCY STOP TRIGGERED - Drawdown: {drawdown:.2%} "
                f"(Limit: {self.emergency_stop_loss_pct:.2%})"
            )

    def get_risk_metrics(self) -> Dict:
        """Get current risk metrics"""
        return {
            'total_exposure': self.total_exposure,
            'max_exposure': self.max_total_exposure_usd,
            'exposure_pct': (self.total_exposure / self.max_total_exposure_usd) * 100 if self.max_total_exposure_usd > 0 else 0,
            'today_pnl': self.get_today_pnl(),
            'total_pnl': self.get_total_pnl(),
            'daily_loss_limit': self.max_loss_per_day_usd,
            'daily_loss_remaining': self.max_loss_per_day_usd + self.get_today_pnl(),
            'emergency_stop': self.emergency_stop_triggered
        }

    def reset_emergency_stop(self):
        """Reset emergency stop (use with caution)"""
        self.emergency_stop_triggered = False
        logger.warning("Emergency stop reset")
