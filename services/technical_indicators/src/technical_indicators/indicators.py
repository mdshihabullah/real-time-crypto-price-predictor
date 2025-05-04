"""Module for computing technical indicators"""

import numpy as np
from loguru import logger
from talib import stream

from technical_indicators.config import config


def compute_technical_indicators(
    candle: dict,
    state: dict,
):
    """
    Computes technical indicators from the candles in the state dictionary.

    Args:
        candle (dict): The current candle data
        state (dict): Dictionary containing historical candles data

    Returns:
        indicators (dict): Dictionary with the computed technical indicators
    """


    # Extract the candles from the state dictionary
    candles = state.get('candles', default=[])

    logger.debug(f'Number of candles in state: {len(candles)}')

    # Extract the open, close, high, low, volume candles: List[dict]
    # into numpy arrays, because this is the type TA-Lib expects to compute indicators
    _open = np.array([c['open'] for c in candles])
    _high = np.array([c['high'] for c in candles])
    _low = np.array([c['low'] for c in candles])
    close = np.array([c['close'] for c in candles])
    volume = np.array([c['volume'] for c in candles])

    indicators = {}

    # Simple Moving Average (SMA) for configured periods
    for period in config.periods:
        # Skip if we don't have enough data points
        if len(close) >= period:
            indicators[f'sma_{period}'] = stream.SMA(close, timeperiod=period)
            # Exponential Moving Average (EMA) for different periods
            indicators[f'ema_{period}'] = stream.EMA(close, timeperiod=period)
            # Relative Strength Index (RSI) for different periods
            indicators[f'rsi_{period}'] = stream.RSI(close, timeperiod=period)
            #Average Directional Movement Index (ADX) for different periods
            indicators[f'adx_{period}'] = stream.ADX(_high,
                                                     _low,
                                                     close,
                                                     timeperiod= period)
            # Moving Average Convergence Divergence (MACD) for different periods
            indicators[f'macd_{period}'], \
            indicators[f'macdsignal_{period}'], \
            indicators[f'macdhist_{period}'] = \
            stream.MACD(close,
                        fastperiod=period,
                        slowperiod=2*period,
                        signalperiod=period)
        else:
            logger.debug(f"Needed {period} but have {len(close)} candles")
            indicators[f'sma_{period}'] = None
            indicators[f'ema_{period}'] = None
            indicators[f'rsi_{period}'] = None
            indicators[f'adx_{period}'] = None
            indicators[f'macd_{period}'] = None
            indicators[f'macdsignal_{period}'] = None
            indicators[f'macdhist_{period}'] = None

    # On-Balance Volume (OBV)
    indicators['obv'] = stream.OBV(close, volume)

    return {
        **candle,
        **indicators,
    }
