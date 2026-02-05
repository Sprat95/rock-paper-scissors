"""
ICT (Inner Circle Trader) Strategy Implementation
Implements key ICT concepts for Bitcoin trading:
- Fair Value Gaps (FVG)
- Order Blocks (OB)
- Liquidity Sweeps
- Market Structure (Break of Structure, Change of Character)
- Kill Zones
"""

import pandas as pd
import numpy as np
from datetime import datetime, time
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ICT_CONFIG


class Bias(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class SignalType(Enum):
    LONG = "long"
    SHORT = "short"
    NONE = "none"


@dataclass
class FairValueGap:
    """Represents a Fair Value Gap"""
    index: int
    timestamp: datetime
    type: str  # 'bullish' or 'bearish'
    top: float
    bottom: float
    midpoint: float
    filled: bool = False
    fill_percent: float = 0.0


@dataclass
class OrderBlock:
    """Represents an Order Block"""
    index: int
    timestamp: datetime
    type: str  # 'bullish' or 'bearish'
    high: float
    low: float
    body_high: float
    body_low: float
    mitigated: bool = False


@dataclass
class LiquidityLevel:
    """Represents a liquidity level (swing high/low)"""
    index: int
    timestamp: datetime
    type: str  # 'high' or 'low'
    price: float
    swept: bool = False


@dataclass
class TradeSignal:
    """Represents a trade signal"""
    index: int
    timestamp: datetime
    signal_type: SignalType
    entry_price: float
    stop_loss: float
    take_profit: float
    reason: str
    confidence: float  # 0-1


class ICTStrategy:
    """
    ICT Strategy Implementation
    Uses multiple ICT concepts to identify high-probability trade setups
    """

    def __init__(self, config: dict = None):
        self.config = config or ICT_CONFIG
        self.fvg_list: list[FairValueGap] = []
        self.order_blocks: list[OrderBlock] = []
        self.liquidity_levels: list[LiquidityLevel] = []
        self.market_bias: Bias = Bias.NEUTRAL

    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Run full ICT analysis on the data

        Args:
            df: DataFrame with OHLCV data

        Returns:
            DataFrame with ICT indicators added
        """
        df = df.copy()

        # Calculate all ICT indicators
        df = self._identify_swing_points(df)
        df = self._identify_market_structure(df)
        df = self._identify_fair_value_gaps(df)
        df = self._identify_order_blocks(df)
        df = self._identify_liquidity_levels(df)
        df = self._identify_kill_zones(df)
        df = self._calculate_bias(df)

        return df

    def _identify_swing_points(self, df: pd.DataFrame) -> pd.DataFrame:
        """Identify swing highs and swing lows"""
        periods = self.config["market_structure"]["swing_periods"]

        df["swing_high"] = False
        df["swing_low"] = False

        for i in range(periods, len(df) - periods):
            # Swing high: highest high in the range
            if df["high"].iloc[i] == df["high"].iloc[i - periods:i + periods + 1].max():
                df.loc[df.index[i], "swing_high"] = True

            # Swing low: lowest low in the range
            if df["low"].iloc[i] == df["low"].iloc[i - periods:i + periods + 1].min():
                df.loc[df.index[i], "swing_low"] = True

        return df

    def _identify_market_structure(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Identify market structure:
        - Higher Highs (HH), Higher Lows (HL) for uptrend
        - Lower Highs (LH), Lower Lows (LL) for downtrend
        - Break of Structure (BOS)
        - Change of Character (CHoCH)
        """
        df["structure"] = ""
        df["bos"] = False
        df["choch"] = False

        last_swing_high = None
        last_swing_low = None
        prev_swing_high = None
        prev_swing_low = None
        current_trend = "neutral"

        for i in range(len(df)):
            if df["swing_high"].iloc[i]:
                prev_swing_high = last_swing_high
                last_swing_high = (i, df["high"].iloc[i])

                if prev_swing_high:
                    if last_swing_high[1] > prev_swing_high[1]:
                        df.loc[df.index[i], "structure"] = "HH"
                        if current_trend == "bearish":
                            df.loc[df.index[i], "choch"] = True
                            current_trend = "bullish"
                        elif current_trend == "bullish":
                            df.loc[df.index[i], "bos"] = True
                    else:
                        df.loc[df.index[i], "structure"] = "LH"
                        if current_trend == "bullish":
                            df.loc[df.index[i], "choch"] = True
                            current_trend = "bearish"
                        elif current_trend == "bearish":
                            df.loc[df.index[i], "bos"] = True

            if df["swing_low"].iloc[i]:
                prev_swing_low = last_swing_low
                last_swing_low = (i, df["low"].iloc[i])

                if prev_swing_low:
                    if last_swing_low[1] > prev_swing_low[1]:
                        df.loc[df.index[i], "structure"] = "HL"
                    else:
                        df.loc[df.index[i], "structure"] = "LL"

        return df

    def _identify_fair_value_gaps(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Identify Fair Value Gaps (FVG)
        Bullish FVG: Gap between candle 1 high and candle 3 low (with candle 2 in between)
        Bearish FVG: Gap between candle 1 low and candle 3 high
        """
        df["fvg_bullish"] = False
        df["fvg_bearish"] = False
        df["fvg_top"] = np.nan
        df["fvg_bottom"] = np.nan

        min_gap_pct = self.config["fvg"]["min_gap_percent"] / 100
        self.fvg_list = []

        for i in range(2, len(df)):
            # Bullish FVG: Previous candle's high < Current candle's low
            gap_up = df["low"].iloc[i] - df["high"].iloc[i - 2]
            if gap_up > 0 and gap_up / df["close"].iloc[i] > min_gap_pct:
                df.loc[df.index[i], "fvg_bullish"] = True
                df.loc[df.index[i], "fvg_bottom"] = df["high"].iloc[i - 2]
                df.loc[df.index[i], "fvg_top"] = df["low"].iloc[i]

                fvg = FairValueGap(
                    index=i,
                    timestamp=df["timestamp"].iloc[i],
                    type="bullish",
                    top=df["low"].iloc[i],
                    bottom=df["high"].iloc[i - 2],
                    midpoint=(df["low"].iloc[i] + df["high"].iloc[i - 2]) / 2
                )
                self.fvg_list.append(fvg)

            # Bearish FVG: Previous candle's low > Current candle's high
            gap_down = df["low"].iloc[i - 2] - df["high"].iloc[i]
            if gap_down > 0 and gap_down / df["close"].iloc[i] > min_gap_pct:
                df.loc[df.index[i], "fvg_bearish"] = True
                df.loc[df.index[i], "fvg_top"] = df["low"].iloc[i - 2]
                df.loc[df.index[i], "fvg_bottom"] = df["high"].iloc[i]

                fvg = FairValueGap(
                    index=i,
                    timestamp=df["timestamp"].iloc[i],
                    type="bearish",
                    top=df["low"].iloc[i - 2],
                    bottom=df["high"].iloc[i],
                    midpoint=(df["low"].iloc[i - 2] + df["high"].iloc[i]) / 2
                )
                self.fvg_list.append(fvg)

        return df

    def _identify_order_blocks(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Identify Order Blocks
        Bullish OB: Last bearish candle before a significant up move
        Bearish OB: Last bullish candle before a significant down move
        """
        df["ob_bullish"] = False
        df["ob_bearish"] = False
        df["ob_high"] = np.nan
        df["ob_low"] = np.nan

        lookback = self.config["order_block"]["lookback_periods"]
        min_move_pct = self.config["order_block"]["min_move_percent"] / 100
        self.order_blocks = []

        for i in range(lookback, len(df)):
            current_close = df["close"].iloc[i]

            # Look for bullish order block
            for j in range(i - 1, max(i - lookback, 0), -1):
                # Find bearish candle (close < open)
                if df["close"].iloc[j] < df["open"].iloc[j]:
                    # Check if price moved significantly up after this candle
                    max_price_after = df["high"].iloc[j + 1:i + 1].max()
                    move_pct = (max_price_after - df["high"].iloc[j]) / df["close"].iloc[j]

                    if move_pct > min_move_pct:
                        df.loc[df.index[j], "ob_bullish"] = True
                        df.loc[df.index[j], "ob_high"] = df["high"].iloc[j]
                        df.loc[df.index[j], "ob_low"] = df["low"].iloc[j]

                        ob = OrderBlock(
                            index=j,
                            timestamp=df["timestamp"].iloc[j],
                            type="bullish",
                            high=df["high"].iloc[j],
                            low=df["low"].iloc[j],
                            body_high=max(df["open"].iloc[j], df["close"].iloc[j]),
                            body_low=min(df["open"].iloc[j], df["close"].iloc[j])
                        )
                        if ob not in self.order_blocks:
                            self.order_blocks.append(ob)
                        break

            # Look for bearish order block
            for j in range(i - 1, max(i - lookback, 0), -1):
                # Find bullish candle (close > open)
                if df["close"].iloc[j] > df["open"].iloc[j]:
                    # Check if price moved significantly down after this candle
                    min_price_after = df["low"].iloc[j + 1:i + 1].min()
                    move_pct = (df["low"].iloc[j] - min_price_after) / df["close"].iloc[j]

                    if move_pct > min_move_pct:
                        df.loc[df.index[j], "ob_bearish"] = True
                        df.loc[df.index[j], "ob_high"] = df["high"].iloc[j]
                        df.loc[df.index[j], "ob_low"] = df["low"].iloc[j]

                        ob = OrderBlock(
                            index=j,
                            timestamp=df["timestamp"].iloc[j],
                            type="bearish",
                            high=df["high"].iloc[j],
                            low=df["low"].iloc[j],
                            body_high=max(df["open"].iloc[j], df["close"].iloc[j]),
                            body_low=min(df["open"].iloc[j], df["close"].iloc[j])
                        )
                        if ob not in self.order_blocks:
                            self.order_blocks.append(ob)
                        break

        return df

    def _identify_liquidity_levels(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Identify liquidity levels (areas where stop losses likely cluster)
        - Equal highs/lows
        - Recent swing highs/lows
        """
        df["liquidity_high"] = np.nan
        df["liquidity_low"] = np.nan
        df["liquidity_swept_high"] = False
        df["liquidity_swept_low"] = False

        lookback = self.config["liquidity"]["swing_lookback"]
        threshold = self.config["liquidity"]["stop_hunt_threshold"] / 100
        self.liquidity_levels = []

        # Identify liquidity at swing points
        for i in range(lookback, len(df)):
            if df["swing_high"].iloc[i]:
                df.loc[df.index[i], "liquidity_high"] = df["high"].iloc[i]
                self.liquidity_levels.append(LiquidityLevel(
                    index=i,
                    timestamp=df["timestamp"].iloc[i],
                    type="high",
                    price=df["high"].iloc[i]
                ))

            if df["swing_low"].iloc[i]:
                df.loc[df.index[i], "liquidity_low"] = df["low"].iloc[i]
                self.liquidity_levels.append(LiquidityLevel(
                    index=i,
                    timestamp=df["timestamp"].iloc[i],
                    type="low",
                    price=df["low"].iloc[i]
                ))

        # Check for liquidity sweeps
        for i, level in enumerate(self.liquidity_levels):
            for j in range(level.index + 1, len(df)):
                if level.type == "high":
                    # Check if price swept above and closed back below
                    if df["high"].iloc[j] > level.price * (1 + threshold):
                        if df["close"].iloc[j] < level.price:
                            df.loc[df.index[j], "liquidity_swept_high"] = True
                            level.swept = True
                            break
                else:
                    # Check if price swept below and closed back above
                    if df["low"].iloc[j] < level.price * (1 - threshold):
                        if df["close"].iloc[j] > level.price:
                            df.loc[df.index[j], "liquidity_swept_low"] = True
                            level.swept = True
                            break

        return df

    def _identify_kill_zones(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Identify ICT Kill Zones (optimal trading times)
        - Asian Session
        - London Session
        - New York Session
        """
        df["in_asian_kz"] = False
        df["in_london_kz"] = False
        df["in_ny_kz"] = False

        for kz_name, kz_times in self.config["kill_zones"].items():
            start_time = datetime.strptime(kz_times["start"], "%H:%M").time()
            end_time = datetime.strptime(kz_times["end"], "%H:%M").time()

            for i in range(len(df)):
                candle_time = df["timestamp"].iloc[i].time()

                if start_time <= end_time:
                    in_zone = start_time <= candle_time <= end_time
                else:
                    # Handle overnight zones
                    in_zone = candle_time >= start_time or candle_time <= end_time

                if kz_name == "asian":
                    df.loc[df.index[i], "in_asian_kz"] = in_zone
                elif kz_name == "london":
                    df.loc[df.index[i], "in_london_kz"] = in_zone
                elif kz_name == "new_york":
                    df.loc[df.index[i], "in_ny_kz"] = in_zone

        return df

    def _calculate_bias(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate overall market bias based on structure"""
        df["bias"] = "neutral"

        for i in range(1, len(df)):
            # Count recent structure points
            lookback = min(50, i)
            recent_structure = df["structure"].iloc[i - lookback:i + 1]

            hh_count = (recent_structure == "HH").sum()
            hl_count = (recent_structure == "HL").sum()
            lh_count = (recent_structure == "LH").sum()
            ll_count = (recent_structure == "LL").sum()

            bullish_score = hh_count + hl_count
            bearish_score = lh_count + ll_count

            if bullish_score > bearish_score + 1:
                df.loc[df.index[i], "bias"] = "bullish"
            elif bearish_score > bullish_score + 1:
                df.loc[df.index[i], "bias"] = "bearish"
            else:
                df.loc[df.index[i], "bias"] = "neutral"

        return df

    def generate_signals(self, df: pd.DataFrame) -> list[TradeSignal]:
        """
        Generate trade signals based on ICT concepts

        Entry criteria:
        1. Market structure bias alignment
        2. Price in a valid FVG or Order Block
        3. In a Kill Zone (optional but increases confidence)
        4. Recent liquidity sweep (optional but increases confidence)
        """
        signals = []

        for i in range(50, len(df)):
            signal = self._check_for_signal(df, i)
            if signal and signal.signal_type != SignalType.NONE:
                signals.append(signal)

        return signals

    def _check_for_signal(self, df: pd.DataFrame, index: int) -> Optional[TradeSignal]:
        """Check if there's a valid trade signal at the given index"""
        row = df.iloc[index]
        bias = row["bias"]
        confidence = 0.5

        # Check for bullish setup
        if bias == "bullish":
            # Check if price is at a bullish FVG
            for fvg in self.fvg_list:
                if fvg.type == "bullish" and not fvg.filled:
                    if fvg.bottom <= row["low"] <= fvg.top:
                        confidence += 0.15

                        # Check for additional confluence
                        if row["in_london_kz"] or row["in_ny_kz"]:
                            confidence += 0.1
                        if row["liquidity_swept_low"]:
                            confidence += 0.15

                        # Calculate entry, stop, and target
                        entry = row["close"]
                        stop_loss = fvg.bottom * 0.995  # Just below FVG
                        risk = entry - stop_loss
                        take_profit = entry + (risk * 2)  # 2R target

                        if confidence >= 0.6:
                            return TradeSignal(
                                index=index,
                                timestamp=row["timestamp"],
                                signal_type=SignalType.LONG,
                                entry_price=entry,
                                stop_loss=stop_loss,
                                take_profit=take_profit,
                                reason=f"Bullish FVG entry with {bias} bias",
                                confidence=min(confidence, 1.0)
                            )

            # Check if price is at a bullish Order Block
            for ob in self.order_blocks:
                if ob.type == "bullish" and not ob.mitigated:
                    if ob.low <= row["low"] <= ob.high:
                        confidence += 0.15

                        if row["in_london_kz"] or row["in_ny_kz"]:
                            confidence += 0.1
                        if row["liquidity_swept_low"]:
                            confidence += 0.15

                        entry = row["close"]
                        stop_loss = ob.low * 0.995
                        risk = entry - stop_loss
                        take_profit = entry + (risk * 2)

                        if confidence >= 0.6:
                            return TradeSignal(
                                index=index,
                                timestamp=row["timestamp"],
                                signal_type=SignalType.LONG,
                                entry_price=entry,
                                stop_loss=stop_loss,
                                take_profit=take_profit,
                                reason=f"Bullish Order Block entry with {bias} bias",
                                confidence=min(confidence, 1.0)
                            )

        # Check for bearish setup
        elif bias == "bearish":
            # Check if price is at a bearish FVG
            for fvg in self.fvg_list:
                if fvg.type == "bearish" and not fvg.filled:
                    if fvg.bottom <= row["high"] <= fvg.top:
                        confidence += 0.15

                        if row["in_london_kz"] or row["in_ny_kz"]:
                            confidence += 0.1
                        if row["liquidity_swept_high"]:
                            confidence += 0.15

                        entry = row["close"]
                        stop_loss = fvg.top * 1.005  # Just above FVG
                        risk = stop_loss - entry
                        take_profit = entry - (risk * 2)

                        if confidence >= 0.6:
                            return TradeSignal(
                                index=index,
                                timestamp=row["timestamp"],
                                signal_type=SignalType.SHORT,
                                entry_price=entry,
                                stop_loss=stop_loss,
                                take_profit=take_profit,
                                reason=f"Bearish FVG entry with {bias} bias",
                                confidence=min(confidence, 1.0)
                            )

            # Check if price is at a bearish Order Block
            for ob in self.order_blocks:
                if ob.type == "bearish" and not ob.mitigated:
                    if ob.low <= row["high"] <= ob.high:
                        confidence += 0.15

                        if row["in_london_kz"] or row["in_ny_kz"]:
                            confidence += 0.1
                        if row["liquidity_swept_high"]:
                            confidence += 0.15

                        entry = row["close"]
                        stop_loss = ob.high * 1.005
                        risk = stop_loss - entry
                        take_profit = entry - (risk * 2)

                        if confidence >= 0.6:
                            return TradeSignal(
                                index=index,
                                timestamp=row["timestamp"],
                                signal_type=SignalType.SHORT,
                                entry_price=entry,
                                stop_loss=stop_loss,
                                take_profit=take_profit,
                                reason=f"Bearish Order Block entry with {bias} bias",
                                confidence=min(confidence, 1.0)
                            )

        return None

    def get_analysis_summary(self, df: pd.DataFrame) -> dict:
        """Get a summary of the ICT analysis"""
        return {
            "total_candles": len(df),
            "bullish_fvgs": len([f for f in self.fvg_list if f.type == "bullish"]),
            "bearish_fvgs": len([f for f in self.fvg_list if f.type == "bearish"]),
            "bullish_obs": len([o for o in self.order_blocks if o.type == "bullish"]),
            "bearish_obs": len([o for o in self.order_blocks if o.type == "bearish"]),
            "liquidity_levels": len(self.liquidity_levels),
            "swept_levels": len([l for l in self.liquidity_levels if l.swept]),
            "current_bias": df["bias"].iloc[-1] if len(df) > 0 else "neutral",
            "bos_count": df["bos"].sum(),
            "choch_count": df["choch"].sum(),
        }


def main():
    """Test the ICT strategy"""
    # Create sample data for testing
    import numpy as np

    dates = pd.date_range(start="2024-01-01", periods=100, freq="1h")
    np.random.seed(42)

    # Generate realistic price data
    price = 42000
    prices = [price]
    for _ in range(99):
        change = np.random.randn() * 100
        price = max(price + change, 30000)
        prices.append(price)

    df = pd.DataFrame({
        "timestamp": dates,
        "open": prices,
        "high": [p + abs(np.random.randn() * 50) for p in prices],
        "low": [p - abs(np.random.randn() * 50) for p in prices],
        "close": [p + np.random.randn() * 30 for p in prices],
        "volume": [np.random.randint(100, 1000) for _ in prices]
    })

    # Run ICT analysis
    strategy = ICTStrategy()
    df_analyzed = strategy.analyze(df)

    # Print summary
    summary = strategy.get_analysis_summary(df_analyzed)
    print("\nICT Analysis Summary:")
    print("-" * 40)
    for key, value in summary.items():
        print(f"{key}: {value}")

    # Generate signals
    signals = strategy.generate_signals(df_analyzed)
    print(f"\nGenerated {len(signals)} trade signals")

    for signal in signals[:5]:
        print(f"\n{signal.signal_type.value.upper()} Signal:")
        print(f"  Time: {signal.timestamp}")
        print(f"  Entry: ${signal.entry_price:.2f}")
        print(f"  Stop: ${signal.stop_loss:.2f}")
        print(f"  Target: ${signal.take_profit:.2f}")
        print(f"  Confidence: {signal.confidence:.1%}")
        print(f"  Reason: {signal.reason}")


if __name__ == "__main__":
    main()
