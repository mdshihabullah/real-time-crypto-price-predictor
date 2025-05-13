"""Module for data preprocessing"""

import numpy as np
import pandas as pd
from loguru import logger
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler, RobustScaler

from predictor.config import config


def handle_missing_values(df, method="ffill", drop_threshold=0.8):
    """
    Handle missing values in the dataframe

    Args:
        df (pandas.DataFrame): Input DataFrame
        method (str): Method to handle missing values ('ffill', 'bfill', 'interpolate', 'drop')
        drop_threshold (float): Threshold for dropping columns with too many missing values

    Returns:
        pandas.DataFrame: DataFrame with handled missing values
    """
    logger.info(f"Handling missing values using method: {method}")

    # Create a copy to avoid modifying the original dataframe
    df_clean = df.copy()

    # Drop columns with too many missing values
    if drop_threshold < 1.0:
        missing_ratio = df_clean.isnull().mean()
        cols_to_drop = missing_ratio[missing_ratio > drop_threshold].index
        if len(cols_to_drop) > 0:
            logger.info(
                f"Dropping columns with > {drop_threshold * 100}% missing values: {list(cols_to_drop)}"
            )
            df_clean = df_clean.drop(columns=cols_to_drop)

    # Handle remaining missing values
    if method == "ffill":
        # Forward fill with backfill for any remaining NAs at the beginning
        df_clean = df_clean.ffill().bfill()
    elif method == "bfill":
        # Backward fill with forward fill for any remaining NAs at the end
        df_clean = df_clean.bfill().ffill()
    elif method == "interpolate":
        # Interpolate missing values
        df_clean = df_clean.interpolate(method="time").ffill().bfill()
    elif method == "drop":
        # Drop rows with any missing values
        df_clean = df_clean.dropna()

    # Log the results
    initial_missing = df.isnull().sum().sum()
    final_missing = df_clean.isnull().sum().sum()
    logger.info(f"Missing values: {initial_missing} -> {final_missing}")

    return df_clean


def create_target_variable(df, prediction_horizon, target_column=None):
    """
    Create target variable for prediction based on the horizon

    Args:
        df (pandas.DataFrame): Input DataFrame
        prediction_horizon (int): Prediction horizon in minutes
        target_column (str, optional): Name for the target column

    Returns:
        pandas.DataFrame: DataFrame with added target variable
    """
    if target_column is None:
        target_column = f"future_close_{prediction_horizon}m"

    logger.info(
        f"Creating target variable '{target_column}' with {prediction_horizon}m horizon"
    )

    # Create a copy to avoid modifying the original dataframe
    df_with_target = df.copy()

    # Create the target variable based on future close prices
    df_with_target[target_column] = df_with_target["close"].shift(-prediction_horizon)

    # Drop rows where the target is NaN (at the end of the dataset)
    rows_before = len(df_with_target)
    df_with_target = df_with_target.dropna(subset=[target_column])
    rows_after = len(df_with_target)

    logger.info(
        f"Created target variable. Dropped {rows_before - rows_after} rows with NaN targets."
    )

    return df_with_target


def scale_features(df, features_to_scale=None, scaler_type="standard"):
    """
    Scale numerical features in the DataFrame

    Args:
        df (pandas.DataFrame): Input DataFrame
        features_to_scale (list, optional): List of features to scale
                                          If None, scale all numeric features
        scaler_type (str): Type of scaler to use
                         'standard': StandardScaler
                         'robust': RobustScaler

    Returns:
        tuple: (scaled_df, scaler)
            - scaled_df (pandas.DataFrame): DataFrame with scaled features
            - scaler (object): Fitted scaler object
    """
    logger.info(f"Scaling features with scaler type: {scaler_type}")

    # Create a copy to avoid modifying the original DataFrame
    df_scaled = df.copy()

    # If no features specified, use all numeric features
    if features_to_scale is None:
        features_to_scale = df.select_dtypes(
            include=["float64", "int64"]
        ).columns.tolist()
        # Exclude timestamp and window columns
        features_to_scale = [
            col
            for col in features_to_scale
            if not any(
                exclude in col
                for exclude in ["timestamp", "window", "_ms", "future_close"]
            )
        ]

    logger.info(f"Scaling {len(features_to_scale)} features")

    # Choose scaler
    if scaler_type == "standard":
        scaler = StandardScaler()
    elif scaler_type == "robust":
        scaler = RobustScaler()
    else:
        raise ValueError(f"Unknown scaler type: {scaler_type}")

    # Scale features
    df_scaled[features_to_scale] = scaler.fit_transform(df[features_to_scale])

    return df_scaled, scaler


