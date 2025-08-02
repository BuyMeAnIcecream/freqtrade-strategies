# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401

# --- Do not remove these libs ---
import numpy as np  # noqa
import pandas as pd  # noqa
from pandas import DataFrame
from datetime import datetime

from freqtrade.strategy import (BooleanParameter, CategoricalParameter, DecimalParameter,
                                IStrategy, IntParameter)

# --------------------------------
# Add your lib to import here
import talib
import talib.abstract as ta
import pandas_ta as pta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from technical.util import resample_to_interval, resampled_merge


class BearMarketHybrid(IStrategy):
    """
    Bear Market Hybrid Strategy
    
    This strategy combines RSI oversold signals with common candlestick patterns
    and only trades during bear markets (price below moving average).
    
    Key Features:
    - Only trades when price is below 100-day moving average (bear market)
    - Uses RSI oversold signals (< 35) as primary entry condition
    - Confirms with common reversal patterns (Doji, Hammer, etc.)
    - Includes volume and support level confirmation
    - Exits when market turns bullish or conditions deteriorate
    
    Expected Performance:
    - Should avoid bull market losses
    - Should capture bear market bounces and reversals
    - Higher frequency than pattern-only strategies
    - Better confirmation than RSI-only strategies
    """

    INTERFACE_VERSION: int = 3
    
    # Buy hyperspace params:
    buy_params = {
        "rsi_period": 14,
        "rsi_oversold": 35,
        "rsi_overbought": 70,
        "sma_period": 100,
        "volume_multiplier": 1.3,
        "use_patterns": True,
        "pattern_type": "CDLDOJI",
    }

    # ROI table - designed for bear market opportunities
    minimal_roi = {
        "0": 0.06,    # 6% profit target
        "30": 0.04,   # 4% after 30 minutes
        "60": 0.03,   # 3% after 1 hour
        "120": 0.02,  # 2% after 2 hours
        "240": 0.01,  # 1% after 4 hours
    }

    # Stoploss - balanced for hybrid approach
    stoploss = -0.035  # 3.5% stop loss

    # Trailing stop - protect profits
    trailing_stop = True
    trailing_stop_positive = 0.012  # 1.2% trailing stop
    trailing_stop_positive_offset = 0.02  # Start trailing after 2% profit
    trailing_only_offset_is_reached = True

    # Optimal timeframe for the strategy
    timeframe = '2h'  # 2-hour timeframe for balanced opportunities

    # Strategy parameters
    rsi_period = IntParameter(10, 20, default=14, space="buy")
    rsi_oversold = IntParameter(25, 45, default=35, space="buy")
    rsi_overbought = IntParameter(60, 80, default=70, space="buy")
    sma_period = IntParameter(50, 200, default=100, space="buy")
    volume_multiplier = DecimalParameter(1.0, 2.5, default=1.3, space="buy")
    use_patterns = BooleanParameter(default=True, space="buy")
    pattern_type = CategoricalParameter([
        "CDLDOJI",           # Doji pattern
        "CDLHAMMER",         # Hammer pattern
        "CDLINVERTEDHAMMER", # Inverted Hammer
        "CDLENGULFING",      # Engulfing pattern
        "CDLMORNINGSTAR",    # Morning Star
        "CDLEVENINGSTAR",    # Evening Star
    ], default="CDLDOJI", space="buy")

    # Run "populate_indicators" only for new candle.
    process_only_new_candles = True

    # These values can be overridden in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 100

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds several different TA indicators to the given DataFrame
        """
        
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)
        
        # Moving Averages
        dataframe['sma'] = ta.SMA(dataframe, timeperiod=self.sma_period.value)
        dataframe['sma_20'] = ta.SMA(dataframe, timeperiod=20)
        
        # Volume indicators
        dataframe['volume_sma'] = ta.SMA(dataframe['volume'], timeperiod=20)
        dataframe['volume_high'] = dataframe['volume'] > (dataframe['volume_sma'] * self.volume_multiplier.value)
        
        # Bear market detection
        dataframe['bear_market'] = dataframe['close'] < dataframe['sma']
        
        # RSI conditions
        dataframe['rsi_oversold'] = dataframe['rsi'] < self.rsi_oversold.value
        dataframe['rsi_overbought'] = dataframe['rsi'] > self.rsi_overbought.value
        
        # Price momentum
        dataframe['price_change'] = dataframe['close'].pct_change()
        dataframe['negative_momentum'] = dataframe['price_change'] < 0
        
        # Bollinger Bands for additional context
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']
        dataframe['bb_percent'] = (dataframe['close'] - dataframe['bb_lowerband']) / (dataframe['bb_upperband'] - dataframe['bb_lowerband'])
        
        # Near support levels
        dataframe['near_support'] = dataframe['bb_percent'] < 0.25
        
        # Pattern recognition (if enabled)
        if self.use_patterns.value:
            pattern_functions = [
                "CDLDOJI", "CDLHAMMER", "CDLINVERTEDHAMMER", "CDLENGULFING",
                "CDLMORNINGSTAR", "CDLEVENINGSTAR"
            ]
            
            for pattern in pattern_functions:
                dataframe[pattern] = getattr(ta, pattern)(dataframe)
            
            # Pattern signal (the selected pattern)
            dataframe['pattern_signal'] = dataframe[self.pattern_type.value] == 100
        else:
            # If patterns disabled, always True
            dataframe['pattern_signal'] = True

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        """
        dataframe.loc[
            (
                # Bear market condition - price below moving average
                (dataframe['bear_market'] == True) &
                
                # Primary signal: RSI oversold
                (dataframe['rsi_oversold'] == True) &
                
                # Secondary signal: Pattern confirmation (if enabled)
                (dataframe['pattern_signal'] == True) &
                
                # Volume confirmation
                (dataframe['volume_high'] == True) &
                
                # Near support levels
                (dataframe['near_support'] == True) &
                
                # Ensure we have volume
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        """
        dataframe.loc[
            (
                # Exit if market turns bullish (price above MA)
                (dataframe['bear_market'] == False) |
                
                # Exit if RSI becomes overbought
                (dataframe['rsi_overbought'] == True) |
                
                # Exit if price moves too far from support
                (dataframe['bb_percent'] > 0.8) |
                
                # Exit if momentum turns strongly negative
                (dataframe['negative_momentum'] == True) &
                (dataframe['rsi'] > 50)  # Only if RSI is not oversold
            ),
            'exit_long'] = 1

        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                       current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Custom stoploss logic, returning the new distance relative to current_rate
        """
        
        # If we're in a strong bear market, use tighter stops
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        # Tighter stop in very oversold conditions
        if last_candle['rsi'] < 25:
            return -0.025  # 2.5% stop in very oversold conditions
        
        # Tighter stop if pattern was used and we're not near support
        if self.use_patterns.value and last_candle['bb_percent'] > 0.5:
            return -0.03  # 3% stop when away from support
        
        # Normal stop
        return self.stoploss 