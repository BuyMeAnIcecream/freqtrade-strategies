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


class ScalpingSimple(IStrategy):
    """
    Simple Scalping Strategy
    
    This strategy uses basic momentum and trend indicators for scalping
    on short timeframes. It's designed to be less restrictive and generate
    more trading opportunities.
    
    Key Features:
    - Uses RSI and moving averages for signals
    - Quick entries and exits
    - Volume confirmation
    - Simple and effective approach
    
    Expected Performance:
    - Higher frequency trading
    - Small profits per trade
    - Good for volatile markets
    """

    INTERFACE_VERSION: int = 3
    
    # Buy hyperspace params:
    buy_params = {
        "rsi_period": 14,
        "rsi_oversold": 30,
        "rsi_overbought": 70,
        "sma_fast": 5,
        "sma_slow": 10,
        "volume_multiplier": 1.1,
    }

    # ROI table - designed for scalping
    minimal_roi = {
        "0": 0.01,    # 1% profit target
        "5": 0.005,   # 0.5% after 5 minutes
        "10": 0.003,  # 0.3% after 10 minutes
        "15": 0.002,  # 0.2% after 15 minutes
        "30": 0.001,  # 0.1% after 30 minutes
    }

    # Stoploss - moderate for scalping
    stoploss = -0.005  # 0.5% stop loss

    # Trailing stop - protect profits
    trailing_stop = True
    trailing_stop_positive = 0.002  # 0.2% trailing stop
    trailing_stop_positive_offset = 0.003  # Start trailing after 0.3% profit
    trailing_only_offset_is_reached = True

    # Optimal timeframe for scalping
    timeframe = '1m'  # 1-minute timeframe

    # Strategy parameters
    rsi_period = IntParameter(10, 20, default=14, space="buy")
    rsi_oversold = IntParameter(25, 40, default=30, space="buy")
    rsi_overbought = IntParameter(60, 80, default=70, space="buy")
    sma_fast = IntParameter(3, 8, default=5, space="buy")
    sma_slow = IntParameter(8, 15, default=10, space="buy")
    volume_multiplier = DecimalParameter(1.0, 1.5, default=1.1, space="buy")

    # Run "populate_indicators" only for new candle.
    process_only_new_candles = True

    # These values can be overridden in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 15

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds several different TA indicators to the given DataFrame
        """
        
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)
        dataframe['rsi_oversold'] = dataframe['rsi'] < self.rsi_oversold.value
        dataframe['rsi_overbought'] = dataframe['rsi'] > self.rsi_overbought.value
        
        # Moving Averages
        dataframe['sma_fast'] = ta.SMA(dataframe, timeperiod=self.sma_fast.value)
        dataframe['sma_slow'] = ta.SMA(dataframe, timeperiod=self.sma_slow.value)
        
        # MA crossover
        dataframe['sma_cross_up'] = (
            (dataframe['sma_fast'].shift(1) <= dataframe['sma_slow'].shift(1)) &
            (dataframe['sma_fast'] > dataframe['sma_slow'])
        )
        
        dataframe['sma_cross_down'] = (
            (dataframe['sma_fast'].shift(1) >= dataframe['sma_slow'].shift(1)) &
            (dataframe['sma_fast'] < dataframe['sma_slow'])
        )
        
        # Volume indicators
        dataframe['volume_sma'] = ta.SMA(dataframe['volume'], timeperiod=20)
        dataframe['volume_high'] = dataframe['volume'] > (dataframe['volume_sma'] * self.volume_multiplier.value)
        
        # Price momentum
        dataframe['price_change'] = dataframe['close'].pct_change()
        dataframe['momentum_positive'] = dataframe['price_change'] > 0
        dataframe['momentum_negative'] = dataframe['price_change'] < 0
        
        # Price above/below moving averages
        dataframe['price_above_sma'] = dataframe['close'] > dataframe['sma_fast']
        dataframe['price_below_sma'] = dataframe['close'] < dataframe['sma_fast']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        """
        dataframe.loc[
            (
                # RSI oversold bounce
                (dataframe['rsi_oversold'] == True) &
                
                # Price above fast SMA (trending up)
                (dataframe['price_above_sma'] == True) &
                
                # Positive momentum
                (dataframe['momentum_positive'] == True) &
                
                # Volume confirmation (less restrictive)
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
                # Exit if RSI becomes overbought
                (dataframe['rsi_overbought'] == True) |
                
                # Exit if SMA crosses down
                (dataframe['sma_cross_down'] == True) |
                
                # Exit if price falls below SMA
                (dataframe['price_below_sma'] == True) &
                (dataframe['momentum_negative'] == True)
            ),
            'exit_long'] = 1

        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                       current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Custom stoploss logic, returning the new distance relative to current_rate
        """
        
        # Get current market conditions
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        # Tighter stop if RSI is overbought
        if last_candle['rsi_overbought']:
            return -0.003  # 0.3% stop if RSI overbought
        
        # Tighter stop if momentum is negative
        if last_candle['momentum_negative']:
            return -0.003  # 0.3% stop if momentum negative
        
        # Normal stop
        return self.stoploss 