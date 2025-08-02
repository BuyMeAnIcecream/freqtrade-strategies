# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401

# --- Do not remove these libs ---
import numpy as np  # noqa
import pandas as pd  # noqa
from pandas import DataFrame

from freqtrade.strategy import (BooleanParameter, CategoricalParameter, DecimalParameter,
                                IStrategy, IntParameter)

# --------------------------------
# Add your lib to import here
import talib
import talib.abstract as ta
import pandas_ta as pta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from technical.util import resample_to_interval, resampled_merge


class PatternRecognition_Debug(IStrategy):
    # Pattern Recognition Strategy - DEBUG VERSION
    # By: @Mablue (Debug version to understand signals)
    # This strategy shows us when conditions are met
    #

    INTERFACE_VERSION: int = 3
    
    # Buy hyperspace params:
    buy_params = {
        "buy_pr1": "CDLHIGHWAVE",
        "buy_vol1": -100,
    }

    # ROI table:
    minimal_roi = {
        "0": 0.936,
        "5271": 0.332,
        "18147": 0.086,
        "48152": 0
    }

    # Stoploss:
    stoploss = -0.288

    # Trailing stop:
    trailing_stop = True
    trailing_stop_positive = 0.032
    trailing_stop_positive_offset = 0.084
    trailing_only_offset_is_reached = True

    # Optimal timeframe for the strategy.
    timeframe = '1d'
    prs = talib.get_function_groups()['Pattern Recognition']

    # Strategy parameters
    buy_pr1 = CategoricalParameter(prs, default=prs[0], space="buy")
    buy_vol1 = CategoricalParameter([-100,100], default=0, space="buy")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Calculate all pattern recognition indicators
        for pr in self.prs:
            dataframe[pr] = getattr(ta, pr)(dataframe)

        # Simple bear market detection
        dataframe['sma_100'] = ta.SMA(dataframe, timeperiod=100)
        dataframe['bear_market'] = dataframe['close'] < dataframe['sma_100']
        
        # Count how many times each condition is met
        dataframe['pattern_signal'] = (dataframe[self.buy_pr1.value]==self.buy_vol1.value)
        dataframe['both_conditions'] = dataframe['pattern_signal'] & dataframe['bear_market']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Let's see what happens with different conditions
        
        # 1. Original pattern recognition (no bear market filter)
        dataframe.loc[
            (
                (dataframe[self.buy_pr1.value]==self.buy_vol1.value)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe 