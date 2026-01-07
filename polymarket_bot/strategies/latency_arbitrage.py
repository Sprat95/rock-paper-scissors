"""
Temporal/Latency Arbitrage Strategy

Exploits the lag between spot crypto prices on exchanges (Binance, Coinbase)
and Polymarket's 15-minute up/down markets. When BTC/ETH/SOL makes a strong
move on exchanges, the Polymarket odds lag behind, creating arbitrage opportunities.
"""

import asyncio
import time
from typing import Optional, Dict, List
from datetime import datetime
from .base_strategy import BaseStrategy
from ..models.position import Position, Side, PositionStatus
from ..clients.polymarket_client import PolymarketClient
from ..data_feeds.exchange_feeds import BinancePriceFeed
from ..utils.logger import get_logger

logger = get_logger()


class LatencyArbitrageStrategy(BaseStrategy):
    """
    Temporal arbitrage strategy for crypto markets

    The bot that turned $313 into $438k used this exact strategy:
    1. Monitor BTC/ETH/SOL spot prices on Binance/Coinbase
    2. Detect significant price movements (momentum)
    3. Check Polymarket 15-min markets
    4. If Polymarket odds haven't updated (still ~50%), buy the likely outcome
    5. Exit when odds update or market resolves
    """

    def __init__(
        self,
        polymarket_client: PolymarketClient,
        config: Dict,
        price_feed: BinancePriceFeed
    ):
        super().__init__("LatencyArbitrage", polymarket_client, config)

        self.price_feed = price_feed
        self.min_edge = config.get('min_edge', 0.03)  # 3% edge minimum
        self.max_latency_ms = config.get('max_latency_ms', 500)
        self.markets_config = config.get('markets', ['BTC_15min', 'ETH_15min', 'SOL_15min'])

        # Market mappings
        self.symbol_to_polymarket = {
            'BTCUSDT': 'BTC_15min',
            'ETHUSDT': 'ETH_15min',
            'SOLUSDT': 'SOL_15min'
        }

        # Price history for momentum calculation
        self.price_history: Dict[str, List[Dict]] = {}
        self.polymarket_markets: Dict[str, Dict] = {}

        # Performance tracking
        self.opportunities_found = 0
        self.opportunities_taken = 0

    async def initialize(self):
        """Initialize strategy - fetch Polymarket markets"""
        try:
            # Get all markets
            markets = self.client.get_simplified_markets()

            # Find 15-minute crypto markets
            for market in markets:
                question = market.get('question', '').lower()

                # Look for 15-minute up/down markets
                if '15 min' in question or '15min' in question or '15-minute' in question:
                    for crypto in ['btc', 'eth', 'sol']:
                        if crypto in question:
                            market_key = f"{crypto.upper()}_15min"
                            if market_key in self.markets_config:
                                self.polymarket_markets[market_key] = market
                                logger.info(f"Found {market_key} market: {market.get('condition_id')}")

            logger.info(f"Initialized with {len(self.polymarket_markets)} markets")

        except Exception as e:
            logger.error(f"Failed to initialize strategy: {e}")

    def calculate_momentum(self, symbol: str, timeframe_seconds: int = 60) -> Optional[Dict]:
        """
        Calculate price momentum over timeframe

        Returns:
            Dict with momentum metrics or None
        """
        if symbol not in self.price_history:
            return None

        history = self.price_history[symbol]
        if len(history) < 2:
            return None

        current_time = time.time()
        recent_prices = [
            p for p in history
            if (current_time - p['timestamp']) <= timeframe_seconds
        ]

        if len(recent_prices) < 2:
            return None

        # Get first and last prices in timeframe
        start_price = recent_prices[0]['price']
        end_price = recent_prices[-1]['price']

        # Calculate percentage change
        pct_change = ((end_price - start_price) / start_price) * 100

        # Determine direction
        direction = 'UP' if pct_change > 0 else 'DOWN'

        return {
            'symbol': symbol,
            'start_price': start_price,
            'end_price': end_price,
            'pct_change': abs(pct_change),
            'direction': direction,
            'confidence': min(abs(pct_change) / 5.0, 1.0)  # Normalize to 0-1
        }

    def update_price_history(self, symbol: str, price: float):
        """Update price history for a symbol"""
        if symbol not in self.price_history:
            self.price_history[symbol] = []

        timestamp = time.time()
        self.price_history[symbol].append({
            'price': price,
            'timestamp': timestamp
        })

        # Keep only last 5 minutes of data
        cutoff = timestamp - 300
        self.price_history[symbol] = [
            p for p in self.price_history[symbol]
            if p['timestamp'] >= cutoff
        ]

    async def check_polymarket_odds(self, market_key: str, expected_direction: str) -> Optional[Dict]:
        """
        Check if Polymarket odds are stale/mispriced

        Args:
            market_key: Market identifier (e.g., 'BTC_15min')
            expected_direction: Expected direction ('UP' or 'DOWN')

        Returns:
            Opportunity dict if edge exists
        """
        if market_key not in self.polymarket_markets:
            return None

        market = self.polymarket_markets[market_key]
        condition_id = market.get('condition_id')

        # Get current odds from Polymarket
        try:
            # Get tokens for this market (typically YES/NO or UP/DOWN)
            tokens = market.get('tokens', [])

            if len(tokens) < 2:
                return None

            # Find UP and DOWN tokens
            up_token = None
            down_token = None

            for token in tokens:
                outcome = token.get('outcome', '').upper()
                if 'UP' in outcome or 'YES' in outcome:
                    up_token = token
                elif 'DOWN' in outcome or 'NO' in outcome:
                    down_token = token

            if not up_token or not down_token:
                return None

            # Get current prices
            up_token_id = up_token.get('token_id')
            down_token_id = down_token.get('token_id')

            up_price = self.client.get_midpoint(up_token_id)
            down_price = self.client.get_midpoint(down_token_id)

            if up_price is None or down_price is None:
                return None

            # Determine if there's an edge
            target_token_id = up_token_id if expected_direction == 'UP' else down_token_id
            target_price = up_price if expected_direction == 'UP' else down_price

            # If price is still near 0.5, there's a potential edge
            # (Based on research: bot bought when actual probability was ~85% but market showed 50/50)
            if target_price < 0.6:  # Market hasn't priced in the move yet
                edge = 0.85 - target_price  # Expected value - current price

                if edge >= self.min_edge:
                    return {
                        'market_key': market_key,
                        'condition_id': condition_id,
                        'token_id': target_token_id,
                        'direction': expected_direction,
                        'current_price': target_price,
                        'expected_value': 0.85,  # Conservative estimate
                        'edge': edge,
                        'edge_pct': (edge / target_price) * 100
                    }

        except Exception as e:
            logger.error(f"Error checking Polymarket odds for {market_key}: {e}")

        return None

    async def analyze(self) -> Optional[Dict]:
        """
        Analyze for latency arbitrage opportunities

        Strategy:
        1. Get current prices from exchange feed
        2. Calculate momentum
        3. If strong momentum detected, check Polymarket odds
        4. If Polymarket hasn't updated, we have an opportunity
        """
        opportunities = []

        for symbol, poly_market in self.symbol_to_polymarket.items():
            # Get current price
            current_price = self.price_feed.get_price(symbol)
            if current_price is None:
                continue

            # Update price history
            self.update_price_history(symbol, current_price)

            # Calculate momentum (last 60 seconds)
            momentum = self.calculate_momentum(symbol, timeframe_seconds=60)
            if momentum is None:
                continue

            # Check if momentum is significant enough
            if momentum['pct_change'] < 1.0:  # Less than 1% move
                continue

            logger.info(
                f"{symbol}: {momentum['direction']} {momentum['pct_change']:.2f}% "
                f"(confidence: {momentum['confidence']:.2f})"
            )

            # Check Polymarket odds
            poly_opportunity = await self.check_polymarket_odds(
                poly_market,
                momentum['direction']
            )

            if poly_opportunity:
                poly_opportunity['momentum'] = momentum
                poly_opportunity['symbol'] = symbol
                opportunities.append(poly_opportunity)
                self.opportunities_found += 1

                logger.info(
                    f"OPPORTUNITY FOUND: {poly_market} {momentum['direction']} "
                    f"- Edge: {poly_opportunity['edge']:.2%} "
                    f"(Price: {poly_opportunity['current_price']:.3f})"
                )

        # Return best opportunity (highest edge)
        if opportunities:
            return max(opportunities, key=lambda x: x['edge'])

        return None

    async def execute(self, opportunity: Dict) -> Optional[Position]:
        """
        Execute a latency arbitrage trade

        Args:
            opportunity: Opportunity from analyze()
        """
        try:
            token_id = opportunity['token_id']
            direction = opportunity['direction']
            edge = opportunity['edge']
            current_price = opportunity['current_price']
            market_key = opportunity['market_key']

            # Calculate position size (simple fixed size for now)
            # In production, this should use proper risk management
            position_size_usd = 100  # $100 per trade

            amount = position_size_usd / current_price

            # Execute market order
            logger.info(
                f"Executing {direction} order for {market_key}: "
                f"${position_size_usd} at {current_price:.3f}"
            )

            order = self.client.create_market_order(
                token_id=token_id,
                side='BUY',
                amount=amount,
                price=current_price
            )

            if order:
                # Create position
                position = Position(
                    position_id=f"latency_{int(time.time())}",
                    market_id=opportunity['condition_id'],
                    token_id=token_id,
                    entry_price=current_price,
                    amount=amount,
                    side=Side.BUY,
                    strategy=self.name,
                    entry_time=datetime.now(),
                    metadata={
                        'direction': direction,
                        'edge': edge,
                        'symbol': opportunity['symbol'],
                        'momentum': opportunity['momentum']
                    }
                )

                self.add_position(position)
                self.opportunities_taken += 1

                logger.info(f"Position opened successfully: {position.position_id}")
                return position

        except Exception as e:
            logger.error(f"Failed to execute latency arbitrage trade: {e}")

        return None

    async def monitor_positions(self):
        """
        Monitor open positions and close when:
        1. Market resolves
        2. Odds have updated (no more edge)
        3. Stop loss hit
        """
        open_positions = self.get_open_positions()

        for position in open_positions:
            try:
                token_id = position.token_id
                current_price = self.client.get_midpoint(token_id)

                if current_price is None:
                    continue

                # Calculate current PnL
                unrealized_pnl = position.calculate_pnl(current_price)
                pnl_pct = (unrealized_pnl / position.cost_basis) * 100

                # Exit conditions
                should_exit = False
                exit_reason = ""

                # Take profit if odds have moved in our favor
                if current_price > position.entry_price * 1.5:  # 50% profit
                    should_exit = True
                    exit_reason = "Take profit"

                # Stop loss
                elif current_price < position.entry_price * 0.8:  # 20% loss
                    should_exit = True
                    exit_reason = "Stop loss"

                # Market about to close (15 minutes elapsed)
                elif (datetime.now() - position.entry_time).seconds > 840:  # 14 minutes
                    should_exit = True
                    exit_reason = "Market closing soon"

                if should_exit:
                    # Execute exit
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
                            f"{exit_reason} - PnL: {pnl_pct:.2f}%"
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
                    # Execute trade
                    position = await self.execute(opportunity)

                # Monitor existing positions
                await self.monitor_positions()

                # Wait before next iteration
                await asyncio.sleep(1)  # Check every second

            except Exception as e:
                logger.error(f"Error in strategy loop: {e}")
                await asyncio.sleep(5)

        logger.info(f"{self.name} strategy stopped")
