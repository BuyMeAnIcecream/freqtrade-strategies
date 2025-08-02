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


class PatternRecognition_BearMarket_VerySimple(IStrategy):
    # Pattern Recognition Strategy - VERY SIMPLE BEAR MARKET VERSION
    # By: @Mablue (Modified for bear market only - VERY SIMPLE VERSION)
    # This strategy only trades when price is below moving average
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

    # Very simple bear market detection - just price below MA
    bear_market_sma_period = IntParameter(50, 200, default=100, space="buy")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Calculate all pattern recognition indicators
        for pr in self.prs:
            dataframe[pr] = getattr(ta, pr)(dataframe)

        # Very simple bear market detection - just price below moving average
        dataframe['sma'] = ta.SMA(dataframe, timeperiod=self.bear_market_sma_period.value)
        dataframe['bear_market'] = dataframe['close'] < dataframe['sma']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # Original pattern recognition signal
                (dataframe[self.buy_pr1.value]==self.buy_vol1.value) &
                # ONLY trade when price is below moving average (bear market)
                (dataframe['bear_market'] == True)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit if price goes above moving average (no longer bear market)
        dataframe.loc[
            (
                (dataframe['bear_market'] == False)
            ),
            'exit_long'] = 1

        return dataframe 