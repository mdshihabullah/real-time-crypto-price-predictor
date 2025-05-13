"""Module for data validation using Great Expectations"""

import great_expectations as ge
from loguru import logger


def validate_timeseries_data(df):
    """
    Validate time series data using Great Expectations
    
    Args:
        df (pandas.DataFrame): DataFrame containing time series data
    
    Returns:
        tuple: (is_valid, validation_results)
            - is_valid (bool): Whether the data is valid
            - validation_results (dict): Detailed validation results
    """
    logger.info(f"Validating time series data with shape {df.shape}")
    
    # Convert to Great Expectations DataFrame
    ge_df = ge.from_pandas(df)
    
    # Define expectations
    expectations = [
        # Basic structure expectations
        ge_df.expect_table_row_count_to_be_between(min_value=10, max_value=None),
        
        # Required columns expectations
        ge_df.expect_column_to_exist('pair'),
        ge_df.expect_column_to_exist('open'),
        ge_df.expect_column_to_exist('high'),
        ge_df.expect_column_to_exist('low'),
        ge_df.expect_column_to_exist('close'),
        ge_df.expect_column_to_exist('volume'),
        ge_df.expect_column_to_exist('window_start_ms'),
        ge_df.expect_column_to_exist('window_end_ms'),
        ge_df.expect_column_to_exist('window_in_sec'),
        
        # Technical indicators expectations (sample - assuming these columns exist)
        ge_df.expect_column_to_exist('sma_7'),
        ge_df.expect_column_to_exist('ema_7'),
        ge_df.expect_column_to_exist('rsi_7'),
        
        # Value expectations for required numerical columns
        ge_df.expect_column_values_to_not_be_null('close'),
        ge_df.expect_column_values_to_not_be_null('window_start_ms'),
        ge_df.expect_column_values_to_be_of_type('close', 'float64'),
        ge_df.expect_column_values_to_be_of_type('window_start_ms', 'int64'),
        
        # Value range expectations
        ge_df.expect_column_values_to_be_between('close', min_value=0, max_value=None),
        ge_df.expect_column_values_to_be_between('volume', min_value=0, max_value=None),
        
        # Time series specific expectations
        ge_df.expect_column_values_to_be_increasing('window_start_ms')
    ]
    
    # Run all expectations
    results = []
    is_valid = True
    
    for expectation in expectations:
        result = expectation
        results.append(result)
        
        if not result['success']:
            is_valid = False
            logger.warning(f"Validation failed: {result['expectation_config']['expectation_type']}")
    
    logger.info(f"Data validation {'passed' if is_valid else 'failed'}")
    return is_valid, results


def generate_validation_report(df, report_path=None):
    """
    Generate a validation report for the dataset using Great Expectations
    
    Args:
        df (pandas.DataFrame): DataFrame to validate
        report_path (str, optional): Path to save the validation report
    
    Returns:
        dict: Validation report summary
    """
    logger.info("Generating data validation report")
    
    # Convert to Great Expectations DataFrame
    ge_df = ge.from_pandas(df)
    
    # Create validation report
    validation_result = ge_df.validate()
    
    # Generate comprehensive report
    report = {
        "success": validation_result.success,
        "statistics": {
            "evaluated_expectations": validation_result.statistics["evaluated_expectations"],
            "successful_expectations": validation_result.statistics["successful_expectations"],
            "unsuccessful_expectations": validation_result.statistics["unsuccessful_expectations"],
            "success_percent": validation_result.statistics["success_percent"],
        },
        "results": validation_result.to_json_dict()
    }
    
    # Save report if path is provided
    if report_path:
        import json
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=4)
        logger.info(f"Saved validation report to {report_path}")
    
    return report 