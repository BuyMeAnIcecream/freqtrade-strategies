import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from pandas import DataFrame

from freqtrade.strategy import IStrategy, DecimalParameter


logger = logging.getLogger(__name__)


class DipBuyingStrategy(IStrategy):
    """
    Simple dip-buying strategy for SOL, ADA, and XLM.
    Buys when price drops 2% from recent high, sells when price gains 3%.
    """
    
    INTERFACE_VERSION = 3
    
    # Minimal ROI designed for the strategy - we'll use custom exit logic instead
    minimal_roi = {
        "0": 0.03,  # 3% profit target
    }

    # Optimal stoploss designed for the strategy
    stoploss = -0.05  # 5% stop loss as safety net

    # Optimal timeframe for the strategy - 15 minutes is good balance
    timeframe = '15m'

    # Run "populate_indicators" only for new candle.
    process_only_new_candles = True

    # These values can be overridden in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 20

    # Strategy parameters
    dip_threshold = DecimalParameter(0.015, 0.025, default=0.04, space="buy", decimals=3)
    profit_target = DecimalParameter(0.025, 0.035, default=0.03, space="sell", decimals=3)
    lookback_period = 10  # Number of candles to look back for high/low

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds indicators to the given DataFrame
        """
        # Calculate rolling high and low over lookback period
        dataframe['rolling_high'] = dataframe['high'].rolling(window=self.lookback_period).max()
        dataframe['rolling_low'] = dataframe['low'].rolling(window=self.lookback_period).min()
        
        # Calculate percentage drop from recent high
        dataframe['drop_from_high'] = (dataframe['close'] - dataframe['rolling_high']) / dataframe['rolling_high']
        
        # Calculate percentage gain from recent low
        dataframe['gain_from_low'] = (dataframe['close'] - dataframe['rolling_low']) / dataframe['rolling_low']
        
        # Volume filter - ensure there's some activity
        dataframe['volume_ma'] = dataframe['volume'].rolling(window=10).mean()
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry signal: Buy when price drops 2% from recent high
        """
        dataframe.loc[
            (
                (dataframe['drop_from_high'] <= -self.dip_threshold.value) &  # Price dropped 2% from high
                (dataframe['volume'] > dataframe['volume_ma'] * 0.5) &  # Some volume activity
                (dataframe['volume'] > 0)  # Ensure volume exists
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit signal: Sell when price gains 3% from recent low
        """
        dataframe.loc[
            (
                (dataframe['gain_from_low'] >= self.profit_target.value) &  # Price gained 3% from low
                (dataframe['volume'] > 0)  # Ensure volume exists
            ),
            'exit_long'] = 1

        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                       current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Custom stoploss logic, returning the new distance relative to current_rate
        """
        # If we're in profit, tighten the stop loss
        if current_profit > 0.01:  # 1% profit
            return -0.02  # 2% stop loss
        elif current_profit > 0.02:  # 2% profit
            return -0.01  # 1% stop loss
        
        return self.stoploss  # Default stop loss 