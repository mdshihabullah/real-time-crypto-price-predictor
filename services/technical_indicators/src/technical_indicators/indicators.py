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
        dict: Dictionary with the computed technical indicators
    """


    # Extract the candles from the state dictionary
    candles = state.get('candles', default=[])

    logger.debug(f'Number of candles in state: {len(candles)}')

    # Extract the open, close, high, low, volume candles (which is a list of dictionaries)
    # into numpy arrays, because this is the type that TA-Lib expects to compute the indicators
    _open = np.array([c['open'] for c in candles])
    _high = np.array([c['high'] for c in candles])
    _low = np.array([c['low'] for c in candles])
    close = np.array([c['close'] for c in candles])
    _volume = np.array([c['volume'] for c in candles])

    indicators = {}

    # Simple Moving Average (SMA) for configured periods
    for period in config.sma_periods:
        # Skip if we don't have enough data points
        if len(close) >= period:
            indicators[f'sma_{period}'] = stream.SMA(close, timeperiod=period)
        else:
            logger.debug(f"Not enough data for SMA_{period}, needed {period} points but have {len(close)}")  # noqa: E501
            indicators[f'sma_{period}'] = None

    return {
        **candle,
        **indicators,
    }
