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


class ScalpingUltraFast(IStrategy):
    """
    Ultra-Fast Scalping Strategy
    
    This strategy is designed for extremely short-term scalping on 1-minute timeframes.
    It uses momentum indicators and quick reversals for very fast entries and exits.
    
    Key Features:
    - 1-minute timeframe for maximum speed
    - Uses RSI, MACD, and Bollinger Bands
    - Very tight stops (0.1-0.2%)
    - Maximum hold time of 5-10 minutes
    - Volume and momentum confirmation
    
    Expected Performance:
    - Very high frequency trading
    - Small profits per trade (0.1-0.3%)
    - Requires excellent execution and low spreads
    - Best during high volatility periods
    """

    INTERFACE_VERSION: int = 3
    
    # Buy hyperspace params:
    buy_params = {
        "rsi_period": 7,
        "rsi_oversold": 25,
        "rsi_overbought": 75,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "bb_period": 20,
        "bb_std": 2,
        "volume_multiplier": 1.5,
        "max_hold_time": 5,
        "profit_target": 0.002,
        "stop_loss": 0.001,
    }

    # ROI table - ultra-fast scalping
    minimal_roi = {
        "0": 0.002,   # 0.2% profit target
        "1": 0.0015,  # 0.15% after 1 minute
        "2": 0.001,   # 0.1% after 2 minutes
        "3": 0.0005,  # 0.05% after 3 minutes
        "5": 0.0002,  # 0.02% after 5 minutes
    }

    # Stoploss - very tight for ultra-fast scalping
    stoploss = -0.001  # 0.1% stop loss

    # Trailing stop - protect tiny profits
    trailing_stop = True
    trailing_stop_positive = 0.0005  # 0.05% trailing stop
    trailing_stop_positive_offset = 0.001  # Start trailing after 0.1% profit
    trailing_only_offset_is_reached = True

    # Optimal timeframe for ultra-fast scalping
    timeframe = '1m'  # 1-minute timeframe

    # Strategy parameters
    rsi_period = IntParameter(5, 10, default=7, space="buy")
    rsi_oversold = IntParameter(20, 35, default=25, space="buy")
    rsi_overbought = IntParameter(65, 80, default=75, space="buy")
    macd_fast = IntParameter(8, 16, default=12, space="buy")
    macd_slow = IntParameter(20, 30, default=26, space="buy")
    macd_signal = IntParameter(6, 12, default=9, space="buy")
    bb_period = IntParameter(15, 25, default=20, space="buy")
    bb_std = DecimalParameter(1.5, 2.5, default=2.0, space="buy")
    volume_multiplier = DecimalParameter(1.2, 2.0, default=1.5, space="buy")
    max_hold_time = IntParameter(3, 10, default=5, space="buy")
    profit_target = DecimalParameter(0.001, 0.005, default=0.002, space="buy")
    stop_loss = DecimalParameter(0.0005, 0.002, default=0.001, space="buy")

    # Run "populate_indicators" only for new candle.
    process_only_new_candles = True

    # These values can be overridden in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 30

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds several different TA indicators to the given DataFrame
        """
        
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)
        dataframe['rsi_oversold'] = dataframe['rsi'] < self.rsi_oversold.value
        dataframe['rsi_overbought'] = dataframe['rsi'] > self.rsi_overbought.value
        
        # MACD
        macd = ta.MACD(dataframe, 
                      fastperiod=self.macd_fast.value, 
                      slowperiod=self.macd_slow.value, 
                      signalperiod=self.macd_signal.value)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']
        
        # MACD conditions
        dataframe['macd_cross_up'] = (
            (dataframe['macd'].shift(1) <= dataframe['macdsignal'].shift(1)) &
            (dataframe['macd'] > dataframe['macdsignal'])
        )
        
        dataframe['macd_cross_down'] = (
            (dataframe['macd'].shift(1) >= dataframe['macdsignal'].shift(1)) &
            (dataframe['macd'] < dataframe['macdsignal'])
        )
        
        # Bollinger Bands
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), 
                                          window=self.bb_period.value, 
                                          stds=self.bb_std.value)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']
        dataframe['bb_percent'] = (dataframe['close'] - dataframe['bb_lowerband']) / (dataframe['bb_upperband'] - dataframe['bb_lowerband'])
        
        # BB conditions
        dataframe['bb_squeeze'] = (
            (dataframe['bb_upperband'] - dataframe['bb_lowerband']) / dataframe['bb_middleband'] < 0.02
        )
        
        dataframe['bb_expansion'] = (
            (dataframe['bb_upperband'] - dataframe['bb_lowerband']) / dataframe['bb_middleband'] > 0.05
        )
        
        # Volume indicators
        dataframe['volume_sma'] = ta.SMA(dataframe['volume'], timeperiod=20)
        dataframe['volume_high'] = dataframe['volume'] > (dataframe['volume_sma'] * self.volume_multiplier.value)
        
        # Price momentum
        dataframe['price_change'] = dataframe['close'].pct_change()
        dataframe['momentum_positive'] = dataframe['price_change'] > 0
        dataframe['momentum_negative'] = dataframe['price_change'] < 0
        
        # Price acceleration
        dataframe['price_acceleration'] = dataframe['price_change'].diff()
        dataframe['accelerating_up'] = dataframe['price_acceleration'] > 0
        dataframe['accelerating_down'] = dataframe['price_acceleration'] < 0

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        """
        dataframe.loc[
            (
                # RSI oversold bounce
                (dataframe['rsi_oversold'] == True) &
                
                # MACD cross up (momentum turning positive)
                (dataframe['macd_cross_up'] == True) &
                
                # Price near BB lower band (support)
                (dataframe['bb_percent'] < 0.2) &
                
                # Volume confirmation
                (dataframe['volume_high'] == True) &
                
                # Positive momentum
                (dataframe['momentum_positive'] == True) &
                
                # Price accelerating up
                (dataframe['accelerating_up'] == True) &
                
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
                # Exit if RSI becomes overbought
                (dataframe['rsi_overbought'] == True) |
                
                # Exit if MACD crosses down
                (dataframe['macd_cross_down'] == True) |
                
                # Exit if price reaches BB upper band
                (dataframe['bb_percent'] > 0.8) |
                
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
        
        # Get current market conditions
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        # Tighter stop if BB squeeze (low volatility)
        if last_candle['bb_squeeze']:
            return -0.0005  # 0.05% stop in low volatility
        
        # Tighter stop if volume drops
        if not last_candle['volume_high']:
            return -0.0005  # 0.05% stop if volume is low
        
        # Tighter stop if momentum turns negative
        if last_candle['momentum_negative']:
            return -0.0005  # 0.05% stop if momentum is negative
        
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
        
        # Exit if we've been in profit for too long without hitting target
        if current_profit > 0.001 and (current_time - trade.open_date_utc).total_seconds() > (self.max_hold_time.value * 30):
            return "profit_timeout"
        
        return None 