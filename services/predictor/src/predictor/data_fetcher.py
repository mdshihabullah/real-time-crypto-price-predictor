"""Module for fetching data from RisingWave database"""

import pandas as pd
from loguru import logger
from risingwave import OutputFormat, RisingWave, RisingWaveConnOptions

from predictor.config import config


def get_db_connection():
    """Create a database connection to RisingWave"""
    logger.info(
        f"Connecting to RisingWave DB at {config.risingwave_host}:\
                {config.risingwave_port}"
    )
    # Connect to RisingWave instance on localhost with named parameters
    rw_conn = RisingWave(
        RisingWaveConnOptions.from_connection_info(
            host=config.risingwave_host,
            port=config.risingwave_port,
            user=config.risingwave_user,
            password=config.risingwave_password,
            database=config.risingwave_db,
        )
    )
    return rw_conn


def get_available_pairs():
    """
    Fetch all available cryptocurrency pairs from RisingWave database

    Returns:
        list: List of available pairs
    """
    conn = get_db_connection()

    query = "SELECT DISTINCT pair FROM public.technical_indicators"

    try:
        result: pd.DataFrame = conn.fetch(query, format=OutputFormat.DATAFRAME)
        pairs = result["pair"].tolist()
        logger.info(f"Retrieved {len(pairs)} available pairs: {pairs}")
        return pairs
    except Exception as e:
        logger.error(f"Error fetching available pairs from RisingWave: {e}")
        raise


def fetch_technical_indicators_data(pair=None, limit=None):
    """
    Fetch technical indicators from RisingWave database

    Args:
        pair (str, optional): Specific pair to fetch (e.g., 'BTC/EUR').
                             If None, fetch data for all pairs.
        limit (int, optional): Limit the number of rows returned.

    Returns:
        pandas.DataFrame: DataFrame containing technical indicators
    """
    conn = get_db_connection()

    query = "SELECT * FROM public.technical_indicators"

    if pair:
        query += f" WHERE pair = '{pair}'"

    query += " ORDER BY window_start_ms DESC"

    if limit:
        query += f" LIMIT {limit}"

    logger.info(f"Executing query: {query}")

    try:
        result: pd.DataFrame = conn.fetch(query, format=OutputFormat.DATAFRAME)
        logger.info(f"Retrieved {len(result)} rows of technical indicators data")
        
        # Convert timestamp columns to datetime for easier handling
        if not result.empty and "window_start_ms" in result.columns:
            result["timestamp"] = pd.to_datetime(result["window_start_ms"], unit="ms")
        
        return result
    except Exception as e:
        logger.error(f"Error fetching data from RisingWave: {e}")
        raise


def fetch_pair_data_last_n_days(pair, days_back=None):
    """
    Fetch technical indicators for a specific pair within a timeframe

    Args:
        pair (str): Cryptocurrency pair (e.g., 'BTC/EUR')
        days_back (int, optional): Number of days back to fetch data for.
                                  If None, fetch all available data.

    Returns:
        pandas.DataFrame: DataFrame containing technical indicators for the pair
    """
    conn = get_db_connection()

    query = f"SELECT * FROM public.technical_indicators WHERE pair = '{pair}'"

    if days_back:
        # Convert days to milliseconds
        ms_back = days_back * 24 * 60 * 60 * 1000
        current_time_ms = pd.Timestamp.now().timestamp() * 1000
        cutoff_time_ms = current_time_ms - ms_back

        query += f" AND window_start_ms > {cutoff_time_ms}"

    query += " ORDER BY window_start_ms ASC"

    logger.info(f"Executing query: {query}")

    try:
        result: pd.DataFrame = conn.fetch(query, format=OutputFormat.DATAFRAME)
        logger.info(f"Retrieved {len(result)} rows for pair {pair}")

        # Convert timestamp columns to datetime for easier handling
        if not result.empty:
            result["timestamp"] = pd.to_datetime(result["window_start_ms"], unit="ms")

        return result
    except Exception as e:
        logger.error(f"Error fetching data for pair {pair}: {e}")
        raise