def prepare_time_series_data(
    df, prediction_horizon=None, handle_na_strategy="interpolate", scale=True
):
    """
    Prepare time series data for machine learning

    Args:
        df (pandas.DataFrame): Input DataFrame with time series data
        prediction_horizon (int, optional): Number of minutes in the future to predict
        handle_na_strategy (str): Strategy to handle missing values
        scale (bool): Whether to scale features

    Returns:
        tuple: (X, y, scaler)
            - X (pandas.DataFrame): Feature DataFrame
            - y (pandas.Series): Target Series
            - scaler (object): Fitted scaler object (None if scale=False)
    """
    logger.info(f"Preparing time series data with shape: {df.shape}")

    # Handle missing values
    df_cleaned = handle_missing_values(df, method=handle_na_strategy)

    # Sort the dataframe by the value of window_start_ms if it exists
    if "window_start_ms" in df_cleaned.columns:
        df_cleaned = df_cleaned.sort_values(by="window_start_ms")

    # Create target variable
    df_with_target = create_target_variable(df_cleaned, prediction_horizon)

    # Define features and target
    # Get the actual target column name
    target_column = f"future_close_{prediction_horizon}m"

    # Define features and target
    X = df_with_target.drop(columns=[target_column])
    y = df_with_target[target_column]

    # Drop non-feature columns if they exist
    cols_to_drop = ["timestamp", "created_at"]
    X = X.drop(columns=[col for col in cols_to_drop if col in X.columns])

    # Scale features if required
    scaler = None
    if scale:
        X, scaler = scale_features(X)

    logger.info(f"Prepared time series data. X shape: {X.shape}, y shape: {y.shape}")

    return X, y, scaler


def split_timeseries_data(features_df, n_splits=5, test_size=None):
    """
    Split time series data into train/validation/test sets using TimeSeriesSplit

    Args:
        features_df (pandas.DataFrame): Input DataFrame with time-ordered features
        n_splits (int): Number of splits for TimeSeriesSplit
        test_size (int, optional): Size of each test set. If None, will use len(df)//(n_splits+1)

    Returns:
        tuple: (X_train, X_val, X_test)
            - X_train (pandas.DataFrame): Training features
            - X_val (pandas.DataFrame): Validation features
            - X_test (pandas.DataFrame): Testing features
    """
    logger.info(
        f"Splitting time series data with TimeSeriesSplit (n_splits={n_splits})"
    )

    # Sort the dataframe by the value of window_start_ms if it exists
    if "window_start_ms" in features_df.columns:
        features_df = features_df.sort_values(by="window_start_ms")

    # Initialize TimeSeriesSplit
    tscv = TimeSeriesSplit(n_splits=n_splits, test_size=test_size)

    # Get the splits
    splits = list(tscv.split(features_df))

    # Use the last split for final train/validation/test
    # The second-to-last split will be used for validation
    if len(splits) >= 2:
        # For the train set, use all data before the validation set
        train_idx, _ = splits[-2]
        # For validation, use the test set from the second-to-last split
        _, val_idx = splits[-2]
        # For the test set, use the test set from the last split
        _, test_idx = splits[-1]

        # Split the dataframe
        X_train = features_df.iloc[train_idx].copy()
        X_val = features_df.iloc[val_idx].copy()
        X_test = features_df.iloc[test_idx].copy()

        logger.info(
            f"Split data - train: {len(X_train)}, validation: {len(X_val)}, test: {len(X_test)}"
        )

        return X_train, X_val, X_test
    else:
        logger.warning(
            f"Not enough data for {n_splits} splits. Using simple ratio split."
        )
        # Fallback to a simple ratio-based split
        train_size = int(len(features_df) * 0.7)
        val_size = int(len(features_df) * 0.15)

        X_train = features_df.iloc[:train_size].copy()
        X_val = features_df.iloc[train_size : train_size + val_size].copy()
        X_test = features_df.iloc[train_size + val_size :].copy()

        logger.info(
            f"Split data - train: {len(X_train)}, validation: {len(X_val)}, test: {len(X_test)}"
        )

        return X_train, X_val, X_test


