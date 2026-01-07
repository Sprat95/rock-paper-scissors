"""
Polymarket API client wrapper
"""

from typing import Optional, Dict, Any, List
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, MarketOrderArgs, OrderType
from py_clob_client.exceptions import PolyApiException
from ..utils.logger import get_logger

logger = get_logger()


class PolymarketClient:
    """Wrapper around py-clob-client for Polymarket trading"""

    def __init__(
        self,
        private_key: str,
        chain_id: int = 137,
        host: str = "https://clob.polymarket.com",
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        api_passphrase: Optional[str] = None
    ):
        """
        Initialize Polymarket client

        Args:
            private_key: Ethereum private key
            chain_id: Chain ID (137 for Polygon mainnet)
            host: CLOB API host
            api_key: Optional API key
            api_secret: Optional API secret
            api_passphrase: Optional API passphrase
        """
        self.private_key = private_key
        self.chain_id = chain_id
        self.host = host

        try:
            self.client = ClobClient(
                host=host,
                key=private_key,
                chain_id=chain_id
            )
            logger.info("Polymarket client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Polymarket client: {e}")
            raise

    def get_markets(self, **params) -> List[Dict]:
        """Get available markets"""
        try:
            markets = self.client.get_markets(**params)
            return markets
        except PolyApiException as e:
            logger.error(f"Failed to get markets: {e}")
            return []

    def get_simplified_markets(self) -> List[Dict]:
        """Get simplified market data"""
        try:
            return self.client.get_simplified_markets()
        except PolyApiException as e:
            logger.error(f"Failed to get simplified markets: {e}")
            return []

    def get_market(self, condition_id: str) -> Optional[Dict]:
        """Get specific market by condition ID"""
        try:
            return self.client.get_market(condition_id)
        except PolyApiException as e:
            logger.error(f"Failed to get market {condition_id}: {e}")
            return None

    def get_order_book(self, token_id: str) -> Optional[Dict]:
        """Get order book for a token"""
        try:
            return self.client.get_order_book(token_id)
        except PolyApiException as e:
            logger.error(f"Failed to get order book for {token_id}: {e}")
            return None

    def get_midpoint(self, token_id: str) -> Optional[float]:
        """Get midpoint price for a token"""
        try:
            return self.client.get_midpoint(token_id)
        except PolyApiException as e:
            logger.error(f"Failed to get midpoint for {token_id}: {e}")
            return None

    def get_price(self, token_id: str, side: str) -> Optional[float]:
        """
        Get price for a token on specific side

        Args:
            token_id: Token ID
            side: 'BUY' or 'SELL'
        """
        try:
            return self.client.get_price(token_id, side)
        except PolyApiException as e:
            logger.error(f"Failed to get {side} price for {token_id}: {e}")
            return None

    def get_last_trade_price(self, token_id: str) -> Optional[float]:
        """Get last trade price for a token"""
        try:
            return self.client.get_last_trade_price(token_id)
        except PolyApiException as e:
            logger.error(f"Failed to get last trade price for {token_id}: {e}")
            return None

    def create_market_order(
        self,
        token_id: str,
        side: str,
        amount: float,
        price: Optional[float] = None
    ) -> Optional[Dict]:
        """
        Create and submit a market order

        Args:
            token_id: Token ID to trade
            side: 'BUY' or 'SELL'
            amount: Amount to trade
            price: Optional price (for FOK orders)
        """
        try:
            order_args = MarketOrderArgs(
                token_id=token_id,
                amount=amount,
                price=price
            )

            if side.upper() == 'BUY':
                order = self.client.create_market_buy_order(order_args)
            else:
                order = self.client.create_market_sell_order(order_args)

            # Submit order
            result = self.client.post_order(order, OrderType.FOK)
            logger.info(f"Market order created: {side} {amount} of {token_id}")
            return result

        except PolyApiException as e:
            logger.error(f"Failed to create market order: {e}")
            return None

    def create_limit_order(
        self,
        token_id: str,
        side: str,
        amount: float,
        price: float,
        expiration: Optional[int] = None
    ) -> Optional[Dict]:
        """
        Create and submit a limit order

        Args:
            token_id: Token ID to trade
            side: 'BUY' or 'SELL'
            amount: Amount to trade
            price: Limit price
            expiration: Optional expiration timestamp
        """
        try:
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=amount,
                side=side.upper(),
                expiration=expiration
            )

            order = self.client.create_order(order_args)
            result = self.client.post_order(order, OrderType.GTC)
            logger.info(f"Limit order created: {side} {amount} of {token_id} at {price}")
            return result

        except PolyApiException as e:
            logger.error(f"Failed to create limit order: {e}")
            return None

    def get_open_orders(self, market: Optional[str] = None) -> List[Dict]:
        """Get all open orders"""
        try:
            return self.client.get_orders(market=market)
        except PolyApiException as e:
            logger.error(f"Failed to get open orders: {e}")
            return []

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a specific order"""
        try:
            self.client.cancel(order_id)
            logger.info(f"Order cancelled: {order_id}")
            return True
        except PolyApiException as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    def cancel_all_orders(self) -> bool:
        """Cancel all open orders"""
        try:
            self.client.cancel_all()
            logger.info("All orders cancelled")
            return True
        except PolyApiException as e:
            logger.error(f"Failed to cancel all orders: {e}")
            return False

    def get_balance(self, asset_type: str = "USDC") -> Optional[float]:
        """
        Get balance for specific asset

        Args:
            asset_type: Asset type (default: USDC)
        """
        try:
            balances = self.client.get_balances()
            for balance in balances:
                if balance.get('asset') == asset_type:
                    return float(balance.get('balance', 0))
            return 0.0
        except PolyApiException as e:
            logger.error(f"Failed to get balance: {e}")
            return None

    def get_positions(self) -> List[Dict]:
        """Get all open positions"""
        try:
            return self.client.get_positions()
        except PolyApiException as e:
            logger.error(f"Failed to get positions: {e}")
            return []

    def is_connected(self) -> bool:
        """Check if client is connected"""
        try:
            self.client.get_server_time()
            return True
        except:
            return False
