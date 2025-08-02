import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter


logger = logging.getLogger(__name__)


class SimpleTestStrategy(IStrategy):
    """
    Simple test strategy for demonstration purposes.
    This strategy uses basic moving average crossover signals.
    """
    
    INTERFACE_VERSION = 3
    
    # Minimal ROI designed for the strategy.
    minimal_roi = {
        "0": 0.05,
        "30": 0.025,
        "60": 0.015,
        "120": 0.01
    }

    # Optimal stoploss designed for the strategy
    stoploss = -0.10

    # Optimal timeframe for the strategy
    timeframe = '1h'

    # Run "populate_indicators" only for new candle.
    process_only_new_candles = True

    # These values can be overridden in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 30

    # Strategy parameters
    fast_ma = IntParameter(5, 20, default=10, space="buy")
    slow_ma = IntParameter(20, 50, default=30, space="buy")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds several different TA indicators to the given DataFrame

        Performance Note: For the best performance be frugal on the number of indicators
        you add. Let uncomment only the indicator you are using in your strategies
        or your hyperopt configuration, otherwise you will waste your memory and CPU usage.
        """

        # SMA - Simple Moving Average
        dataframe['sma_fast'] = dataframe['close'].rolling(window=self.fast_ma.value).mean()
        dataframe['sma_slow'] = dataframe['close'].rolling(window=self.slow_ma.value).mean()

        # RSI
        dataframe['rsi'] = self.rsi(dataframe, timeperiod=14)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with entry columns populated
        """
        dataframe.loc[
            (
                (dataframe['sma_fast'] > dataframe['sma_slow']) &
                (dataframe['rsi'] < 70) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with exit columns populated
        """
        dataframe.loc[
            (
                (dataframe['sma_fast'] < dataframe['sma_slow']) |
                (dataframe['rsi'] > 80)
            ),
            'exit_long'] = 1

        return dataframe

    def rsi(self, dataframe: DataFrame, timeperiod: int = 14) -> pd.Series:
        """Relative Strength Index"""
        delta = dataframe['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=timeperiod).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=timeperiod).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs)) 