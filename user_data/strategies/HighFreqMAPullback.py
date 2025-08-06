from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import pandas as pd
from datetime import datetime
from freqtrade.persistence import Trade

class HighFreqMAPullback(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = '1m'

    minimal_roi = {
        "0": 0.01,  # 1% target
        "10": 0.005  # 0.5% after 10 minutes
    }

    stoploss = -0.005  # Fixed 0.5% stoploss initially

    trailing_stop = True
    trailing_stop_positive = 0.002
    trailing_stop_positive_offset = 0.005
    trailing_only_offset_is_reached = True

    cooldown_lookback = 5  # Candles to wait after exit before new entry

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ema9'] = ta.EMA(dataframe, timeperiod=9)
        dataframe['ema21'] = ta.EMA(dataframe, timeperiod=21)
        dataframe['engulfing'] = ta.CDLENGULFING(dataframe['open'], dataframe['high'], dataframe['low'], dataframe['close'])  # Keep calculation but not using in entry
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['volume_sma'] = dataframe['volume'].rolling(20).mean()
        # Removed ADX
        dataframe['recent_low'] = dataframe['low'].rolling(window=5).min()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Removed recent_exit calculation as exit_long not available here
        dataframe.loc[
            (dataframe['ema9'] > dataframe['ema21']) &  # Uptrend
            qtpylib.crossed_above(dataframe['close'], dataframe['ema9']) &  # Bounce above EMA9
            (dataframe['close'] > dataframe['open']) &  # Bullish candle for reversal
            (dataframe['rsi'] < 50) &  # Oversold filter (relaxed)
            (dataframe['volume'] > dataframe['volume_sma'] * 1.2) &  # Volume confirmation (relaxed)
            (dataframe['volume'] > 0),  # Guard
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe['close'] < dataframe['ema21']),  # Exit if drops below EMA21
            'exit_long'] = 1

        return dataframe

    use_custom_stoploss = True

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Custom stoploss - set to recent pullback low
        """
        # Get current dataframe
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or len(dataframe) == 0:
            return -1  # Don't change stoploss

        last_candle = dataframe.iloc[-1].squeeze()

        # Calculate relative stoploss based on recent low
        if 'recent_low' in last_candle and not pd.isna(last_candle['recent_low']):
            sl_price = last_candle['recent_low']
            sl_offset = (sl_price / current_rate) - 1
            return sl_offset
        return -1  # Don't change if no data 