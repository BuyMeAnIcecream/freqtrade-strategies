# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy  # noqa

# SmoothOperator Optimized Final - Best Hyperopt Results
# Based on original by Gert Wohlgemuth
# Optimized with hyperopt parameters achieving +0.84% profit


class SmoothOperator_Optimized_Final(IStrategy):
    """

    author@: Gert Wohlgemuth (Original)
    optimized@: AI Assistant Final

    idea:
        The concept is about combining several common indicators, with a heavily smoothing, while trying to detect
        a none completed peak shape. Now optimized with:
        - Market condition filtering (bear/sideways markets only)
        - Hyperopt-optimized parameters for maximum profit
        - Refined exit logic with less aggressive conditions
        - Best performing configuration from 100 hyperopt epochs
    """

    INTERFACE_VERSION: int = 3
    
    # Hyperopt-optimized ROI table (achieved +0.84% profit)
    minimal_roi = {
        "0": 0.146,   # 14.6% profit target
        "37": 0.1,    # 10% after 37 minutes
        "55": 0.036,  # 3.6% after 55 minutes
        "158": 0      # 0% after 158 minutes
    }

    # Hyperopt-optimized stoploss
    stoploss = -0.061

    # Optimal timeframe for the strategy
    timeframe = '5m'

    # Hyperopt Parameters (Best Results from 100 epochs)
    # RSI thresholds
    rsi_oversold = IntParameter(20, 35, default=29, space="buy")
    rsi_overbought = IntParameter(65, 80, default=76, space="sell")
    
    # CCI thresholds
    cci_oversold = IntParameter(-250, -150, default=-198, space="buy")
    cci_overbought = IntParameter(150, 250, default=197, space="sell")
    
    # MFI thresholds
    mfi_oversold = IntParameter(10, 30, default=15, space="buy")
    mfi_overbought = IntParameter(70, 90, default=73, space="sell")
    
    # Moving average periods
    sma_fast_period = IntParameter(20, 60, default=49, space="buy")
    sma_medium_period = IntParameter(80, 120, default=101, space="buy")
    sma_slow_period = IntParameter(180, 220, default=180, space="buy")
    
    # Exit logic parameters
    exit_rsi_threshold = IntParameter(70, 85, default=80, space="sell")
    exit_cci_threshold = IntParameter(150, 250, default=187, space="sell")
    exit_mfi_threshold = IntParameter(75, 90, default=85, space="sell")
    
    # Market condition parameters
    bullish_threshold = DecimalParameter(1.03, 1.08, default=1.044, space="sell")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ##################################################################################
        # required for entry and exit
        # CCI
        dataframe['cci'] = ta.CCI(dataframe, timeperiod=20)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['adx'] = ta.ADX(dataframe)
        dataframe['mfi'] = ta.MFI(dataframe)
        dataframe['mfi_smooth'] = ta.EMA(dataframe, timeperiod=11, price='mfi')
        dataframe['cci_smooth'] = ta.EMA(dataframe, timeperiod=11, price='cci')
        dataframe['rsi_smooth'] = ta.EMA(dataframe, timeperiod=11, price='rsi')

        ##################################################################################
        # required for graphing
        bollinger = qtpylib.bollinger_bands(dataframe['close'], window=20, stds=2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_upperband'] = bollinger['upper']
        dataframe['bb_middleband'] = bollinger['mid']

        # MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        ##################################################################################
        # required for entry
        bollinger = qtpylib.bollinger_bands(dataframe['close'], window=20, stds=1.6)
        dataframe['entry_bb_lowerband'] = bollinger['lower']
        dataframe['entry_bb_upperband'] = bollinger['upper']
        dataframe['entry_bb_middleband'] = bollinger['mid']

        dataframe['bpercent'] = (dataframe['close'] - dataframe['bb_lowerband']) / (
                dataframe['bb_upperband'] - dataframe['bb_lowerband']) * 100

        dataframe['bsharp'] = (dataframe['bb_upperband'] - dataframe['bb_lowerband']) / (
            dataframe['bb_middleband'])

        # these seem to be kind useful to measure when bands widen
        # but than they are directly based on the moving average
        dataframe['bsharp_slow'] = ta.SMA(dataframe, price='bsharp', timeperiod=11)
        dataframe['bsharp_medium'] = ta.SMA(dataframe, price='bsharp', timeperiod=8)
        dataframe['bsharp_fast'] = ta.SMA(dataframe, price='bsharp', timeperiod=5)

        ##################################################################################
        # rsi and mfi are slightly weighted
        dataframe['mfi_rsi_cci_smooth'] = (dataframe['rsi_smooth'] * 1.125 + dataframe['mfi_smooth'] * 1.125 +
                                           dataframe[
                                               'cci_smooth']) / 3

        dataframe['mfi_rsi_cci_smooth'] = ta.TEMA(dataframe, timeperiod=21, price='mfi_rsi_cci_smooth')

        # playground
        dataframe['candle_size'] = (dataframe['close'] - dataframe['open']) * (
                dataframe['close'] - dataframe['open']) / 2

        # helps with pattern recognition
        dataframe['average'] = (dataframe['close'] + dataframe['open'] + dataframe['high'] + dataframe['low']) / 4
        
        # Use hyperopt parameters for moving averages
        dataframe['sma_slow'] = ta.SMA(dataframe, timeperiod=self.sma_slow_period.value, price='close')
        dataframe['sma_medium'] = ta.SMA(dataframe, timeperiod=self.sma_medium_period.value, price='close')
        dataframe['sma_fast'] = ta.SMA(dataframe, timeperiod=self.sma_fast_period.value, price='close')

        ##################################################################################
        # NEW: Market Condition Filtering
        # Detect bear markets and sideways markets
        dataframe['sma_200'] = ta.SMA(dataframe, timeperiod=200, price='close')
        dataframe['sma_50'] = ta.SMA(dataframe, timeperiod=50, price='close')
        
        # Bear market: price below 200 SMA
        dataframe['bear_market'] = dataframe['close'] < dataframe['sma_200']
        
        # Sideways market: price between 50 and 200 SMA, or within 5% of 200 SMA
        dataframe['sideways_market'] = (
            (dataframe['close'] >= dataframe['sma_200'] * 0.95) &
            (dataframe['close'] <= dataframe['sma_200'] * 1.05)
        )
        
        # Combined market condition (bear OR sideways, but not strong bull)
        dataframe['favorable_market'] = dataframe['bear_market'] | dataframe['sideways_market']
        
        # Trend detection for exit logic
        dataframe['trend_up'] = dataframe['sma_fast'] > dataframe['sma_medium']
        dataframe['trend_down'] = dataframe['sma_fast'] < dataframe['sma_medium']
        
        # Trend reversal detection
        dataframe['trend_reversal_down'] = (
            (dataframe['sma_fast'].shift(1) > dataframe['sma_medium'].shift(1)) &
            (dataframe['sma_fast'] < dataframe['sma_medium'])
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # NEW: Market Condition Filter - Only trade in bear/sideways markets
                (dataframe['favorable_market'] == True) &
                
                # Original entry conditions with hyperopt parameters
                (
                    # simple v bottom shape (lopsided to the left to increase reactivity)
                    # which has to be below a very slow average
                    # this pattern only catches a few, but normally very good buy points
                    (
                            (dataframe['average'].shift(5) > dataframe['average'].shift(4))
                            & (dataframe['average'].shift(4) > dataframe['average'].shift(3))
                            & (dataframe['average'].shift(3) > dataframe['average'].shift(2))
                            & (dataframe['average'].shift(2) > dataframe['average'].shift(1))
                            & (dataframe['average'].shift(1) < dataframe['average'].shift(0))
                            & (dataframe['low'].shift(1) < dataframe['bb_middleband'])
                            & (dataframe['cci'].shift(1) < self.cci_oversold.value)
                            & (dataframe['rsi'].shift(1) < self.rsi_oversold.value)

                    )
                    |
                    # buy in very oversold conditions
                    (
                            (dataframe['low'] < dataframe['bb_middleband'])
                            & (dataframe['cci'] < self.cci_oversold.value)
                            & (dataframe['rsi'] < self.rsi_oversold.value)
                            & (dataframe['mfi'] < self.mfi_oversold.value)
                    )

                    |
                    # etc tends to trade like this
                    # over very long periods of slowly building up coins
                    # does not happen often, but once in a while
                    (
                            (dataframe['mfi'] < 10)
                            & (dataframe['cci'] < -150)
                            & (dataframe['rsi'] < dataframe['mfi'])
                    )

                )

                &
                # ensure we have an overall uptrend
                (dataframe['close'] > dataframe['close'].shift())
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # IMPROVED: Less aggressive exit logic with hyperopt parameters
        dataframe.loc[
            (
                # Original exit conditions (more conservative)
                (
                    #   This generates very nice sale points, and mostly sit's one stop behind
                    #   the top of the peak - made more conservative
                    (
                        (dataframe['mfi_rsi_cci_smooth'] > 110)  # Increased from 100
                        & (dataframe['mfi_rsi_cci_smooth'].shift(1) > dataframe['mfi_rsi_cci_smooth'])
                        & (dataframe['mfi_rsi_cci_smooth'].shift(2) < dataframe['mfi_rsi_cci_smooth'].shift(1))
                        & (dataframe['mfi_rsi_cci_smooth'].shift(3) < dataframe['mfi_rsi_cci_smooth'].shift(2))
                        & (dataframe['mfi_rsi_cci_smooth'].shift(4) < dataframe['mfi_rsi_cci_smooth'].shift(3))  # Added confirmation
                    )
                    |
                    #   This helps with very long, sideways trends, to get out of a market before
                    #   it dumps - made more conservative (10 green candles instead of 8)
                    (
                        StrategyHelper.ten_green_candles(dataframe)
                    )
                    |
                    # in case of very overbought market, like some one pumping
                    # sell - made more conservative
                    (
                        (dataframe['cci'] > self.exit_cci_threshold.value)
                        & (dataframe['rsi'] > self.exit_rsi_threshold.value)
                        & (dataframe['mfi'] > self.exit_mfi_threshold.value)
                    )
                )
                |
                # IMPROVED: Less aggressive trend-following exits
                (
                    # Exit on strong trend reversal (when fast MA crosses below medium MA AND price is falling)
                    (
                        (dataframe['trend_reversal_down'] == True) &
                        (dataframe['close'] < dataframe['close'].shift(1)) &
                        (dataframe['close'].shift(1) < dataframe['close'].shift(2))
                    )
                    |
                    # Exit if market turns strongly bullish (price above 200 SMA by threshold)
                    (dataframe['close'] > dataframe['sma_200'] * self.bullish_threshold.value)
                    |
                    # Exit if momentum indicators show extreme overbought (more conservative)
                    (
                        (dataframe['rsi'] > self.exit_rsi_threshold.value) &
                        (dataframe['cci'] > self.exit_cci_threshold.value) &
                        (dataframe['mfi'] > self.exit_mfi_threshold.value) &
                        (dataframe['close'] < dataframe['close'].shift(1))  # Price must be falling
                    )
                )
            ),
            'exit_long'] = 1

        return dataframe


class StrategyHelper:
    @staticmethod
    def seven_green_candles(dataframe):
        return (
                (dataframe['close'] > dataframe['open'])
                & (dataframe['close'].shift(1) > dataframe['open'].shift(1))
                & (dataframe['close'].shift(2) > dataframe['open'].shift(2))
                & (dataframe['close'].shift(3) > dataframe['open'].shift(3))
                & (dataframe['close'].shift(4) > dataframe['open'].shift(4))
                & (dataframe['close'].shift(5) > dataframe['open'].shift(5))
                & (dataframe['close'].shift(6) > dataframe['open'].shift(6))
        )

    @staticmethod
    def eight_green_candles(dataframe):
        return (
                (dataframe['close'] > dataframe['open'])
                & (dataframe['close'].shift(1) > dataframe['open'].shift(1))
                & (dataframe['close'].shift(2) > dataframe['open'].shift(2))
                & (dataframe['close'].shift(3) > dataframe['open'].shift(3))
                & (dataframe['close'].shift(4) > dataframe['open'].shift(4))
                & (dataframe['close'].shift(5) > dataframe['open'].shift(5))
                & (dataframe['close'].shift(6) > dataframe['open'].shift(6))
                & (dataframe['close'].shift(7) > dataframe['open'].shift(7))
        )

    @staticmethod
    def ten_green_candles(dataframe):
        return (
                (dataframe['close'] > dataframe['open'])
                & (dataframe['close'].shift(1) > dataframe['open'].shift(1))
                & (dataframe['close'].shift(2) > dataframe['open'].shift(2))
                & (dataframe['close'].shift(3) > dataframe['open'].shift(3))
                & (dataframe['close'].shift(4) > dataframe['open'].shift(4))
                & (dataframe['close'].shift(5) > dataframe['open'].shift(5))
                & (dataframe['close'].shift(6) > dataframe['open'].shift(6))
                & (dataframe['close'].shift(7) > dataframe['open'].shift(7))
                & (dataframe['close'].shift(8) > dataframe['open'].shift(8))
                & (dataframe['close'].shift(9) > dataframe['open'].shift(9))
        )

    @staticmethod
    def eight_red_candles(dataframe, shift=0):
        return (
                (dataframe['close'].shift(shift) < dataframe['open'].shift(shift))
                & (dataframe['close'].shift(shift + 1) < dataframe['open'].shift(shift + 1))
                & (dataframe['close'].shift(shift + 2) < dataframe['open'].shift(shift + 2))
                & (dataframe['close'].shift(shift + 3) < dataframe['open'].shift(shift + 3))
                & (dataframe['close'].shift(shift + 4) < dataframe['open'].shift(shift + 4))
                & (dataframe['close'].shift(shift + 5) < dataframe['open'].shift(shift + 5))
                & (dataframe['close'].shift(shift + 6) < dataframe['open'].shift(shift + 6))
                & (dataframe['close'].shift(shift + 7) < dataframe['open'].shift(shift + 7))
        )

    @staticmethod
    def four_green_one_red_candle(dataframe):
        return (
                (dataframe['close'] < dataframe['open'])
                & (dataframe['close'].shift(1) > dataframe['open'].shift(1))
                & (dataframe['close'].shift(2) > dataframe['open'].shift(2))
                & (dataframe['close'].shift(3) > dataframe['open'].shift(3))
                & (dataframe['close'].shift(4) > dataframe['open'].shift(4))
        )

    @staticmethod
    def four_red_one_green_candle(dataframe):
        return (
                (dataframe['close'] > dataframe['open'])
                & (dataframe['close'].shift(1) < dataframe['open'].shift(1))
                & (dataframe['close'].shift(2) < dataframe['open'].shift(2))
                & (dataframe['close'].shift(3) < dataframe['open'].shift(3))
                & (dataframe['close'].shift(4) < dataframe['open'].shift(4))
        ) 