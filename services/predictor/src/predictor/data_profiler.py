"""Module for data profiling using ydata-profiling"""

import os
from datetime import datetime
from pathlib import Path

from loguru import logger
from ydata_profiling import ProfileReport

# Define report output directory
REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports"


def ensure_reports_dir():
    """Ensure reports directory exists"""
    os.makedirs(REPORTS_DIR, exist_ok=True)


def profile_dataframe(df, title=None, minimal=False):
    """
    Generate a profile report for a DataFrame
    
    Args:
        df (pandas.DataFrame): DataFrame to profile
        title (str, optional): Title for the profile report
        minimal (bool): Whether to use minimal mode (faster, less detailed)
    
    Returns:
        ProfileReport: Profile report object
    """
    if title is None:
        title = f"Data Profile Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    logger.info(f"Generating profile report: {title}, shape: {df.shape}")
    
    # Configure profile settings based on minimal flag
    config_kwargs = {}
    if minimal:
        config_kwargs = {
            "explorative": {
                "mode": False  # Equivalent to minimal=True in older versions
            }
        }
    
    # Generate profile report
    profile = ProfileReport(
        df, 
        title=title,
        **config_kwargs
    )
    
    logger.info(f"Profile report generated: {title}")
    return profile


def profile_timeframe_data(df, pair_name, timestamp=None, save_html=True, save_json=False):
    """
    Profile time series data for a specific pair and timeframe
    
    Args:
        df (pandas.DataFrame): DataFrame containing time series data
        pair_name (str): Name of cryptocurrency pair (e.g., 'BTC/EUR')
        timestamp (str, optional): Timestamp string for the report
        save_html (bool): Whether to save the report as HTML
        save_json (bool): Whether to save the report as JSON
    
    Returns:
        tuple: (profile, html_path, json_path)
            - profile (ProfileReport): The profile report object
            - html_path (str or None): Path to saved HTML report, if saved
            - json_path (str or None): Path to saved JSON report, if saved
    """
    if timestamp is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Format pair name for filenames
    pair_file_name = pair_name.replace('/', '_')
    
    # Generate profile report
    report_title = f"Crypto Profile Report - {pair_name} - {timestamp}"
    profile = profile_dataframe(df, title=report_title)
    
    html_path = None
    json_path = None
    
    # Ensure reports directory exists
    ensure_reports_dir()
    
    # Save HTML report
    if save_html:
        html_path = REPORTS_DIR / f"profile_{pair_file_name}_{timestamp}.html"
        logger.info(f"Saving HTML profile report to {html_path}")
        profile.to_file(str(html_path))
    
    # Save JSON report
    if save_json:
        json_path = REPORTS_DIR / f"profile_{pair_file_name}_{timestamp}.json"
        logger.info(f"Saving JSON profile data to {json_path}")
        profile.to_file(str(json_path))
    
    return profile, html_path, json_path


def profile_multiple_pairs(pairs_data_dict, timestamp=None, save_html=True):
    """
    Generate profile reports for multiple cryptocurrency pairs
    
    Args:
        pairs_data_dict (dict): Dictionary mapping pair names to their DataFrames
        timestamp (str, optional): Timestamp string for the reports
        save_html (bool): Whether to save the reports as HTML
    
    Returns:
        dict: Dictionary mapping pair names to their (profile, path) tuples
    """
    if timestamp is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    results = {}
    
    for pair_name, df in pairs_data_dict.items():
        logger.info(f"Profiling data for pair: {pair_name}, shape: {df.shape}")
        profile, html_path, _ = profile_timeframe_data(
            df, 
            pair_name=pair_name,
            timestamp=timestamp,
            save_html=save_html,
            save_json=False
        )
        results[pair_name] = (profile, html_path)
    
    return results 