def create_feature_matrix(df, target_column):
    """
    Create feature matrix and target variable from DataFrame

    Args:
        df (pandas.DataFrame): Input DataFrame
        target_column (str): Name of the target column

    Returns:
        tuple: (X, y)
            - X (pandas.DataFrame): Feature matrix
            - y (pandas.Series): Target variable
    """
    logger.info(f"Creating feature matrix with target column: {target_column}")

    # Create a copy to avoid modifying the original dataframe
    df_copy = df.copy()

    # Separate target variable
    if target_column in df_copy.columns:
        y = df_copy[target_column].copy()
        X = df_copy.drop(columns=[target_column])
    else:
        logger.warning(f"Target column '{target_column}' not found in DataFrame")
        y = None
        X = df_copy

    # Remove any timestamp columns that shouldn't be used as features
    timestamp_cols = [
        col
        for col in X.columns
        if "timestamp" in col.lower() or "time" in col.lower() or "date" in col.lower()
    ]
    if timestamp_cols:
        logger.info(f"Removing timestamp columns from features: {timestamp_cols}")
        X = X.drop(columns=timestamp_cols, errors="ignore")

    # Remove any other non-numeric columns
    non_numeric_cols = X.select_dtypes(exclude=["number"]).columns.tolist()
    if non_numeric_cols:
        logger.info(f"Removing non-numeric columns from features: {non_numeric_cols}")
        X = X.drop(columns=non_numeric_cols, errors="ignore")

    logger.info(f"Created feature matrix with shape: {X.shape}")

    return X, y


def normalize_features(train_X, val_X=None, test_X=None):
    """
    Normalize features using StandardScaler

    Args:
        train_X (pandas.DataFrame): Training features
        val_X (pandas.DataFrame, optional): Validation features
        test_X (pandas.DataFrame, optional): Testing features

    Returns:
        tuple: (train_X_scaled, val_X_scaled, test_X_scaled, scaler)
            - train_X_scaled (pandas.DataFrame): Scaled training features
            - val_X_scaled (pandas.DataFrame): Scaled validation features (if provided)
            - test_X_scaled (pandas.DataFrame): Scaled testing features (if provided)
            - scaler (StandardScaler): Fitted scaler
    """
    logger.info("Normalizing features using StandardScaler")

    # Initialize scaler
    scaler = StandardScaler()

    # Fit scaler on training data
    scaler.fit(train_X)

    # Transform data
    train_X_scaled = pd.DataFrame(
        scaler.transform(train_X), columns=train_X.columns, index=train_X.index
    )

    result = [train_X_scaled]

    # Transform validation data if provided
    if val_X is not None:
        val_X_scaled = pd.DataFrame(
            scaler.transform(val_X), columns=val_X.columns, index=val_X.index
        )
        result.append(val_X_scaled)
    else:
        result.append(None)

    # Transform test data if provided
    if test_X is not None:
        test_X_scaled = pd.DataFrame(
            scaler.transform(test_X), columns=test_X.columns, index=test_X.index
        )
        result.append(test_X_scaled)
    else:
        result.append(None)

    # Add scaler to result
    result.append(scaler)

    return tuple(result)


def create_lagged_features(df, lag_columns, lag_periods):
    """
    Create lagged features for time series forecasting

    Args:
        df (pandas.DataFrame): Input DataFrame
        lag_columns (list): List of column names to create lags for
        lag_periods (list): List of lag periods

    Returns:
        pandas.DataFrame: DataFrame with added lagged features
    """
    logger.info(
        f"Creating lagged features for columns: {lag_columns}, lag periods: {lag_periods}"
    )

    # Create a copy to avoid modifying the original dataframe
    df_lagged = df.copy()

    # Create lagged features
    for col in lag_columns:
        if col in df.columns:
            for lag in lag_periods:
                df_lagged[f"{col}_lag_{lag}"] = df_lagged[col].shift(lag)
        else:
            logger.warning(f"Column '{col}' not found in DataFrame")

    # Drop rows with NaN values (from the beginning)
    rows_before = len(df_lagged)
    df_lagged = df_lagged.dropna()
    rows_after = len(df_lagged)

    logger.info(
        f"Created lagged features. Dropped {rows_before - rows_after} rows with NaN values."
    )

    return df_lagged
