"""Module for data and model drift analysis using Evidently"""

import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from loguru import logger
from evidently import ColumnMapping
from evidently.report import Report
from evidently.metrics import DataDriftTable, DatasetDriftMetric
from evidently.metrics.base_metric import ValueDrift
from evidently.test_suite import TestSuite
from evidently.tests import TestColumnDrift, TestShareOfDriftedColumns

# Define reports output directory
DRIFT_REPORTS_DIR = Path(__file__).resolve().parents[2] / "drift_reports"


def ensure_drift_reports_dir():
    """Ensure drift reports directory exists"""
    os.makedirs(DRIFT_REPORTS_DIR, exist_ok=True)


def analyze_data_drift(current_data, reference_data, 
                      target_column=None, prediction_column=None,
                      cat_features=None, num_features=None):
    """
    Analyze data drift between current and reference datasets
    
    Args:
        current_data (pandas.DataFrame): Current dataset
        reference_data (pandas.DataFrame): Reference dataset (baseline)
        target_column (str, optional): Name of the target column
        prediction_column (str, optional): Name of the prediction column
        cat_features (list, optional): List of categorical features
        num_features (list, optional): List of numerical features
    
    Returns:
        Report: Evidently Report object with data drift analysis
    """
    logger.info(f"Analyzing data drift - current shape: {current_data.shape}, reference shape: {reference_data.shape}")
    
    # Create column mapping
    column_mapping = ColumnMapping()
    
    # Set target and prediction columns if provided
    if target_column:
        column_mapping.target = target_column
        
    if prediction_column:
        column_mapping.prediction = prediction_column
    
    # Set categorical and numerical features if provided
    if cat_features:
        column_mapping.categorical_features = cat_features
    if num_features:
        column_mapping.numerical_features = num_features
    else:
        # Use all numeric columns except target/prediction as numerical features
        exclude_cols = [col for col in [target_column, prediction_column] if col]
        column_mapping.numerical_features = [
            col for col in current_data.select_dtypes(include=['number']).columns 
            if col not in exclude_cols
        ]
    
    # Create data drift report
    report = Report(metrics=[
        DatasetDriftMetric(),
        DataDriftTable()
    ])
    
    # Add value drift metrics for important columns
    if "close" in current_data.columns:
        report.add_metric(ValueDrift(column_name="close"))
    
    # Run the report
    report.run(
        reference_data=reference_data,
        current_data=current_data,
        column_mapping=column_mapping
    )
    
    logger.info("Data drift analysis completed")
    return report


def generate_drift_report(current_data, reference_data, pair_name,
                         target_column=None, prediction_column=None,
                         save_html=True, save_json=False):
    """
    Generate comprehensive drift report for a cryptocurrency pair
    
    Args:
        current_data (pandas.DataFrame): Current dataset
        reference_data (pandas.DataFrame): Reference dataset (baseline)
        pair_name (str): Name of cryptocurrency pair (e.g., 'BTC/EUR')
        target_column (str, optional): Name of the target column
        prediction_column (str, optional): Name of the prediction column
        save_html (bool): Whether to save the report as HTML
        save_json (bool): Whether to save the report as JSON
    
    Returns:
        dict: Dictionary mapping report types to (report, path) tuples
    """
    logger.info(f"Generating drift reports for pair: {pair_name}")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Format pair name for filenames
    pair_file_name = pair_name.replace('/', '_')
    
    # Create column mapping
    column_mapping = ColumnMapping()
    
    # Set target and prediction
    if target_column:
        column_mapping.target = target_column
    if prediction_column:
        column_mapping.prediction = prediction_column
    
    # Detect categorical and numerical features
    cat_features = current_data.select_dtypes(include=['object', 'category']).columns.tolist()
    num_features = current_data.select_dtypes(include=['int64', 'float64']).columns.tolist()
    
    # Remove target and prediction columns from features if they exist
    for col in [target_column, prediction_column]:
        if col and col in cat_features:
            cat_features.remove(col)
        if col and col in num_features:
            num_features.remove(col)
    
    column_mapping.categorical_features = cat_features
    column_mapping.numerical_features = num_features
    
    # Ensure reports directory exists
    ensure_drift_reports_dir()
    
    # Create data drift report
    data_drift_report = Report(metrics=[
        DatasetDriftMetric(),
        DataDriftTable()
    ])
    
    # Add value drift metrics for important columns
    if "close" in current_data.columns:
        data_drift_report.add_metric(ValueDrift(column_name="close"))
    
    # Run the report
    data_drift_report.run(
        reference_data=reference_data, 
        current_data=current_data,
        column_mapping=column_mapping
    )
    
    # Create data drift test suite
    data_drift_suite = TestSuite(tests=[
        TestShareOfDriftedColumns(),
        TestColumnDrift(column_name="close") if "close" in current_data.columns else None
    ])
    
    # Filter out None tests
    data_drift_suite.tests = [test for test in data_drift_suite.tests if test]
    
    # Run the test suite
    data_drift_suite.run(
        reference_data=reference_data,
        current_data=current_data,
        column_mapping=column_mapping
    )
    
    html_path = None
    json_path = None
    
    # Save HTML report
    if save_html:
        html_path = DRIFT_REPORTS_DIR / f"data_drift_{pair_file_name}_{timestamp}.html"
        logger.info(f"Saving HTML data drift report to {html_path}")
        data_drift_report.save_html(str(html_path))
        
        # Save test suite HTML
        test_html_path = DRIFT_REPORTS_DIR / f"data_drift_tests_{pair_file_name}_{timestamp}.html"
        data_drift_suite.save_html(str(test_html_path))
    
    # Save JSON report
    if save_json:
        json_path = DRIFT_REPORTS_DIR / f"data_drift_{pair_file_name}_{timestamp}.json"
        logger.info(f"Saving JSON data drift report to {json_path}")
        data_drift_report.save_json(str(json_path))
        
        # Save test suite JSON
        test_json_path = DRIFT_REPORTS_DIR / f"data_drift_tests_{pair_file_name}_{timestamp}.json"
        data_drift_suite.save_json(str(test_json_path))
    
    reports = {
        'data_drift': (data_drift_report, html_path, json_path),
        'data_drift_tests': (data_drift_suite, 
                            DRIFT_REPORTS_DIR / f"data_drift_tests_{pair_file_name}_{timestamp}.html" if save_html else None,
                            DRIFT_REPORTS_DIR / f"data_drift_tests_{pair_file_name}_{timestamp}.json" if save_json else None)
    }
    
    return reports


