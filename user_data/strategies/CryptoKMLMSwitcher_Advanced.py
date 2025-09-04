# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these libs ---
import numpy as np  # noqa
import pandas as pd  # noqa
from pandas import DataFrame
from typing import Dict, List
from functools import reduce

from freqtrade.strategy import (
    BooleanParameter,
    CategoricalParameter,
    DecimalParameter,
    IStrategy,
    IntParameter,
)

# --------------------------------
# Add your lib to import here
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import merge_informative_pair


class CryptoKMLMSwitcherAdvanced(IStrategy):
    """
    Crypto KMLM Switcher Strategy - ADVANCED VERSION
    
    Implements the sophisticated switching logic from defsymphony.clj
    "Simons KMLM switcher (single pops)| BT 4/13/22 = A.R. 466% / D.D. 22%"
    
    Core Logic:
    1. Multi-pair RSI monitoring (like the original's multi-asset approach)
    2. Defensive switching to stable pairs when major pairs are overbought
    3. Aggressive switching to volatile pairs when major pairs are oversold
    4. Dynamic position sizing based on market conditions
    5. Sophisticated nested decision tree for allocation
    
    Key Features:
    - Defensive mode: Switch to stable pairs (like UVXY in original)
    - Aggressive mode: Switch to volatile pairs (like TECL, SOXL, SPXL)
    - Risk management through RSI thresholds
    - Multi-tier decision tree for optimal allocation
    """

    INTERFACE_VERSION = 3
    timeframe = "5m"  # Optimal timeframe for crypto switching
    
    # ROI table - more realistic for crypto volatility
    minimal_roi = {
        "0": 0.18,     # 6% profit target
        "30": 0.12,    # 4% after 30 minutes
        "60": 0.09,    # 3% after 1 hour
        "120": 0.06,   # 2% after 2 hours
        "240": 0.045,  # 1.5% after 4 hours
        "480": 0.03,   # 1% after 8 hours
    }

    # Stoploss - more appropriate for crypto volatility
    stoploss = -0.90  # 90% stop loss - effectively disabled (let ROI and trailing stop handle exits)
    use_custom_stoploss = False  # Disable custom stoploss to avoid regime-based exits

    # Disable shorting for spot trading
    can_short = False

    # Trailing stoploss - less aggressive
    trailing_stop = True
    trailing_stop_positive = 0.015  # 1.5% trailing stop
    trailing_stop_positive_offset = 0.025  # 2.5% offset
    trailing_only_offset_is_reached = True

    # Run "populate_indicators()" only for new candle
    process_only_new_candles = True

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 30

    # Strategy parameters - optimized for crypto
    rsi_window = IntParameter(10, 15, default=12, space="buy")
    rsi_overbought_high = IntParameter(75, 85, default=78, space="sell")
    rsi_overbought_medium = IntParameter(70, 80, default=72, space="sell")
    rsi_oversold = IntParameter(20, 40, default=35, space="buy")  # Relaxed from 28 to 35
    
    # Volume confirmation
    volume_multiplier = DecimalParameter(1.0, 2.0, default=1.2, space="buy")  # Relaxed from 1.5 to 1.2
    
    # Position sizing parameters
    max_risk_per_trade = DecimalParameter(0.02, 0.08, default=0.05, space="buy")
    defensive_allocation = DecimalParameter(0.3, 0.7, default=0.5, space="buy")
    aggressive_allocation = DecimalParameter(0.6, 0.9, default=0.8, space="buy")

    # Exit signal parameters - easily editable
    enable_exit_signals = False  # Set to False to disable exit signals (main source of losses)
    exit_rsi_threshold = 92  # RSI level for exit (higher = less exits)
    exit_trend_drop = 0.88  # Price drop below SMA20 for trend exit (lower = less exits)
    exit_extreme_drop = 0.80  # Extreme price drop for exit (lower = less exits)
    exit_volume_spike = 2.5  # Volume ratio for panic selling exit (higher = less exits)
    exit_candle_drop = 0.85  # Intra-candle drop for volume spike exit (lower = less exits)
    
    # Regime change exit parameters - reduce these to minimize regime change losses
    enable_regime_exits = False  # Set to False to disable regime change exits (bleeding the most)
    regime_exit_profit_threshold = 0.12  # Exit defensive positions when aggressive (higher = less exits)
    regime_exit_loss_threshold = -0.20  # Exit aggressive positions when defensive (lower = less exits)
    
    # Timeout parameters
    enable_trade_timeout = False  # Set to False to disable timeout exits
    trade_timeout_hours = 72  # Hours before timeout exit (higher = longer trades)

    def informative_pairs(self):
        """
        Define additional, informative pair/interval combinations to be cached from the exchange.
        These represent the "market leaders" that drive switching decisions.
        """
        return [
            ("BTC/USDT", "5m"),  # Market leader (like SPY in original)
            ("ETH/USDT", "5m"),  # Tech leader (like QQQE in original)
            ("BNB/USDT", "5m"),  # Exchange token (like XLK in original)
            ("ADA/USDT", "5m"),  # Volatile alt (like TECL in original)
            ("DOT/USDT", "5m"),  # Volatile alt (like SOXL in original)
            ("SOL/USDT", "5m"),  # Volatile alt (like SPXL in original)
            #("AVAX/USDT", "5m"), # Volatile alt (like LABU in original)
        ]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds several different TA indicators to the given DataFrame
        """
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_window.value)
        
        # Moving averages for trend detection
        dataframe['sma_20'] = ta.SMA(dataframe, timeperiod=20)
        dataframe['sma_50'] = ta.SMA(dataframe, timeperiod=50)
        dataframe['sma_200'] = ta.SMA(dataframe, timeperiod=200)
        
        # Bollinger Bands
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']
        dataframe['bb_percent'] = (dataframe['close'] - dataframe['bb_lowerband']) / (dataframe['bb_upperband'] - dataframe['bb_lowerband'])
        
        # Volume indicators
        dataframe['volume_mean'] = dataframe['volume'].rolling(window=20).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_mean']
        
        # Market conditions
        dataframe['bullish_trend'] = dataframe['sma_20'] > dataframe['sma_50']
        dataframe['bearish_trend'] = dataframe['sma_20'] < dataframe['sma_50']
        dataframe['strong_trend'] = dataframe['sma_50'] > dataframe['sma_200']
        
        # RSI conditions
        dataframe['rsi_oversold'] = dataframe['rsi'] < self.rsi_oversold.value
        dataframe['rsi_overbought_medium'] = dataframe['rsi'] > self.rsi_overbought_medium.value
        dataframe['rsi_overbought_high'] = dataframe['rsi'] > self.rsi_overbought_high.value
        
        # Volatility
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['high_volatility'] = dataframe['atr'] > dataframe['atr'].rolling(window=20).mean() * 1.5
        
        # Market regime detection
        dataframe['market_regime'] = self.detect_market_regime(dataframe)
        
        return dataframe

    def detect_market_regime(self, dataframe: DataFrame) -> pd.Series:
        """
        Detect market regime based on RSI and volatility
        Returns: 0 = Defensive, 1 = Neutral, 2 = Aggressive
        """
        regime = pd.Series(1, index=dataframe.index)  # Default to neutral
        
        # Defensive regime: High RSI + High volatility
        defensive_condition = (
            (dataframe['rsi_overbought_high']) &
            (dataframe['high_volatility'])
        )
        regime[defensive_condition] = 0
        
        # Aggressive regime: Low RSI + Strong trend
        aggressive_condition = (
            (dataframe['rsi_oversold']) &
            (dataframe['strong_trend']) &
            (dataframe['volume_ratio'] > self.volume_multiplier.value)
        )
        regime[aggressive_condition] = 2
        
        return regime

    def get_market_rsis(self, metadata: dict) -> Dict[str, float]:
        """
        Get RSI values from major pairs to determine switching conditions
        """
        market_rsis = {}
        
        # Define the pairs we want to monitor (like the original strategy)
        pairs_to_monitor = [
            'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 
            'ADA/USDT', 'DOT/USDT', 'SOL/USDT'#, 'AVAX/USDT' binance us does not trade this
        ]
        
        for pair in pairs_to_monitor:
            if pair != metadata['pair']:
                try:
                    pair_dataframe = self.dp.get_pair_dataframe(pair, self.timeframe)
                    if pair_dataframe is not None and len(pair_dataframe) > 0:
                        # Calculate RSI for this pair
                        pair_rsi = ta.RSI(pair_dataframe, timeperiod=self.rsi_window.value)
                        market_rsis[pair] = pair_rsi.iloc[-1] if not pd.isna(pair_rsi.iloc[-1]) else 50
                except:
                    market_rsis[pair] = 50  # Default if data unavailable
        
        return market_rsis

    def determine_position_size(self, dataframe: DataFrame, metadata: dict) -> float:
        """
        Determine position size based on market regime and RSI conditions
        Implements the sophisticated allocation logic from the original strategy
        """
        # Get market RSI values
        market_rsis = self.get_market_rsis(metadata)
        
        # Count how many pairs are overbought/oversold
        overbought_count = sum(1 for rsi in market_rsis.values() if rsi > self.rsi_overbought_high.value)
        oversold_count = sum(1 for rsi in market_rsis.values() if rsi < self.rsi_oversold.value)
        
        # Get current pair's RSI
        current_rsi = dataframe['rsi'].iloc[-1]
        
        # Determine allocation based on market conditions
        if overbought_count >= 3:  # Defensive mode (like UVXY in original)
            return self.defensive_allocation.value
        elif oversold_count >= 3 and current_rsi < self.rsi_oversold.value:  # Aggressive mode
            return self.aggressive_allocation.value
        else:  # Neutral mode
            return 0.6  # Default allocation
        
        return 0.5  # Fallback

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Implements the sophisticated nested decision tree from the original strategy
        """
        
        # Get market RSI values
        market_rsis = self.get_market_rsis(metadata)
        
        # Initialize entry conditions
        long_conditions = []
        
        # Count overbought/oversold pairs for better decision making
        overbought_count = sum(1 for rsi in market_rsis.values() if rsi > self.rsi_overbought_high.value)
        oversold_count = sum(1 for rsi in market_rsis.values() if rsi < self.rsi_oversold.value)
        
        # Base entry condition - always check for oversold RSI
        base_condition = (
            (dataframe['rsi_oversold']) &
            (dataframe['volume'] > 0)
        )
        
        # Defensive mode: When major pairs are overbought, prefer stable pairs
        defensive_mode = overbought_count >= 1  # Relaxed from 2 to 1
        
        # Aggressive mode: When many pairs are oversold, prefer volatile pairs
        aggressive_mode = oversold_count >= 1  # Relaxed from 2 to 1
        
        # Entry logic with pair-specific conditions
        if metadata['pair'] in ['BTC/USDT', 'ETH/USDT', 'BNB/USDT']:
            # Stable pairs - enter in defensive mode or when oversold
            if defensive_mode:
                # Defensive entry for stable pairs
                defensive_entry = (
                    base_condition &
                    (dataframe['volume_ratio'] > 0.8)  # Relaxed from 1.1 to 0.8
                )
                long_conditions.append(defensive_entry)
            else:
                # Normal entry for stable pairs
                stable_entry = (
                    base_condition &
                    (dataframe['volume_ratio'] > 0.9)  # Relaxed from 1.2 to 0.9
                )
                long_conditions.append(stable_entry)
        
        elif metadata['pair'] in ['ADA/USDT', 'DOT/USDT', 'SOL/USDT']:
            # Volatile pairs - enter in aggressive mode or when oversold
            if aggressive_mode:
                # Aggressive entry for volatile pairs
                aggressive_entry = (
                    base_condition &
                    (dataframe['volume_ratio'] > 1.0)  # Relaxed from volume_multiplier to 1.0
                )
                long_conditions.append(aggressive_entry)
            else:
                # Normal entry for volatile pairs
                volatile_entry = (
                    base_condition &
                    (dataframe['volume_ratio'] > 1.0)  # Relaxed from 1.3 to 1.0
                )
                long_conditions.append(volatile_entry)
        
        else:
            # Other pairs - balanced approach
            balanced_entry = (
                base_condition &
                (dataframe['volume_ratio'] > 0.9)  # Relaxed from 1.2 to 0.9
            )
            long_conditions.append(balanced_entry)
        
        # Combine all conditions
        if long_conditions:
            dataframe.loc[reduce(lambda x, y: x | y, long_conditions), 'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit logic - conservative exit signals that work with ROI and trailing stop
        """
        
        # Disable exit signals if parameter is False
        if not self.enable_exit_signals:
            dataframe['exit_long'] = 0
            dataframe['exit_short'] = 0
            return dataframe
        
        # Exit long positions - only on very strong reversal signals
        # This should be much less frequent than ROI/trailing stop exits
        dataframe.loc[
            (
                # Exit only on extreme RSI overbought (very high threshold)
                (dataframe['rsi'] > self.exit_rsi_threshold) |
                # Exit only on strong bearish trend AND significant price drop
                (dataframe['bearish_trend'] & (dataframe['close'] < dataframe['sma_20'] * self.exit_trend_drop)) |
                # Exit only on extreme reversal (very significant drop)
                (dataframe['close'] < dataframe['sma_20'] * self.exit_extreme_drop) |
                # Exit on volume spike with price drop (panic selling)
                ((dataframe['volume_ratio'] > self.exit_volume_spike) & (dataframe['close'] < dataframe['open'] * self.exit_candle_drop))
            ) &
            (dataframe['volume'] > 0),
            'exit_long'
        ] = 1

        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                       current_profit: float, **kwargs) -> float:
        """
        Custom stoploss logic based on market regime
        """
        # Get the dataframe for this pair
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        
        if len(dataframe) > 0:
            # Get current market regime
            current_regime = dataframe['market_regime'].iloc[-1]
            
            # Adjust stoploss based on regime
            if current_regime == 0:  # Defensive
                return -0.05  # Tighter stoploss
            elif current_regime == 2:  # Aggressive
                return -0.15  # Wider stoploss
            else:  # Neutral
                return self.stoploss
        
        return self.stoploss

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                   current_profit: float, **kwargs) -> str:
        """
        Custom exit logic based on market regime changes - less aggressive
        """
        # Disable regime exits if parameter is False
        if not self.enable_regime_exits:
            # Only check timeout if regime exits are disabled
            if self.enable_trade_timeout and (current_time - trade.open_date_utc).total_seconds() > (self.trade_timeout_hours * 3600):
                return "timeout_exit"
            return None
        
        # Get the dataframe for this pair
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        
        if len(dataframe) > 0:
            # Exit if market regime changes significantly
            current_regime = dataframe['market_regime'].iloc[-1]
            
            # Exit defensive positions when market becomes aggressive (higher profit threshold)
            if current_regime == 2 and current_profit > self.regime_exit_profit_threshold:
                return "regime_change_exit"
            
            # Exit aggressive positions when market becomes defensive (lower loss threshold)
            if current_regime == 0 and current_profit < self.regime_exit_loss_threshold:
                return "regime_change_exit"
        
        # Exit if we've been in the trade too long (configurable timeout)
        if self.enable_trade_timeout and (current_time - trade.open_date_utc).total_seconds() > (self.trade_timeout_hours * 3600):
            return "timeout_exit"
        
        return None
