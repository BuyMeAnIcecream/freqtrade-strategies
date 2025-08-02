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


class ScalpingMARibbon(IStrategy):
    """
    Scalping Moving Average Ribbon Strategy
    
    This strategy uses multiple Simple Moving Averages (5-8-13) to identify
    trending conditions and scalp for quick profits.
    
    Key Features:
    - Uses 5, 8, and 13 period SMAs on short timeframes
    - Identifies trending markets with proper MA alignment
    - Quick entries and exits for scalping
    - Volume confirmation for stronger signals
    - Maximum hold time to prevent overstaying
    
    Expected Performance:
    - High frequency, low profit per trade
    - Good for trending markets
    - Requires low spreads and fast execution
    """

    INTERFACE_VERSION: int = 3
    
    # Buy hyperspace params:
    buy_params = {
        "sma_short": 5,
        "sma_mid": 8,
        "sma_long": 13,
        "volume_multiplier": 1.2,
        "max_hold_time": 30,
        "profit_target": 0.005,
        "stop_loss": 0.003,
    }

    # ROI table - designed for scalping (quick profits)
    minimal_roi = {
        "0": 0.005,   # 0.5% profit target
        "5": 0.003,   # 0.3% after 5 minutes
        "10": 0.002,  # 0.2% after 10 minutes
        "15": 0.001,  # 0.1% after 15 minutes
        "30": 0.0005, # 0.05% after 30 minutes
    }

    # Stoploss - tight for scalping
    stoploss = -0.003  # 0.3% stop loss

    # Trailing stop - protect small profits
    trailing_stop = True
    trailing_stop_positive = 0.001  # 0.1% trailing stop
    trailing_stop_positive_offset = 0.002  # Start trailing after 0.2% profit
    trailing_only_offset_is_reached = True

    # Optimal timeframe for scalping
    timeframe = '1m'  # 1-minute timeframe for scalping

    # Strategy parameters
    sma_short = IntParameter(3, 7, default=5, space="buy")
    sma_mid = IntParameter(6, 10, default=8, space="buy")
    sma_long = IntParameter(10, 16, default=13, space="buy")
    volume_multiplier = DecimalParameter(1.0, 2.0, default=1.2, space="buy")
    max_hold_time = IntParameter(15, 60, default=30, space="buy")
    profit_target = DecimalParameter(0.003, 0.01, default=0.005, space="buy")
    stop_loss = DecimalParameter(0.002, 0.005, default=0.003, space="buy")

    # Run "populate_indicators" only for new candle.
    process_only_new_candles = True

    # These values can be overridden in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 20

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds several different TA indicators to the given DataFrame
        """
        
        # Moving Average Ribbon (5-8-13 SMAs)
        dataframe['sma_short'] = ta.SMA(dataframe, timeperiod=self.sma_short.value)
        dataframe['sma_mid'] = ta.SMA(dataframe, timeperiod=self.sma_mid.value)
        dataframe['sma_long'] = ta.SMA(dataframe, timeperiod=self.sma_long.value)
        
        # Volume indicators
        dataframe['volume_sma'] = ta.SMA(dataframe['volume'], timeperiod=20)
        dataframe['volume_high'] = dataframe['volume'] > (dataframe['volume_sma'] * self.volume_multiplier.value)
        
        # MA Ribbon alignment conditions
        # Long setup: MAs aligned upward with clear spacing
        dataframe['ma_aligned_up'] = (
            (dataframe['sma_short'] > dataframe['sma_mid']) &
            (dataframe['sma_mid'] > dataframe['sma_long']) &
            (dataframe['sma_short'] - dataframe['sma_long']) > (dataframe['sma_long'] * 0.001)  # Clear spacing
        )
        
        # Short setup: MAs aligned downward with clear spacing
        dataframe['ma_aligned_down'] = (
            (dataframe['sma_short'] < dataframe['sma_mid']) &
            (dataframe['sma_mid'] < dataframe['sma_long']) &
            (dataframe['sma_long'] - dataframe['sma_short']) > (dataframe['sma_long'] * 0.001)  # Clear spacing
        )
        
        # MA compression (potential exit signal)
        dataframe['ma_compressed'] = (
            abs(dataframe['sma_short'] - dataframe['sma_long']) < (dataframe['sma_long'] * 0.0005)
        )
        
        # MA crossover signals
        dataframe['ma_cross_up'] = (
            (dataframe['sma_short'].shift(1) <= dataframe['sma_mid'].shift(1)) &
            (dataframe['sma_short'] > dataframe['sma_mid'])
        )
        
        dataframe['ma_cross_down'] = (
            (dataframe['sma_short'].shift(1) >= dataframe['sma_mid'].shift(1)) &
            (dataframe['sma_short'] < dataframe['sma_mid'])
        )
        
        # Price momentum
        dataframe['price_change'] = dataframe['close'].pct_change()
        dataframe['momentum_positive'] = dataframe['price_change'] > 0
        dataframe['momentum_negative'] = dataframe['price_change'] < 0
        
        # RSI for additional confirmation
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['rsi_oversold'] = dataframe['rsi'] < 30
        dataframe['rsi_overbought'] = dataframe['rsi'] > 70

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        """
        dataframe.loc[
            (
                # Long entry: MAs aligned upward with clear spacing
                (dataframe['ma_aligned_up'] == True) &
                
                # Volume confirmation
                (dataframe['volume_high'] == True) &
                
                # Positive momentum
                (dataframe['momentum_positive'] == True) &
                
                # RSI not overbought
                (dataframe['rsi'] < 75) &
                
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
                # Exit if MAs compress (lose alignment)
                (dataframe['ma_compressed'] == True) |
                
                # Exit if MA crossover occurs
                (dataframe['ma_cross_down'] == True) |
                
                # Exit if RSI becomes overbought
                (dataframe['rsi_overbought'] == True) |
                
                # Exit if momentum turns negative
                (dataframe['momentum_negative'] == True) &
                (dataframe['rsi'] > 50)  # Only if RSI is not oversold
            ),
            'exit_long'] = 1

        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                       current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Custom stoploss logic, returning the new distance relative to current_rate
        """
        
        # If we're in a strong trend, use tighter stops
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        # Tighter stop if MAs are compressed
        if last_candle['ma_compressed']:
            return -0.002  # 0.2% stop if MAs compress
        
        # Tighter stop if volume drops
        if not last_candle['volume_high']:
            return -0.002  # 0.2% stop if volume is low
        
        # Normal stop
        return self.stoploss

    def custom_exit(self, pair: str, trade: 'Trade', current_time: datetime, current_rate: float,
                   current_profit: float, **kwargs) -> str:
        """
        Custom exit logic
        """
        
        # Exit if we've held too long (max hold time)
        if (current_time - trade.open_date_utc).total_seconds() > (self.max_hold_time.value * 60):
            return "max_hold_time"
        
        # Exit if we hit profit target
        if current_profit >= self.profit_target.value:
            return "profit_target"
        
        return None 