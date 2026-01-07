"""
Binary Market Hedging Strategy

Waits for cheap opportunities on either side of binary markets.
Buys YES when it becomes unusually cheap and NO when NO becomes cheap,
asymmetrically at different timestamps when the market temporarily misprices.

Example: Trader "gabagool" paid 96.6 cents for contracts guaranteed to be worth $1.
"""

import asyncio
import time
from typing import Optional, Dict, List
from datetime import datetime
from .base_strategy import BaseStrategy
from ..models.position import Position, Side, PositionStatus
from ..clients.polymarket_client import PolymarketClient
from ..utils.logger import get_logger

logger = get_logger()


class BinaryHedgingStrategy(BaseStrategy):
    """
    Binary market hedging strategy

    Strategy:
    1. Monitor binary (YES/NO) markets
    2. Wait for temporary mispricings where YES + NO ≠ 1.00
    3. Buy the underpriced side
    4. Hold until market resolves or prices normalize
    """

    def __init__(
        self,
        polymarket_client: PolymarketClient,
        config: Dict
    ):
        super().__init__("BinaryHedging", polymarket_client, config)

        self.min_discount = config.get('min_discount', 0.034)  # 3.4% discount minimum
        self.max_positions = config.get('max_positions', 10)
        self.target_markets: List[Dict] = []
        self.price_tracking: Dict[str, List[Dict]] = {}

    async def initialize(self):
        """Initialize strategy - find suitable binary markets"""
        try:
            markets = self.client.get_simplified_markets()

            # Find binary markets with good liquidity
            for market in markets:
                tokens = market.get('tokens', [])

                # Look for binary markets (exactly 2 outcomes)
                if len(tokens) == 2:
                    # Check for sufficient liquidity
                    # For now, add all binary markets
                    self.target_markets.append(market)

            logger.info(f"Initialized with {len(self.target_markets)} binary markets")

        except Exception as e:
            logger.error(f"Failed to initialize strategy: {e}")

    def track_price(self, token_id: str, price: float):
        """Track price history for a token"""
        if token_id not in self.price_tracking:
            self.price_tracking[token_id] = []

        timestamp = time.time()
        self.price_tracking[token_id].append({
            'price': price,
            'timestamp': timestamp
        })

        # Keep only last hour of data
        cutoff = timestamp - 3600
        self.price_tracking[token_id] = [
            p for p in self.price_tracking[token_id]
            if p['timestamp'] >= cutoff
        ]

    def get_avg_price(self, token_id: str, lookback_seconds: int = 300) -> Optional[float]:
        """Get average price over lookback period"""
        if token_id not in self.price_tracking:
            return None

        current_time = time.time()
        recent = [
            p['price'] for p in self.price_tracking[token_id]
            if (current_time - p['timestamp']) <= lookback_seconds
        ]

        if not recent:
            return None

        return sum(recent) / len(recent)

    async def check_market_mispricing(self, market: Dict) -> Optional[Dict]:
        """
        Check if a binary market has mispricing

        In efficient markets, YES + NO should equal ~1.00
        If YES + NO < 1.00, there's an arbitrage opportunity
        If one side is significantly cheaper than expected, buy it
        """
        try:
            tokens = market.get('tokens', [])
            if len(tokens) != 2:
                return None

            token_a = tokens[0]
            token_b = tokens[1]

            token_a_id = token_a.get('token_id')
            token_b_id = token_b.get('token_id')

            # Get current prices
            price_a = self.client.get_midpoint(token_a_id)
            price_b = self.client.get_midpoint(token_b_id)

            if price_a is None or price_b is None:
                return None

            # Track prices
            self.track_price(token_a_id, price_a)
            self.track_price(token_b_id, price_b)

            # Calculate sum (should be close to 1.00)
            price_sum = price_a + price_b

            # Get historical averages
            avg_a = self.get_avg_price(token_a_id, lookback_seconds=300)
            avg_b = self.get_avg_price(token_b_id, lookback_seconds=300)

            opportunities = []

            # Check for undervalued token (significantly below average)
            if avg_a is not None:
                discount_a = (avg_a - price_a) / avg_a
                if discount_a >= self.min_discount and price_a < 0.97:
                    opportunities.append({
                        'market': market,
                        'token_id': token_a_id,
                        'outcome': token_a.get('outcome'),
                        'current_price': price_a,
                        'avg_price': avg_a,
                        'discount': discount_a,
                        'discount_pct': discount_a * 100,
                        'type': 'mean_reversion'
                    })

            if avg_b is not None:
                discount_b = (avg_b - price_b) / avg_b
                if discount_b >= self.min_discount and price_b < 0.97:
                    opportunities.append({
                        'market': market,
                        'token_id': token_b_id,
                        'outcome': token_b.get('outcome'),
                        'current_price': price_b,
                        'avg_price': avg_b,
                        'discount': discount_b,
                        'discount_pct': discount_b * 100,
                        'type': 'mean_reversion'
                    })

            # Check for sum arbitrage (YES + NO < 1.00)
            if price_sum < 0.98:  # More than 2% inefficiency
                # Buy both sides for guaranteed profit
                opportunities.append({
                    'market': market,
                    'type': 'sum_arbitrage',
                    'price_sum': price_sum,
                    'edge': 1.00 - price_sum,
                    'edge_pct': (1.00 - price_sum) * 100,
                    'tokens': [
                        {'token_id': token_a_id, 'price': price_a, 'outcome': token_a.get('outcome')},
                        {'token_id': token_b_id, 'price': price_b, 'outcome': token_b.get('outcome')}
                    ]
                })

            return max(opportunities, key=lambda x: x.get('discount', x.get('edge', 0))) if opportunities else None

        except Exception as e:
            logger.error(f"Error checking market mispricing: {e}")
            return None

    async def analyze(self) -> Optional[Dict]:
        """
        Analyze markets for binary hedging opportunities
        """
        # Check if we're at position limit
        if len(self.get_open_positions()) >= self.max_positions:
            return None

        opportunities = []

        for market in self.target_markets:
            opportunity = await self.check_market_mispricing(market)
            if opportunity:
                opportunities.append(opportunity)

        if opportunities:
            # Return best opportunity
            best = max(opportunities, key=lambda x: x.get('discount', x.get('edge', 0)))

            if best.get('type') == 'sum_arbitrage':
                logger.info(
                    f"SUM ARBITRAGE: {best['market'].get('question')} - "
                    f"Sum: {best['price_sum']:.3f}, Edge: {best['edge_pct']:.2f}%"
                )
            else:
                logger.info(
                    f"DISCOUNT OPPORTUNITY: {best['outcome']} - "
                    f"Price: {best['current_price']:.3f}, Discount: {best['discount_pct']:.2f}%"
                )

            return best

        return None

    async def execute(self, opportunity: Dict) -> Optional[Position]:
        """
        Execute binary hedging trade
        """
        try:
            opp_type = opportunity.get('type')

            if opp_type == 'sum_arbitrage':
                # Buy both sides
                return await self._execute_sum_arbitrage(opportunity)
            else:
                # Buy discounted side
                return await self._execute_discount_trade(opportunity)

        except Exception as e:
            logger.error(f"Failed to execute binary hedging trade: {e}")
            return None

    async def _execute_discount_trade(self, opportunity: Dict) -> Optional[Position]:
        """Execute trade on discounted token"""
        token_id = opportunity['token_id']
        current_price = opportunity['current_price']
        outcome = opportunity['outcome']

        # Position size
        position_size_usd = 100  # $100 per trade
        amount = position_size_usd / current_price

        logger.info(
            f"Buying {outcome} at {current_price:.3f} "
            f"(Discount: {opportunity['discount_pct']:.2f}%)"
        )

        order = self.client.create_market_order(
            token_id=token_id,
            side='BUY',
            amount=amount,
            price=current_price
        )

        if order:
            position = Position(
                position_id=f"binary_{int(time.time())}",
                market_id=opportunity['market'].get('condition_id'),
                token_id=token_id,
                entry_price=current_price,
                amount=amount,
                side=Side.BUY,
                strategy=self.name,
                entry_time=datetime.now(),
                metadata={
                    'outcome': outcome,
                    'discount': opportunity['discount'],
                    'avg_price': opportunity['avg_price'],
                    'type': 'discount'
                }
            )

            self.add_position(position)
            return position

        return None

    async def _execute_sum_arbitrage(self, opportunity: Dict) -> Optional[Position]:
        """Execute sum arbitrage (buy both sides)"""
        tokens = opportunity['tokens']

        # Buy both sides
        positions = []

        for token_info in tokens:
            token_id = token_info['token_id']
            price = token_info['price']
            outcome = token_info['outcome']

            # Equal position sizes
            position_size_usd = 50  # $50 per side
            amount = position_size_usd / price

            logger.info(f"Buying {outcome} at {price:.3f} (Sum Arb)")

            order = self.client.create_market_order(
                token_id=token_id,
                side='BUY',
                amount=amount,
                price=price
            )

            if order:
                position = Position(
                    position_id=f"binary_arb_{int(time.time())}_{outcome}",
                    market_id=opportunity['market'].get('condition_id'),
                    token_id=token_id,
                    entry_price=price,
                    amount=amount,
                    side=Side.BUY,
                    strategy=self.name,
                    entry_time=datetime.now(),
                    metadata={
                        'outcome': outcome,
                        'type': 'sum_arbitrage',
                        'price_sum': opportunity['price_sum'],
                        'edge': opportunity['edge']
                    }
                )

                self.add_position(position)
                positions.append(position)

        return positions[0] if positions else None

    async def monitor_positions(self):
        """Monitor and manage positions"""
        open_positions = self.get_open_positions()

        for position in open_positions:
            try:
                token_id = position.token_id
                current_price = self.client.get_midpoint(token_id)

                if current_price is None:
                    continue

                # Calculate PnL
                unrealized_pnl = position.calculate_pnl(current_price)
                pnl_pct = (unrealized_pnl / position.cost_basis) * 100

                # Exit conditions
                should_exit = False
                exit_reason = ""

                position_type = position.metadata.get('type')

                if position_type == 'discount':
                    # Exit when price returns to average
                    avg_price = position.metadata.get('avg_price')
                    if avg_price and current_price >= avg_price * 0.98:
                        should_exit = True
                        exit_reason = "Price normalized"

                    # Take profit
                    elif current_price > position.entry_price * 1.2:
                        should_exit = True
                        exit_reason = "Take profit"

                    # Stop loss
                    elif current_price < position.entry_price * 0.9:
                        should_exit = True
                        exit_reason = "Stop loss"

                elif position_type == 'sum_arbitrage':
                    # For sum arbitrage, exit when edge diminishes
                    # Check if we can sell at profit
                    if current_price > position.entry_price * 1.05:
                        should_exit = True
                        exit_reason = "Take profit"

                # Market resolved (price at 0 or 1)
                if current_price >= 0.99 or current_price <= 0.01:
                    should_exit = True
                    exit_reason = "Market resolved"

                if should_exit:
                    exit_order = self.client.create_market_order(
                        token_id=token_id,
                        side='SELL',
                        amount=position.amount,
                        price=current_price
                    )

                    if exit_order:
                        self.close_position(position, current_price)
                        logger.info(
                            f"Position closed: {position.position_id} - "
                            f"{exit_reason} - PnL: ${position.realized_pnl:.2f} ({pnl_pct:.2f}%)"
                        )

            except Exception as e:
                logger.error(f"Error monitoring position {position.position_id}: {e}")

    async def run(self):
        """Main strategy loop"""
        await self.initialize()
        await self.start()

        logger.info(f"{self.name} strategy running...")

        while self.running:
            try:
                # Look for opportunities
                opportunity = await self.analyze()

                if opportunity:
                    await self.execute(opportunity)

                # Monitor positions
                await self.monitor_positions()

                # Wait before next iteration
                await asyncio.sleep(2)  # Check every 2 seconds

            except Exception as e:
                logger.error(f"Error in strategy loop: {e}")
                await asyncio.sleep(5)

        logger.info(f"{self.name} strategy stopped")
