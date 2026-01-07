"""
Combinatorial Arbitrage Strategy

Exploits mismatched probabilities or inconsistencies between related markets.
For example, if Market A + Market B should equal Market C, but the probabilities
don't match, there's an arbitrage opportunity.
"""

import asyncio
import time
from typing import Optional, Dict, List
from datetime import datetime
from itertools import combinations
from .base_strategy import BaseStrategy
from ..models.position import Position, Side
from ..clients.polymarket_client import PolymarketClient
from ..utils.logger import get_logger

logger = get_logger()


class CombinatorialArbitrageStrategy(BaseStrategy):
    """
    Combinatorial arbitrage strategy

    Strategy:
    1. Find related markets (e.g., election outcomes, sports playoffs)
    2. Check if probabilities are consistent
    3. If inconsistent, execute arbitrage across markets
    """

    def __init__(
        self,
        polymarket_client: PolymarketClient,
        config: Dict,
        trade_simulator = None
    ):
        super().__init__("CombinatorialArbitrage", polymarket_client, config, trade_simulator)

        self.min_edge = config.get('min_edge', 0.02)  # 2% edge minimum
        self.max_markets_per_combo = config.get('max_markets_per_combo', 5)
        self.market_groups: Dict[str, List[Dict]] = {}

    async def initialize(self):
        """Initialize strategy - group related markets"""
        try:
            markets = self.client.get_simplified_markets()

            # Group markets by keywords/topics
            # This is simplified - in production, use NLP or manual curation
            for market in markets:
                question = market.get('question', '').lower()

                # Group by topic
                topic = self._extract_topic(question)
                if topic:
                    if topic not in self.market_groups:
                        self.market_groups[topic] = []
                    self.market_groups[topic].append(market)

            logger.info(
                f"Initialized with {len(self.market_groups)} market groups, "
                f"{sum(len(g) for g in self.market_groups.values())} total markets"
            )

        except Exception as e:
            logger.error(f"Failed to initialize strategy: {e}")

    def _extract_topic(self, question: str) -> Optional[str]:
        """Extract topic from question (simplified)"""
        # Election markets
        if 'election' in question or 'president' in question or 'senate' in question:
            return 'election'
        # Sports markets
        elif any(sport in question for sport in ['nfl', 'nba', 'mlb', 'nhl', 'super bowl']):
            return 'sports'
        # Crypto markets
        elif any(crypto in question for crypto in ['bitcoin', 'btc', 'ethereum', 'eth']):
            return 'crypto'

        return None

    async def check_mutually_exclusive_markets(self, markets: List[Dict]) -> Optional[Dict]:
        """
        Check if mutually exclusive markets sum to 100%

        Example: "Team A wins", "Team B wins", "Tie" should sum to 100%
        """
        try:
            if len(markets) < 2 or len(markets) > self.max_markets_per_combo:
                return None

            # Get probabilities for each market
            market_probs = []

            for market in markets:
                tokens = market.get('tokens', [])
                if not tokens:
                    continue

                # Get YES token price (probability)
                yes_token = tokens[0]
                token_id = yes_token.get('token_id')
                prob = self.client.get_midpoint(token_id)

                if prob is None:
                    return None

                market_probs.append({
                    'market': market,
                    'token_id': token_id,
                    'probability': prob,
                    'outcome': yes_token.get('outcome')
                })

            if len(market_probs) < 2:
                return None

            # Check if sum of probabilities != 1.0
            total_prob = sum(m['probability'] for m in market_probs)

            # If markets are mutually exclusive, total should be ~1.0
            deviation = abs(1.0 - total_prob)

            if deviation > self.min_edge:
                # There's an arbitrage opportunity
                edge_type = "overpriced" if total_prob > 1.0 else "underpriced"

                return {
                    'type': 'mutually_exclusive',
                    'markets': market_probs,
                    'total_probability': total_prob,
                    'deviation': deviation,
                    'deviation_pct': deviation * 100,
                    'edge_type': edge_type
                }

        except Exception as e:
            logger.error(f"Error checking mutually exclusive markets: {e}")

        return None

    async def analyze(self) -> Optional[Dict]:
        """Analyze for combinatorial arbitrage opportunities"""
        opportunities = []

        for topic, markets in self.market_groups.items():
            # Check combinations of markets
            for combo_size in range(2, min(len(markets) + 1, self.max_markets_per_combo + 1)):
                for market_combo in combinations(markets[:10], combo_size):  # Limit search
                    opportunity = await self.check_mutually_exclusive_markets(list(market_combo))

                    if opportunity:
                        opportunity['topic'] = topic
                        opportunities.append(opportunity)

                        logger.info(
                            f"COMBO ARB: {topic} - "
                            f"{combo_size} markets, Total prob: {opportunity['total_probability']:.2%}, "
                            f"Deviation: {opportunity['deviation_pct']:.2f}%"
                        )

        if opportunities:
            # Return best opportunity
            return max(opportunities, key=lambda x: x['deviation'])

        return None

    async def execute(self, opportunity: Dict) -> Optional[Position]:
        """Execute combinatorial arbitrage trade"""
        try:
            edge_type = opportunity['edge_type']
            markets = opportunity['markets']

            if edge_type == "underpriced":
                # Total probability < 1.0 - buy all outcomes
                return await self._execute_buy_all(opportunity)
            else:
                # Total probability > 1.0 - sell all outcomes (requires existing positions)
                logger.info("Overpriced combo detected - skipping (would need to short)")
                return None

        except Exception as e:
            logger.error(f"Failed to execute combinatorial arbitrage: {e}")
            return None

    async def _execute_buy_all(self, opportunity: Dict) -> Optional[Position]:
        """Buy all outcomes when underpriced"""
        markets = opportunity['markets']
        total_prob = opportunity['total_probability']
        deviation = opportunity['deviation']

        positions_created = []

        # Total capital to deploy
        total_capital = 100  # $100

        # Allocate proportionally to probabilities
        for market_info in markets:
            token_id = market_info['token_id']
            prob = market_info['probability']
            outcome = market_info['outcome']

            # Allocate capital proportionally
            allocation = total_capital * (prob / total_prob)
            amount = allocation / prob

            logger.info(
                f"Buying {outcome} at {prob:.3f} "
                f"(${allocation:.2f} allocation)"
            )

            order = self.client.create_market_order(
                token_id=token_id,
                side='BUY',
                amount=amount,
                price=prob
            )

            if order:
                position = Position(
                    position_id=f"combo_{int(time.time())}_{outcome}",
                    market_id=market_info['market'].get('condition_id'),
                    token_id=token_id,
                    entry_price=prob,
                    amount=amount,
                    side=Side.BUY,
                    strategy=self.name,
                    entry_time=datetime.now(),
                    metadata={
                        'outcome': outcome,
                        'type': 'buy_all',
                        'total_prob': total_prob,
                        'deviation': deviation,
                        'combo_id': f"combo_{int(time.time())}"
                    }
                )

                self.add_position(position)
                positions_created.append(position)

        return positions_created[0] if positions_created else None

    async def monitor_positions(self):
        """Monitor combinatorial arbitrage positions"""
        open_positions = self.get_open_positions()

        # Group positions by combo_id
        combos: Dict[str, List[Position]] = {}
        for position in open_positions:
            combo_id = position.metadata.get('combo_id')
            if combo_id:
                if combo_id not in combos:
                    combos[combo_id] = []
                combos[combo_id].append(position)

        # Monitor each combo
        for combo_id, positions in combos.items():
            try:
                # Calculate total PnL for the combo
                total_pnl = 0
                total_cost = 0
                all_resolved = True

                for position in positions:
                    token_id = position.token_id
                    current_price = self.client.get_midpoint(token_id)

                    if current_price is None:
                        all_resolved = False
                        continue

                    unrealized_pnl = position.calculate_pnl(current_price)
                    total_pnl += unrealized_pnl
                    total_cost += position.cost_basis

                    # Check if market resolved
                    if current_price < 0.01 or current_price > 0.99:
                        # Market resolved
                        if position.status.value == "OPEN":
                            self.close_position(position, current_price)
                    else:
                        all_resolved = False

                # If all markets in combo resolved, log final result
                if all_resolved:
                    roi = (total_pnl / total_cost) * 100 if total_cost > 0 else 0
                    logger.info(
                        f"Combo {combo_id} fully resolved - "
                        f"Total PnL: ${total_pnl:.2f}, ROI: {roi:.2f}%"
                    )

            except Exception as e:
                logger.error(f"Error monitoring combo {combo_id}: {e}")

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

                # Check less frequently (more compute intensive)
                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Error in strategy loop: {e}")
                await asyncio.sleep(10)

        logger.info(f"{self.name} strategy stopped")
