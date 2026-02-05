"""
Configuration settings for Bitcoin Trading Bot using ICT Methods
"""

# Binance API Configuration
BINANCE_CONFIG = {
    "base_url": "https://api.binance.com",
    "testnet_url": "https://testnet.binance.vision",
    "use_testnet": False,
}

# Trading Pair Configuration
TRADING_CONFIG = {
    "symbol": "BTCUSDT",
    "timeframes": ["1h", "4h", "1d"],  # Multiple timeframe analysis
    "primary_timeframe": "1h",
    "higher_timeframe": "4h",
}

# ICT Strategy Parameters
ICT_CONFIG = {
    # Fair Value Gap (FVG) Settings
    "fvg": {
        "min_gap_percent": 0.1,  # Minimum gap size as percentage
        "lookback_periods": 50,  # How far back to look for FVGs
        "valid_for_periods": 20,  # How long an FVG remains valid
    },

    # Order Block Settings
    "order_block": {
        "lookback_periods": 20,
        "min_move_percent": 0.5,  # Minimum move after OB to be valid
        "valid_for_periods": 30,
    },

    # Liquidity Settings
    "liquidity": {
        "swing_lookback": 10,  # Periods to identify swing highs/lows
        "stop_hunt_threshold": 0.1,  # Percentage beyond swing for stop hunt
    },

    # Market Structure Settings
    "market_structure": {
        "swing_periods": 5,  # Periods to identify structure points
        "break_confirmation": 0.1,  # Percentage to confirm break
    },

    # Kill Zones (UTC times)
    "kill_zones": {
        "asian": {"start": "00:00", "end": "08:00"},
        "london": {"start": "07:00", "end": "16:00"},
        "new_york": {"start": "12:00", "end": "21:00"},
    },
}

# Backtesting Configuration
BACKTEST_CONFIG = {
    "initial_capital": 10000,
    "position_size_percent": 2,  # Risk 2% per trade
    "max_positions": 1,
    "commission_percent": 0.1,  # 0.1% trading fee
    "slippage_percent": 0.05,  # 0.05% slippage
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
}

# Risk Management
RISK_CONFIG = {
    "risk_reward_ratio": 2.0,  # Minimum R:R ratio
    "max_daily_loss_percent": 5,
    "max_drawdown_percent": 15,
    "trailing_stop_percent": 1.5,
}

# Data Storage
DATA_CONFIG = {
    "data_dir": "cache/historical",
    "cache_enabled": True,
    "cache_expiry_hours": 24,
}