def compare_models_performance(reference_model_preds, current_model_preds, actual_values, pair_name):
    """
    Compare performance of baseline and candidate models
    
    Args:
        reference_model_preds (pandas.Series): Predictions from reference model
        current_model_preds (pandas.Series): Predictions from current model
        actual_values (pandas.Series): Actual target values
        pair_name (str): Name of cryptocurrency pair (e.g., 'BTC/EUR')
    
    Returns:
        tuple: (report, path)
            - report: Evidently Report object with model comparison
            - path: Path to saved HTML report, if saved
    """
    logger.info(f"Comparing model performance for pair: {pair_name}")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Format pair name for filenames
    pair_file_name = pair_name.replace('/', '_')
    
    # Create DataFrames with predictions and actuals
    df_reference = pd.DataFrame({
        'prediction': reference_model_preds,
        'target': actual_values
    })
    
    df_current = pd.DataFrame({
        'prediction': current_model_preds,
        'target': actual_values
    })
    
    # Create column mapping
    column_mapping = ColumnMapping()
    column_mapping.target = 'target'
    column_mapping.prediction = 'prediction'
    
    # Import metrics for regression models
    from evidently.metrics import RegressionQualityMetric, RegressionPredictedVsActualScatter
    
    # Create regression performance report
    report = Report(metrics=[
        RegressionQualityMetric(),
        RegressionPredictedVsActualScatter()
    ])
    
    # Run the report
    report.run(
        reference_data=df_reference,
        current_data=df_current,
        column_mapping=column_mapping
    )
    
    # Ensure reports directory exists
    ensure_drift_reports_dir()
    
    # Save HTML report
    html_path = DRIFT_REPORTS_DIR / f"model_comparison_{pair_file_name}_{timestamp}.html"
    logger.info(f"Saving HTML model comparison report to {html_path}")
    report.save_html(str(html_path))
    
    return report, html_path


def analyze_model_drift_over_time(model, X_data, y_true, window_size=7, step_size=1):
    """
    Analyze model drift over time by measuring performance in sliding windows
    
    Args:
        model: Trained model
        X_data (pandas.DataFrame): Feature DataFrame, time ordered
        y_true (pandas.Series): True target values
        window_size (int): Size of each window in days
        step_size (int): Step size between windows in days
    
    Returns:
        pandas.DataFrame: DataFrame with model performance metrics over time
    """
    logger.info(f"Analyzing model drift over time with window size: {window_size} days, "
               f"step size: {step_size} days")
    
    # Ensure data has a timestamp column
    if 'timestamp' not in X_data.columns:
        if 'window_start_ms' in X_data.columns:
            X_data = X_data.copy()
            X_data['timestamp'] = pd.to_datetime(X_data['window_start_ms'], unit='ms')
        else:
            raise ValueError("X_data must have either 'timestamp' or 'window_start_ms' column")
    
    # Get predictions for all data
    y_pred = model.predict(X_data.drop(columns=['timestamp'], errors='ignore'))
    
    # Convert window size and step size to timedeltas
    window_td = pd.Timedelta(days=window_size)
    step_td = pd.Timedelta(days=step_size)
    
    # Calculate start and end dates for each window
    start_date = X_data['timestamp'].min()
    end_date = X_data['timestamp'].max()
    
    # Create list of window start dates
    window_starts = []
    current_date = start_date
    while current_date + window_td <= end_date:
        window_starts.append(current_date)
        current_date += step_td
    
    # Calculate metrics for each window
    import numpy as np
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    
    metrics_over_time = []
    
    for window_start in window_starts:
        window_end = window_start + window_td
        
        # Get indices for data in this window
        window_mask = (X_data['timestamp'] >= window_start) & (X_data['timestamp'] < window_end)
        
        if window_mask.sum() == 0:
            continue  # Skip if window has no data
        
        # Get predictions and true values for this window
        window_y_pred = y_pred[window_mask]
        window_y_true = y_true[window_mask]
        
        # Calculate metrics
        mae = mean_absolute_error(window_y_true, window_y_pred)
        rmse = np.sqrt(mean_squared_error(window_y_true, window_y_pred))
        r2 = r2_score(window_y_true, window_y_pred)
        
        # Add to metrics list
        metrics_over_time.append({
            'window_start': window_start,
            'window_end': window_end,
            'n_samples': window_mask.sum(),
            'mae': mae,
            'rmse': rmse,
            'r2': r2
        })
    
    # Convert to DataFrame
    metrics_df = pd.DataFrame(metrics_over_time)
    
    logger.info(f"Model drift analysis completed with {len(metrics_df)} windows")
    
    return metrics_df 