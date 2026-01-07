"""
Base strategy class
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, List, TYPE_CHECKING
from datetime import datetime
from ..models.position import Position, StrategyPerformance
from ..clients.polymarket_client import PolymarketClient
from ..utils.logger import get_logger

if TYPE_CHECKING:
    from ..utils.trade_simulator import TradeSimulator

logger = get_logger()


class BaseStrategy(ABC):
    """Base class for all trading strategies"""

    def __init__(
        self,
        name: str,
        polymarket_client: PolymarketClient,
        config: Dict,
        trade_simulator: Optional['TradeSimulator'] = None
    ):
        self.name = name
        self.client = polymarket_client
        self.config = config
        self.enabled = config.get('enabled', True)
        self.positions: List[Position] = []
        self.performance = StrategyPerformance(strategy_name=name)
        self.running = False
        self.trade_simulator = trade_simulator  # For testing mode
        self.testing_mode = trade_simulator is not None

    @abstractmethod
    async def analyze(self) -> Optional[Dict]:
        """
        Analyze market and identify trading opportunities

        Returns:
            Dict with opportunity details or None
        """
        pass

    @abstractmethod
    async def execute(self, opportunity: Dict) -> Optional[Position]:
        """
        Execute a trade based on identified opportunity

        Args:
            opportunity: Opportunity dict from analyze()

        Returns:
            Position object if trade executed
        """
        pass

    @abstractmethod
    async def monitor_positions(self):
        """Monitor and manage open positions"""
        pass

    def add_position(self, position: Position):
        """Add a position to tracking"""
        self.positions.append(position)
        logger.info(f"[{self.name}] Position opened: {position.position_id}")

    def close_position(
        self,
        position: Position,
        exit_price: float,
        exit_fee: float = 0.0
    ):
        """Close a position"""
        position.close(exit_price, datetime.now(), exit_fee)
        self.performance.update_from_position(position)
        logger.info(
            f"[{self.name}] Position closed: {position.position_id}, "
            f"PnL: ${position.realized_pnl:.2f}, ROI: {position.roi:.2f}%"
        )

    def get_open_positions(self) -> List[Position]:
        """Get all open positions"""
        return [p for p in self.positions if p.status.value == "OPEN"]

    def get_total_exposure(self) -> float:
        """Calculate total exposure across all open positions"""
        return sum(p.cost_basis for p in self.get_open_positions())

    def can_open_position(self, cost: float, max_exposure: float) -> bool:
        """Check if new position can be opened within risk limits"""
        current_exposure = self.get_total_exposure()
        return (current_exposure + cost) <= max_exposure

    def get_performance_summary(self) -> Dict:
        """Get performance summary"""
        return {
            'strategy': self.name,
            'total_trades': self.performance.total_trades,
            'win_rate': self.performance.win_rate,
            'total_pnl': self.performance.total_pnl,
            'net_pnl': self.performance.net_pnl,
            'total_fees': self.performance.total_fees,
            'avg_profit': self.performance.avg_profit_per_trade,
            'max_drawdown': self.performance.max_drawdown,
            'open_positions': len(self.get_open_positions())
        }

    async def start(self):
        """Start the strategy"""
        self.running = True
        logger.info(f"Strategy started: {self.name}")

    async def stop(self):
        """Stop the strategy"""
        self.running = False
        logger.info(f"Strategy stopped: {self.name}")
