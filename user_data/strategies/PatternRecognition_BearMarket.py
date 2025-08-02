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


class PatternRecognition_BearMarket(IStrategy):
    # Pattern Recognition Strategy - BEAR MARKET ONLY VERSION
    # By: @Mablue (Modified for bear market only)
    # This strategy only trades in bear markets and stays out during bull markets
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

    # Bear market detection parameters
    bear_market_sma_short = IntParameter(20, 50, default=30, space="buy")
    bear_market_sma_long = IntParameter(100, 200, default=150, space="buy")
    bear_market_rsi_period = IntParameter(10, 30, default=14, space="buy")
    bear_market_rsi_threshold = IntParameter(30, 50, default=40, space="buy")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Calculate all pattern recognition indicators
        for pr in self.prs:
            dataframe[pr] = getattr(ta, pr)(dataframe)

        # Bear market detection indicators
        # 1. Price below long-term moving average (trend is down)
        dataframe['sma_short'] = ta.SMA(dataframe, timeperiod=self.bear_market_sma_short.value)
        dataframe['sma_long'] = ta.SMA(dataframe, timeperiod=self.bear_market_sma_long.value)
        dataframe['price_below_sma'] = dataframe['close'] < dataframe['sma_long']
        
        # 2. Short-term MA below long-term MA (downtrend)
        dataframe['sma_trend_down'] = dataframe['sma_short'] < dataframe['sma_long']
        
        # 3. RSI below threshold (oversold/weak market)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.bear_market_rsi_period.value)
        dataframe['rsi_below_threshold'] = dataframe['rsi'] < self.bear_market_rsi_threshold.value
        
        # 4. Price momentum (negative momentum indicates bear market)
        dataframe['momentum'] = ta.MOM(dataframe, timeperiod=10)
        dataframe['negative_momentum'] = dataframe['momentum'] < 0
        
        # 5. Volume trend (declining volume often accompanies bear markets)
        dataframe['volume_sma'] = ta.SMA(dataframe['volume'], timeperiod=20)
        dataframe['volume_declining'] = dataframe['volume'] < dataframe['volume_sma']
        
        # Combined bear market signal
        dataframe['bear_market'] = (
            dataframe['price_below_sma'] & 
            dataframe['sma_trend_down'] & 
            dataframe['rsi_below_threshold'] &
            dataframe['negative_momentum']
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # Original pattern recognition signal
                (dataframe[self.buy_pr1.value]==self.buy_vol1.value) &
                # ONLY trade in bear market conditions
                (dataframe['bear_market'] == True)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit if we're no longer in a bear market (optional)
        dataframe.loc[
            (
                (dataframe['bear_market'] == False)
            ),
            'exit_long'] = 1

        return dataframe

    # Note: custom_stoploss function removed for simplicity
    # The strategy will use the default stoploss mechanism 