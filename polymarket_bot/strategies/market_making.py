"""
Market Making Strategy

Provides liquidity to Polymarket by placing buy and sell orders on both sides
of the market, profiting from the spread while managing inventory risk.
"""

import asyncio
import time
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import statistics
from .base_strategy import BaseStrategy
from ..models.position import Position, Side
from ..clients.polymarket_client import PolymarketClient
from ..utils.logger import get_logger

logger = get_logger()


class MarketMakingStrategy(BaseStrategy):
    """
    Market making strategy

    Strategy:
    1. Select low-volatility markets
    2. Place limit orders on both bid and ask sides
    3. Profit from the spread
    4. Manage inventory risk
    """

    def __init__(
        self,
        polymarket_client: PolymarketClient,
        config: Dict,
        trade_simulator = None
    ):
        super().__init__("MarketMaking", polymarket_client, config, trade_simulator)

        self.min_spread = config.get('min_spread', 0.025)  # 2.5% minimum spread
        self.volatility_lookback_hours = config.get('volatility_lookback_hours', [3, 24, 168, 720])
        self.active_markets: Dict[str, Dict] = {}
        self.price_history: Dict[str, List[Dict]] = {}

    async def initialize(self):
        """Initialize strategy - find suitable markets for making"""
        try:
            markets = self.client.get_simplified_markets()

            # Find markets with good characteristics for market making
            for market in markets:
                # Skip markets with very short timeframes
                # Skip markets with very high volume (too competitive)
                # Focus on steady, predictable markets

                tokens = market.get('tokens', [])
                if len(tokens) != 2:  # Only binary markets for simplicity
                    continue

                self.active_markets[market.get('condition_id')] = market

            logger.info(f"Initialized with {len(self.active_markets)} markets for making")

        except Exception as e:
            logger.error(f"Failed to initialize strategy: {e}")

    def record_price(self, token_id: str, price: float):
        """Record price for volatility calculation"""
        if token_id not in self.price_history:
            self.price_history[token_id] = []

        timestamp = time.time()
        self.price_history[token_id].append({
            'price': price,
            'timestamp': timestamp
        })

        # Keep only last 30 days
        cutoff = timestamp - (30 * 24 * 3600)
        self.price_history[token_id] = [
            p for p in self.price_history[token_id]
            if p['timestamp'] >= cutoff
        ]

    def calculate_volatility(self, token_id: str, lookback_hours: int) -> Optional[float]:
        """Calculate price volatility over lookback period"""
        if token_id not in self.price_history:
            return None

        current_time = time.time()
        lookback_seconds = lookback_hours * 3600

        recent_prices = [
            p['price'] for p in self.price_history[token_id]
            if (current_time - p['timestamp']) <= lookback_seconds
        ]

        if len(recent_prices) < 10:  # Need sufficient data
            return None

        # Calculate standard deviation (volatility)
        return statistics.stdev(recent_prices)

    def is_suitable_for_making(self, token_id: str) -> bool:
        """
        Determine if a market is suitable for market making

        Low volatility markets are preferred
        """
        # Check volatility across multiple timeframes
        volatilities = []

        for lookback_hours in self.volatility_lookback_hours:
            vol = self.calculate_volatility(token_id, lookback_hours)
            if vol is not None:
                volatilities.append(vol)

        if not volatilities:
            return False  # Not enough data

        avg_vol = sum(volatilities) / len(volatilities)

        # Low volatility threshold
        return avg_vol < 0.05  # Less than 5% standard deviation

    async def analyze(self) -> Optional[Dict]:
        """Analyze for market making opportunities"""
        opportunities = []

        for condition_id, market in list(self.active_markets.items())[:20]:  # Limit analysis
            try:
                tokens = market.get('tokens', [])
                if len(tokens) != 2:
                    continue

                token_id = tokens[0].get('token_id')

                # Get current market state
                order_book = self.client.get_order_book(token_id)
                if not order_book:
                    continue

                midpoint = self.client.get_midpoint(token_id)
                if midpoint is None:
                    continue

                # Record price
                self.record_price(token_id, midpoint)

                # Check if suitable for making
                if not self.is_suitable_for_making(token_id):
                    continue

                # Calculate current spread
                bids = order_book.get('bids', [])
                asks = order_book.get('asks', [])

                if not bids or not asks:
                    continue

                best_bid = float(bids[0].get('price', 0))
                best_ask = float(asks[0].get('price', 1))

                current_spread = best_ask - best_bid
                spread_pct = (current_spread / midpoint) * 100

                # Check if spread is wide enough
                if spread_pct >= self.min_spread * 100:
                    opportunities.append({
                        'market': market,
                        'token_id': token_id,
                        'midpoint': midpoint,
                        'best_bid': best_bid,
                        'best_ask': best_ask,
                        'spread': current_spread,
                        'spread_pct': spread_pct
                    })

            except Exception as e:
                logger.error(f"Error analyzing market {condition_id}: {e}")

        if opportunities:
            # Return market with widest spread
            best = max(opportunities, key=lambda x: x['spread_pct'])

            logger.info(
                f"MM OPPORTUNITY: {best['market'].get('question')[:50]} - "
                f"Spread: {best['spread_pct']:.2f}%"
            )

            return best

        return None

    async def execute(self, opportunity: Dict) -> Optional[Position]:
        """Execute market making orders"""
        try:
            token_id = opportunity['token_id']
            midpoint = opportunity['midpoint']

            # Calculate our bid and ask prices
            # Place orders slightly inside the current best bid/ask
            our_bid = midpoint * 0.99  # 1% below mid
            our_ask = midpoint * 1.01  # 1% above mid

            # Position size
            position_size = 50  # $50 per side

            bid_amount = position_size / our_bid
            ask_amount = position_size / our_ask

            logger.info(
                f"Placing MM orders - Bid: {our_bid:.3f} (${position_size}), "
                f"Ask: {our_ask:.3f} (${position_size})"
            )

            # Place limit orders on both sides
            bid_order = self.client.create_limit_order(
                token_id=token_id,
                side='BUY',
                amount=bid_amount,
                price=our_bid
            )

            ask_order = self.client.create_limit_order(
                token_id=token_id,
                side='SELL',
                amount=ask_amount,
                price=our_ask
            )

            # Track as positions (simplified)
            if bid_order:
                position = Position(
                    position_id=f"mm_bid_{int(time.time())}",
                    market_id=opportunity['market'].get('condition_id'),
                    token_id=token_id,
                    entry_price=our_bid,
                    amount=bid_amount,
                    side=Side.BUY,
                    strategy=self.name,
                    entry_time=datetime.now(),
                    metadata={
                        'type': 'market_making',
                        'side': 'bid',
                        'target_spread': opportunity['spread_pct']
                    }
                )

                self.add_position(position)
                return position

        except Exception as e:
            logger.error(f"Failed to execute market making: {e}")

        return None

    async def monitor_positions(self):
        """Monitor market making positions"""
        open_positions = self.get_open_positions()

        for position in open_positions:
            try:
                # Check if orders are filled
                # In production, use order status API
                token_id = position.token_id
                current_price = self.client.get_midpoint(token_id)

                if current_price is None:
                    continue

                # Simple exit: if price moved against us significantly
                if position.side == Side.BUY:
                    if current_price < position.entry_price * 0.95:  # 5% loss
                        # Cancel order and exit
                        self.close_position(position, current_price)

                # Hold winning positions
                # In production, manage inventory and rebalance

            except Exception as e:
                logger.error(f"Error monitoring MM position: {e}")

    async def run(self):
        """Main strategy loop"""
        await self.initialize()
        await self.start()

        logger.info(f"{self.name} strategy running...")

        while self.running:
            try:
                opportunity = await self.analyze()

                if opportunity:
                    await self.execute(opportunity)

                await self.monitor_positions()

                # Check periodically
                await asyncio.sleep(30)

            except Exception as e:
                logger.error(f"Error in strategy loop: {e}")
                await asyncio.sleep(30)

        logger.info(f"{self.name} strategy stopped")
