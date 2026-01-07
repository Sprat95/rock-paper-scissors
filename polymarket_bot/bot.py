"""
Main Polymarket Bot Orchestrator
"""

import asyncio
from typing import List, Dict, Optional
from datetime import datetime
from .clients.polymarket_client import PolymarketClient
from .data_feeds.exchange_feeds import BinancePriceFeed, AggregatedPriceFeed
from .strategies.base_strategy import BaseStrategy
from .strategies.latency_arbitrage import LatencyArbitrageStrategy
from .strategies.binary_hedging import BinaryHedgingStrategy
from .strategies.combinatorial_arbitrage import CombinatorialArbitrageStrategy
from .strategies.market_making import MarketMakingStrategy
from .utils.config import get_config
from .utils.logger import get_logger
from .utils.risk_manager import RiskManager
from .utils.trade_simulator import TradeSimulator

logger = get_logger()


class PolymarketBot:
    """
    Main Polymarket trading bot

    Orchestrates multiple strategies and manages overall bot lifecycle
    """

    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize the bot"""
        self.config = get_config(config_path)
        self.running = False
        self.strategies: List[BaseStrategy] = []
        self.polymarket_client: Optional[PolymarketClient] = None
        self.price_feed: Optional[BinancePriceFeed] = None
        self.risk_manager: Optional[RiskManager] = None
        self.trade_simulator: Optional[TradeSimulator] = None

        self.starting_balance = 0.0
        self.current_balance = 0.0

    async def initialize(self):
        """Initialize all components"""
        logger.info("=" * 60)
        logger.info("Initializing Polymarket Multi-Strategy Bot")
        logger.info("=" * 60)

        # Initialize Polymarket client
        if not self.config.polymarket_private_key:
            raise ValueError("POLYMARKET_PRIVATE_KEY not set in environment")

        self.polymarket_client = PolymarketClient(
            private_key=self.config.polymarket_private_key,
            chain_id=self.config.polymarket_chain_id,
            api_key=self.config.polymarket_api_key,
            api_secret=self.config.polymarket_secret,
            api_passphrase=self.config.polymarket_passphrase
        )

        # Check connection
        if not self.polymarket_client.is_connected():
            raise ConnectionError("Failed to connect to Polymarket")

        logger.info("Polymarket client connected")

        # Get starting balance
        self.starting_balance = self.polymarket_client.get_balance() or 0.0
        self.current_balance = self.starting_balance
        logger.info(f"Account balance: ${self.current_balance:.2f}")

        # Initialize risk manager
        self.risk_manager = RiskManager(
            max_total_exposure_usd=self.config.risk_management.max_total_exposure_usd,
            max_positions=self.config.risk_management.max_positions,
            max_loss_per_day_usd=self.config.risk_management.max_loss_per_day_usd,
            emergency_stop_loss_pct=self.config.risk_management.emergency_stop_loss_pct,
            max_position_size_usd=self.config.trading.max_position_size_usd,
            risk_per_trade=self.config.trading.risk_per_trade
        )

        logger.info("Risk manager initialized")

        # Initialize trade simulator if in testing mode
        if self.config.testing_mode:
            self.trade_simulator = TradeSimulator(
                output_dir=self.config.testing.output_dir
            )
            logger.info("🧪 Testing mode enabled - Trade simulator initialized")

        # Initialize price feeds for latency arbitrage
        if self.config.latency_arbitrage.enabled:
            if not self.config.binance_api_key or not self.config.binance_api_secret:
                logger.warning("Binance API credentials not set - latency arbitrage disabled")
                self.config.latency_arbitrage.enabled = False
            else:
                self.price_feed = BinancePriceFeed(
                    api_key=self.config.binance_api_key,
                    api_secret=self.config.binance_api_secret
                )
                logger.info("Price feeds initialized")

        # Initialize strategies
        await self._initialize_strategies()

        logger.info(f"Initialized {len(self.strategies)} strategies")

        # Logging mode
        if self.config.testing_mode:
            logger.info("🧪 TESTING MODE - Trades will be logged and verified (NO execution)")
        elif self.config.enable_live_trading:
            logger.warning("⚠️  LIVE TRADING MODE - Real funds will be used")
        else:
            logger.info("📊 PAPER TRADING MODE - No real trades will be executed")

    async def _initialize_strategies(self):
        """Initialize enabled strategies"""
        enabled_strategies = self.config.get_enabled_strategies()

        for strategy_name, strategy_config in enabled_strategies:
            try:
                if strategy_name == 'latency_arbitrage' and self.price_feed:
                    strategy = LatencyArbitrageStrategy(
                        polymarket_client=self.polymarket_client,
                        config=vars(strategy_config),
                        price_feed=self.price_feed,
                        trade_simulator=self.trade_simulator
                    )
                    self.strategies.append(strategy)
                    logger.info(f"✓ {strategy_name} strategy initialized (Priority: {strategy_config.priority})")

                elif strategy_name == 'binary_hedging':
                    strategy = BinaryHedgingStrategy(
                        polymarket_client=self.polymarket_client,
                        config=vars(strategy_config),
                        trade_simulator=self.trade_simulator
                    )
                    self.strategies.append(strategy)
                    logger.info(f"✓ {strategy_name} strategy initialized (Priority: {strategy_config.priority})")

                elif strategy_name == 'combinatorial_arbitrage':
                    strategy = CombinatorialArbitrageStrategy(
                        polymarket_client=self.polymarket_client,
                        config=vars(strategy_config),
                        trade_simulator=self.trade_simulator
                    )
                    self.strategies.append(strategy)
                    logger.info(f"✓ {strategy_name} strategy initialized (Priority: {strategy_config.priority})")

                elif strategy_name == 'market_making':
                    strategy = MarketMakingStrategy(
                        polymarket_client=self.polymarket_client,
                        config=vars(strategy_config),
                        trade_simulator=self.trade_simulator
                    )
                    self.strategies.append(strategy)
                    logger.info(f"✓ {strategy_name} strategy initialized (Priority: {strategy_config.priority})")

                elif strategy_name == 'ai_predictions':
                    logger.info(f"⊘ {strategy_name} strategy skipped (requires training)")

            except Exception as e:
                logger.error(f"Failed to initialize {strategy_name}: {e}")

    async def start(self):
        """Start the bot"""
        self.running = True
        logger.info("\n" + "=" * 60)
        logger.info("🚀 Bot started")
        logger.info("=" * 60 + "\n")

        # Start price feeds if needed
        if self.price_feed:
            symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
            asyncio.create_task(self.price_feed.start(symbols))
            logger.info(f"Price feeds started for {symbols}")

        # Start all strategies
        tasks = []
        for strategy in self.strategies:
            task = asyncio.create_task(strategy.run())
            tasks.append(task)

        # Start monitoring task
        tasks.append(asyncio.create_task(self._monitor_loop()))

        # Start testing mode monitoring task if applicable
        if self.testing_mode and self.trade_simulator:
            tasks.append(asyncio.create_task(self._monitor_simulated_trades()))

        # Wait for all tasks
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Bot tasks cancelled")

    async def stop(self):
        """Stop the bot"""
        self.running = False

        logger.info("\n" + "=" * 60)
        logger.info("Stopping bot...")
        logger.info("=" * 60)

        # Stop strategies
        for strategy in self.strategies:
            await strategy.stop()

        # Stop price feeds
        if self.price_feed:
            await self.price_feed.stop()

        # Generate testing mode report if applicable
        if self.testing_mode and self.trade_simulator:
            self.trade_simulator.save_final_report()
            self.trade_simulator.export_to_csv()

        # Print final summary
        await self._print_final_summary()

        logger.info("Bot stopped")

    async def _monitor_loop(self):
        """Monitor bot performance and risk"""
        while self.running:
            try:
                await asyncio.sleep(60)  # Check every minute

                # Update balance
                current_balance = self.polymarket_client.get_balance() or 0.0
                self.current_balance = current_balance

                # Check emergency stop
                self.risk_manager.check_emergency_stop(
                    self.current_balance,
                    self.starting_balance
                )

                # Log summary every 5 minutes
                if int(datetime.now().timestamp()) % 300 == 0:  # Every 5 minutes
                    await self._print_status()

            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(60)

    async def _monitor_simulated_trades(self):
        """Monitor and resolve simulated trades in testing mode"""
        logger.info("Starting simulated trades monitor...")

        while self.running:
            try:
                await asyncio.sleep(self.config.testing.monitor_interval)

                # Check pending and monitoring trades for resolution
                pending = self.trade_simulator.get_pending_trades()
                monitoring = self.trade_simulator.get_monitoring_trades()

                for trade in pending + monitoring:
                    try:
                        # Get current price to check if market resolved
                        current_price = self.polymarket_client.get_midpoint(trade.token_id)

                        if current_price is None:
                            continue

                        # Check if market resolved (price at 0 or 1)
                        if current_price >= 0.99:
                            # Resolved to YES/UP
                            self.trade_simulator.resolve_trade(trade, "YES", 1.0)
                        elif current_price <= 0.01:
                            # Resolved to NO/DOWN
                            self.trade_simulator.resolve_trade(trade, "NO", 0.0)

                    except Exception as e:
                        logger.error(f"Error checking trade {trade.trade_id}: {e}")

                # Generate periodic reports
                if self.config.testing.generate_reports:
                    stats = self.trade_simulator.get_statistics()
                    if stats['resolved_trades'] > 0 and stats['resolved_trades'] % 10 == 0:
                        logger.info(self.trade_simulator.generate_report())

            except Exception as e:
                logger.error(f"Error in simulated trades monitor: {e}")
                await asyncio.sleep(self.config.testing.monitor_interval)

    async def _print_status(self):
        """Print current bot status"""
        logger.info("\n" + "=" * 60)
        logger.info("Bot Status Update")
        logger.info("=" * 60)

        # Account info
        pnl = self.current_balance - self.starting_balance
        pnl_pct = (pnl / self.starting_balance * 100) if self.starting_balance > 0 else 0

        logger.info(f"Balance: ${self.current_balance:.2f} (Start: ${self.starting_balance:.2f})")
        logger.info(f"PnL: ${pnl:.2f} ({pnl_pct:+.2f}%)")

        # Risk metrics
        risk_metrics = self.risk_manager.get_risk_metrics()
        logger.info(f"Total Exposure: ${risk_metrics['total_exposure']:.2f} ({risk_metrics['exposure_pct']:.1f}%)")
        logger.info(f"Today PnL: ${risk_metrics['today_pnl']:.2f}")

        # Strategy performance
        logger.info("\nStrategy Performance:")
        for strategy in self.strategies:
            perf = strategy.get_performance_summary()
            logger.info(
                f"  {perf['strategy']}: "
                f"Trades: {perf['total_trades']}, "
                f"Win Rate: {perf['win_rate']:.1f}%, "
                f"PnL: ${perf['net_pnl']:.2f}, "
                f"Open: {perf['open_positions']}"
            )

        # Testing mode statistics
        if self.testing_mode and self.trade_simulator:
            stats = self.trade_simulator.get_statistics()
            logger.info("\n🧪 Testing Mode Statistics:")
            logger.info(f"  Total Simulated Trades: {stats['total_trades']}")
            logger.info(f"  Resolved: {stats['resolved_trades']}, Pending: {stats['pending_trades']}")
            logger.info(f"  Win Rate: {stats['win_rate']:.2f}%")
            logger.info(f"  Hypothetical PnL: ${stats['total_pnl']:.2f}")
            logger.info(f"  Avg PnL/Trade: ${stats['avg_pnl_per_trade']:.2f}")

        logger.info("=" * 60 + "\n")

    async def _print_final_summary(self):
        """Print final performance summary"""
        logger.info("\n" + "=" * 60)
        logger.info("Final Performance Summary")
        logger.info("=" * 60)

        # Overall performance
        total_pnl = self.current_balance - self.starting_balance
        total_pnl_pct = (total_pnl / self.starting_balance * 100) if self.starting_balance > 0 else 0

        logger.info(f"Starting Balance: ${self.starting_balance:.2f}")
        logger.info(f"Ending Balance: ${self.current_balance:.2f}")
        logger.info(f"Total PnL: ${total_pnl:.2f} ({total_pnl_pct:+.2f}%)")

        # Strategy breakdown
        logger.info("\nStrategy Breakdown:")
        for strategy in self.strategies:
            perf = strategy.get_performance_summary()
            logger.info(
                f"\n{perf['strategy']}:"
                f"\n  Total Trades: {perf['total_trades']}"
                f"\n  Win Rate: {perf['win_rate']:.2f}%"
                f"\n  Total PnL: ${perf['total_pnl']:.2f}"
                f"\n  Fees Paid: ${perf['total_fees']:.2f}"
                f"\n  Net PnL: ${perf['net_pnl']:.2f}"
                f"\n  Avg Profit/Trade: ${perf['avg_profit']:.2f}"
                f"\n  Max Drawdown: ${perf['max_drawdown']:.2f}"
            )

        logger.info("\n" + "=" * 60)

    def get_status(self) -> Dict:
        """Get current bot status"""
        return {
            'running': self.running,
            'balance': self.current_balance,
            'starting_balance': self.starting_balance,
            'pnl': self.current_balance - self.starting_balance,
            'strategies': [s.get_performance_summary() for s in self.strategies],
            'risk_metrics': self.risk_manager.get_risk_metrics()
        }


async def run_bot(config_path: str = "config/config.yaml"):
    """Run the Polymarket bot"""
    bot = PolymarketBot(config_path)

    try:
        await bot.initialize()
        await bot.start()
    except KeyboardInterrupt:
        logger.info("\nReceived shutdown signal")
    except Exception as e:
        logger.error(f"Bot error: {e}")
        raise
    finally:
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(run_bot())
