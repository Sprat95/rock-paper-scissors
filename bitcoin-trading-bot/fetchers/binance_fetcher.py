"""
Binance Historical Data Fetcher
Fetches OHLCV data from Binance API for backtesting
"""

import os
import json
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BINANCE_CONFIG, DATA_CONFIG, TRADING_CONFIG


class BinanceFetcher:
    """Fetches historical kline/candlestick data from Binance"""

    KLINE_INTERVALS = {
        "1m": 60,
        "3m": 180,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
        "2h": 7200,
        "4h": 14400,
        "6h": 21600,
        "8h": 28800,
        "12h": 43200,
        "1d": 86400,
        "3d": 259200,
        "1w": 604800,
    }

    def __init__(self):
        self.base_url = (
            BINANCE_CONFIG["testnet_url"]
            if BINANCE_CONFIG["use_testnet"]
            else BINANCE_CONFIG["base_url"]
        )
        self.data_dir = DATA_CONFIG["data_dir"]
        self._ensure_data_dir()

    def _ensure_data_dir(self):
        """Create data directory if it doesn't exist"""
        full_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            self.data_dir
        )
        os.makedirs(full_path, exist_ok=True)
        self.data_dir = full_path

    def _get_cache_path(self, symbol: str, interval: str, start_date: str, end_date: str) -> str:
        """Generate cache file path"""
        filename = f"{symbol}_{interval}_{start_date}_{end_date}.csv"
        return os.path.join(self.data_dir, filename)

    def _is_cache_valid(self, cache_path: str) -> bool:
        """Check if cache file exists and is not expired"""
        if not DATA_CONFIG["cache_enabled"]:
            return False

        if not os.path.exists(cache_path):
            return False

        file_time = datetime.fromtimestamp(os.path.getmtime(cache_path))
        expiry_time = datetime.now() - timedelta(hours=DATA_CONFIG["cache_expiry_hours"])
        return file_time > expiry_time

    def fetch_klines(
        self,
        symbol: str = None,
        interval: str = None,
        start_date: str = None,
        end_date: str = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        Fetch historical kline/candlestick data from Binance

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            interval: Kline interval (e.g., '1h', '4h', '1d')
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format
            limit: Maximum number of candles per request (max 1000)

        Returns:
            DataFrame with OHLCV data
        """
        symbol = symbol or TRADING_CONFIG["symbol"]
        interval = interval or TRADING_CONFIG["primary_timeframe"]

        # Check cache first
        cache_path = self._get_cache_path(symbol, interval, start_date, end_date)
        if self._is_cache_valid(cache_path):
            print(f"Loading cached data from {cache_path}")
            return pd.read_csv(cache_path, parse_dates=["timestamp"])

        print(f"Fetching {symbol} {interval} data from Binance...")

        # Convert dates to timestamps
        start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
        end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)

        all_klines = []
        current_start = start_ts

        while current_start < end_ts:
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": current_start,
                "endTime": end_ts,
                "limit": limit
            }

            try:
                response = requests.get(
                    f"{self.base_url}/api/v3/klines",
                    params=params,
                    timeout=30
                )
                response.raise_for_status()
                klines = response.json()

                if not klines:
                    break

                all_klines.extend(klines)

                # Move to next batch
                current_start = klines[-1][0] + 1

                # Rate limiting
                time.sleep(0.1)

                print(f"  Fetched {len(all_klines)} candles...")

            except requests.exceptions.RequestException as e:
                print(f"Error fetching data: {e}")
                raise

        # Convert to DataFrame
        df = self._klines_to_dataframe(all_klines)

        # Cache the data
        if DATA_CONFIG["cache_enabled"] and not df.empty:
            df.to_csv(cache_path, index=False)
            print(f"Data cached to {cache_path}")

        return df

    def _klines_to_dataframe(self, klines: list) -> pd.DataFrame:
        """Convert Binance klines to pandas DataFrame"""
        if not klines:
            return pd.DataFrame()

        df = pd.DataFrame(klines, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore"
        ])

        # Convert types
        df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms")
        df["open"] = pd.to_numeric(df["open"])
        df["high"] = pd.to_numeric(df["high"])
        df["low"] = pd.to_numeric(df["low"])
        df["close"] = pd.to_numeric(df["close"])
        df["volume"] = pd.to_numeric(df["volume"])

        # Keep only relevant columns
        df = df[["timestamp", "open", "high", "low", "close", "volume"]]

        return df

    def fetch_multiple_timeframes(
        self,
        symbol: str = None,
        timeframes: list = None,
        start_date: str = None,
        end_date: str = None
    ) -> dict:
        """
        Fetch data for multiple timeframes

        Returns:
            Dictionary with timeframe as key and DataFrame as value
        """
        symbol = symbol or TRADING_CONFIG["symbol"]
        timeframes = timeframes or TRADING_CONFIG["timeframes"]

        data = {}
        for tf in timeframes:
            print(f"\nFetching {tf} timeframe...")
            data[tf] = self.fetch_klines(
                symbol=symbol,
                interval=tf,
                start_date=start_date,
                end_date=end_date
            )

        return data

    def get_current_price(self, symbol: str = None) -> float:
        """Get current price for a symbol"""
        symbol = symbol or TRADING_CONFIG["symbol"]

        try:
            response = requests.get(
                f"{self.base_url}/api/v3/ticker/price",
                params={"symbol": symbol},
                timeout=10
            )
            response.raise_for_status()
            return float(response.json()["price"])
        except requests.exceptions.RequestException as e:
            print(f"Error fetching current price: {e}")
            raise


def main():
    """Test the data fetcher"""
    fetcher = BinanceFetcher()

    # Fetch historical data
    df = fetcher.fetch_klines(
        symbol="BTCUSDT",
        interval="1h",
        start_date="2024-01-01",
        end_date="2024-03-01"
    )

    print(f"\nFetched {len(df)} candles")
    print(f"\nSample data:")
    print(df.head(10))
    print(f"\nData range: {df['timestamp'].min()} to {df['timestamp'].max()}")


if __name__ == "__main__":
    main()
