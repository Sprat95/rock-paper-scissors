"""
Real-time price feeds from crypto exchanges
"""

import asyncio
import json
from typing import Dict, Callable, Optional, List
from binance.client import Client as BinanceClient
from binance import AsyncClient, BinanceSocketManager
from ..utils.logger import get_logger

logger = get_logger()


class PriceFeed:
    """Base class for price feeds"""

    def __init__(self):
        self.prices: Dict[str, float] = {}
        self.callbacks: List[Callable] = []
        self.last_update: Dict[str, float] = {}

    def add_callback(self, callback: Callable):
        """Add callback function for price updates"""
        self.callbacks.append(callback)

    def update_price(self, symbol: str, price: float, timestamp: float = None):
        """Update price and trigger callbacks"""
        self.prices[symbol] = price
        if timestamp:
            self.last_update[symbol] = timestamp

        for callback in self.callbacks:
            try:
                callback(symbol, price, timestamp)
            except Exception as e:
                logger.error(f"Error in price callback: {e}")

    def get_price(self, symbol: str) -> Optional[float]:
        """Get current price for symbol"""
        return self.prices.get(symbol)


class BinancePriceFeed(PriceFeed):
    """Real-time price feed from Binance"""

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        super().__init__()
        self.api_key = api_key
        self.api_secret = api_secret
        self.client: Optional[BinanceClient] = None
        self.async_client: Optional[AsyncClient] = None
        self.bsm: Optional[BinanceSocketManager] = None
        self.running = False

    async def initialize(self):
        """Initialize async Binance client"""
        try:
            if self.api_key and self.api_secret:
                self.async_client = await AsyncClient.create(self.api_key, self.api_secret)
            else:
                self.async_client = await AsyncClient.create()

            self.bsm = BinanceSocketManager(self.async_client)
            logger.info("Binance price feed initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Binance client: {e}")
            raise

    async def start_symbol_ticker(self, symbol: str):
        """Start real-time ticker for a symbol"""
        try:
            socket = self.bsm.symbol_ticker_socket(symbol)
            async with socket as tscm:
                while self.running:
                    msg = await tscm.recv()
                    if msg:
                        price = float(msg.get('c', 0))  # 'c' is close/current price
                        timestamp = msg.get('E', 0) / 1000  # Event time in seconds
                        self.update_price(symbol, price, timestamp)
        except Exception as e:
            logger.error(f"Error in symbol ticker for {symbol}: {e}")

    async def start_multi_ticker(self, symbols: List[str]):
        """Start real-time tickers for multiple symbols"""
        try:
            # Use multiplex socket for better performance
            socket = self.bsm.multiplex_socket([f'{s.lower()}@ticker' for s in symbols])
            async with socket as tscm:
                while self.running:
                    msg = await tscm.recv()
                    if msg and 'data' in msg:
                        data = msg['data']
                        symbol = data.get('s')
                        price = float(data.get('c', 0))
                        timestamp = data.get('E', 0) / 1000
                        self.update_price(symbol, price, timestamp)
        except Exception as e:
            logger.error(f"Error in multi ticker: {e}")

    async def start(self, symbols: List[str]):
        """Start the price feed for given symbols"""
        await self.initialize()
        self.running = True
        logger.info(f"Starting Binance feed for symbols: {symbols}")

        # Start multi ticker
        await self.start_multi_ticker(symbols)

    async def stop(self):
        """Stop the price feed"""
        self.running = False
        if self.async_client:
            await self.async_client.close_connection()
        logger.info("Binance price feed stopped")


class AggregatedPriceFeed:
    """Aggregates prices from multiple exchanges"""

    def __init__(self):
        self.feeds: Dict[str, PriceFeed] = {}
        self.aggregated_prices: Dict[str, Dict[str, float]] = {}

    def add_feed(self, name: str, feed: PriceFeed):
        """Add a price feed"""
        self.feeds[name] = feed
        feed.add_callback(self._on_price_update)

    def _on_price_update(self, symbol: str, price: float, timestamp: float):
        """Handle price updates from feeds"""
        if symbol not in self.aggregated_prices:
            self.aggregated_prices[symbol] = {}

        # Store price from each exchange
        for feed_name, feed in self.feeds.items():
            feed_price = feed.get_price(symbol)
            if feed_price:
                self.aggregated_prices[symbol][feed_name] = feed_price

    def get_best_price(self, symbol: str, side: str = 'mid') -> Optional[float]:
        """
        Get best price across all exchanges

        Args:
            symbol: Trading symbol
            side: 'buy', 'sell', or 'mid'
        """
        if symbol not in self.aggregated_prices:
            return None

        prices = list(self.aggregated_prices[symbol].values())
        if not prices:
            return None

        if side == 'buy':
            return min(prices)  # Best buy price (lowest)
        elif side == 'sell':
            return max(prices)  # Best sell price (highest)
        else:  # mid
            return sum(prices) / len(prices)

    def get_price_spread(self, symbol: str) -> Optional[Dict]:
        """Get price spread across exchanges"""
        if symbol not in self.aggregated_prices:
            return None

        prices = self.aggregated_prices[symbol]
        if not prices:
            return None

        values = list(prices.values())
        return {
            'min': min(values),
            'max': max(values),
            'spread': max(values) - min(values),
            'spread_pct': (max(values) - min(values)) / min(values) * 100,
            'exchanges': prices
        }


class LatencyMonitor:
    """Monitor latency between price updates"""

    def __init__(self):
        self.latencies: Dict[str, List[float]] = {}
        self.max_samples = 100

    def record_latency(self, symbol: str, latency_ms: float):
        """Record latency for a symbol"""
        if symbol not in self.latencies:
            self.latencies[symbol] = []

        self.latencies[symbol].append(latency_ms)

        # Keep only recent samples
        if len(self.latencies[symbol]) > self.max_samples:
            self.latencies[symbol] = self.latencies[symbol][-self.max_samples:]

    def get_avg_latency(self, symbol: str) -> Optional[float]:
        """Get average latency for a symbol"""
        if symbol not in self.latencies or not self.latencies[symbol]:
            return None

        return sum(self.latencies[symbol]) / len(self.latencies[symbol])

    def get_max_latency(self, symbol: str) -> Optional[float]:
        """Get maximum latency for a symbol"""
        if symbol not in self.latencies or not self.latencies[symbol]:
            return None

        return max(self.latencies[symbol])
