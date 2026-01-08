"""
Configuration management for the Polymarket bot
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv
from pydantic import BaseModel, Field


class TradingConfig(BaseModel):
    max_position_size_usd: float = Field(default=1000)
    risk_per_trade: float = Field(default=0.02)
    min_profit_threshold: float = Field(default=0.025)
    max_slippage: float = Field(default=0.005)
    winner_fee: float = Field(default=0.02)
    taker_fee: float = Field(default=0.0)


class StrategyConfig(BaseModel):
    enabled: bool = Field(default=True)
    priority: int = Field(default=1)


class LatencyArbitrageConfig(StrategyConfig):
    markets: list[str] = Field(default=["BTC_15min", "ETH_15min", "SOL_15min"])
    min_edge: float = Field(default=0.03)
    max_latency_ms: int = Field(default=500)


class BinaryHedgingConfig(StrategyConfig):
    min_discount: float = Field(default=0.034)
    max_positions: int = Field(default=10)


class CombinatorialArbitrageConfig(StrategyConfig):
    min_edge: float = Field(default=0.02)
    max_markets_per_combo: int = Field(default=5)


class MarketMakingConfig(StrategyConfig):
    min_spread: float = Field(default=0.025)
    volatility_lookback_hours: list[int] = Field(default=[3, 24, 168, 720])


class AIPredictionsConfig(StrategyConfig):
    confidence_threshold: float = Field(default=0.7)


class RiskManagementConfig(BaseModel):
    max_total_exposure_usd: float = Field(default=10000)
    max_positions: int = Field(default=20)
    max_loss_per_day_usd: float = Field(default=500)
    emergency_stop_loss_pct: float = Field(default=0.1)


class TestingConfig(BaseModel):
    enabled: bool = Field(default=False)
    output_dir: str = Field(default="simulation_results")
    monitor_interval: int = Field(default=30)
    auto_resolve_timeout: int = Field(default=3600)
    generate_reports: bool = Field(default=True)


class Config:
    """Main configuration class"""

    def __init__(self, config_path: str = "config/config.yaml"):
        load_dotenv()

        self.config_path = Path(config_path)
        self._load_config()
        self._load_env_vars()

    def _load_config(self):
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            self.config_data = yaml.safe_load(f)

        # Parse configurations
        self.trading = TradingConfig(**self.config_data.get('trading', {}))
        self.testing = TestingConfig(**self.config_data.get('testing', {}))

        strategies = self.config_data.get('strategies', {})
        self.latency_arbitrage = LatencyArbitrageConfig(**strategies.get('latency_arbitrage', {}))
        self.binary_hedging = BinaryHedgingConfig(**strategies.get('binary_hedging', {}))
        self.combinatorial_arbitrage = CombinatorialArbitrageConfig(**strategies.get('combinatorial_arbitrage', {}))
        self.market_making = MarketMakingConfig(**strategies.get('market_making', {}))
        self.ai_predictions = AIPredictionsConfig(**strategies.get('ai_predictions', {}))

        self.risk_management = RiskManagementConfig(**self.config_data.get('risk_management', {}))
        self.data_feeds = self.config_data.get('data_feeds', {})
        self.logging_config = self.config_data.get('logging', {})

    def _load_env_vars(self):
        """Load environment variables"""
        self.polymarket_private_key = os.getenv('POLYMARKET_PRIVATE_KEY')
        self.polymarket_api_key = os.getenv('POLYMARKET_API_KEY')
        self.polymarket_secret = os.getenv('POLYMARKET_SECRET')
        self.polymarket_passphrase = os.getenv('POLYMARKET_PASSPHRASE')
        self.polymarket_chain_id = int(os.getenv('POLYMARKET_CHAIN_ID', '137'))

        self.binance_api_key = os.getenv('BINANCE_API_KEY')
        self.binance_api_secret = os.getenv('BINANCE_API_SECRET')

        self.coinbase_api_key = os.getenv('COINBASE_API_KEY')
        self.coinbase_api_secret = os.getenv('COINBASE_API_SECRET')

        # Trading modes
        self.testing_mode = os.getenv('TESTING_MODE', 'false').lower() == 'true'
        self.enable_live_trading = os.getenv('ENABLE_LIVE_TRADING', 'false').lower() == 'true'

        # Override from config if testing enabled in YAML
        if self.testing.enabled:
            self.testing_mode = True

        self.log_level = os.getenv('LOG_LEVEL', 'INFO')

    def get_enabled_strategies(self) -> list[tuple[str, StrategyConfig]]:
        """Get list of enabled strategies sorted by priority"""
        strategies = [
            ('latency_arbitrage', self.latency_arbitrage),
            ('binary_hedging', self.binary_hedging),
            ('combinatorial_arbitrage', self.combinatorial_arbitrage),
            ('market_making', self.market_making),
            ('ai_predictions', self.ai_predictions),
        ]

        enabled = [(name, cfg) for name, cfg in strategies if cfg.enabled]
        return sorted(enabled, key=lambda x: x[1].priority)


# Global config instance
config = None


def get_config(config_path: str = "config/config.yaml") -> Config:
    """Get or create global config instance"""
    global config
    if config is None:
        config = Config(config_path)
    return config
