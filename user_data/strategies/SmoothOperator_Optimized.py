# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy  # noqa

# Optimized SmoothOperator with Market Condition Filtering
# Based on original by Gert Wohlgemuth


class SmoothOperator_Optimized(IStrategy):
    """

    author@: Gert Wohlgemuth (Original)
    optimized@: AI Assistant

    idea:
        The concept is about combining several common indicators, with a heavily smoothing, while trying to detect
        a none completed peak shape. Now optimized with:
        - Market condition filtering (bear/sideways markets only)
        - Improved ROI targets for 5-minute timeframe
        - Better exit logic with trend-following exits
    """

    INTERFACE_VERSION: int = 3
    
    # Optimized ROI for 5-minute timeframe (lower targets for faster exits)
    minimal_roi = {
        "0": 0.02,    # 2% profit target
        "30": 0.015,  # 1.5% after 30 minutes
        "60": 0.01,   # 1% after 1 hour
        "120": 0.005, # 0.5% after 2 hours
        "240": 0.002, # 0.2% after 4 hours
    }

    # Optimal stoploss designed for the strategy
    stoploss = -0.05

    # Optimal timeframe for the strategy
    timeframe = '5m'

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
        dataframe['sma_slow'] = ta.SMA(dataframe, timeperiod=200, price='close')
        dataframe['sma_medium'] = ta.SMA(dataframe, timeperiod=100, price='close')
        dataframe['sma_fast'] = ta.SMA(dataframe, timeperiod=50, price='close')

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
                
                # Original entry conditions
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
                            & (dataframe['cci'].shift(1) < -100)
                            & (dataframe['rsi'].shift(1) < 30)

                    )
                    |
                    # buy in very oversold conditions
                    (
                            (dataframe['low'] < dataframe['bb_middleband'])
                            & (dataframe['cci'] < -200)
                            & (dataframe['rsi'] < 30)
                            & (dataframe['mfi'] < 30)
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
        # Enhanced exit logic with trend-following exits
        dataframe.loc[
            (
                # Original exit conditions
                (
                    #   This generates very nice sale points, and mostly sit's one stop behind
                    #   the top of the peak
                    (
                        (dataframe['mfi_rsi_cci_smooth'] > 100)
                        & (dataframe['mfi_rsi_cci_smooth'].shift(1) > dataframe['mfi_rsi_cci_smooth'])
                        & (dataframe['mfi_rsi_cci_smooth'].shift(2) < dataframe['mfi_rsi_cci_smooth'].shift(1))
                        & (dataframe['mfi_rsi_cci_smooth'].shift(3) < dataframe['mfi_rsi_cci_smooth'].shift(2))
                    )
                    |
                    #   This helps with very long, sideways trends, to get out of a market before
                    #   it dumps
                    (
                        StrategyHelper.eight_green_candles(dataframe)
                    )
                    |
                    # in case of very overbought market, like some one pumping
                    # sell
                    (
                        (dataframe['cci'] > 200)
                        & (dataframe['rsi'] > 70)
                    )
                )
                |
                # NEW: Trend-following exits
                (
                    # Exit on trend reversal (when fast MA crosses below medium MA)
                    (dataframe['trend_reversal_down'] == True)
                    |
                    # Exit if market turns strongly bullish (price above 200 SMA by 5%)
                    (dataframe['close'] > dataframe['sma_200'] * 1.05)
                    |
                    # Exit if momentum indicators show overbought
                    (
                        (dataframe['rsi'] > 75) &
                        (dataframe['cci'] > 150) &
                        (dataframe['mfi'] > 80)
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