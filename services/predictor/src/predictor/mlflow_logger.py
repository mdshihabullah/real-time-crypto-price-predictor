"""
This module provides functionality to log data and profile reports to MLflow.

It includes functions to:
- Set up MLflow tracking
- Log data and profile reports for specific cryptocurrency pairs
"""

import os
import tempfile
import contextlib
from datetime import datetime
from typing import List, Optional, Dict, Union, Any, Generator, Tuple

import mlflow
import pandas as pd
import ydata_profiling
from loguru import logger

from predictor.config import config


def setup_mlflow():
    """Set up MLflow tracking"""
    tracking_uri = (
        f"http://{config.mlflow_tracking_username}:"
        f"{config.mlflow_tracking_password}@"
        f"{config.mlflow_tracking_uri}"
    )
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_registry_uri(tracking_uri)

    logger.info(f"MLflow configured with tracking URI: {config.mlflow_tracking_uri}")


def get_or_create_experiment(pair_name: str) -> str:
    """
    Get or create an MLflow experiment for a specific cryptocurrency pair.

    Args:
        pair_name (str): Name of the cryptocurrency pair

    Returns:
        str: The experiment ID
    """
    # Create experiment name
    experiment_name = f"{config.mlflow_experiment_name}_{pair_name.replace('/', '_')}"
    client = mlflow.tracking.MlflowClient()

    # First, check for active experiments with this name
    experiment = mlflow.get_experiment_by_name(experiment_name)

    if experiment is None:
        # No experiment found - try to create a new one
        try:
            experiment_id = mlflow.create_experiment(experiment_name)
            logger.info(f"Created new experiment: {experiment_name}")
            return experiment_id
        except mlflow.exceptions.RestException as e:
            # If creation failed, it might exist but be deleted
            if "RESOURCE_ALREADY_EXISTS" not in str(e):
                raise
            logger.warning(
                f"Experiment '{experiment_name}' exists but may be deleted or inaccessible"
            )

    # If we get here, the experiment either exists (active or deleted) or creation failed
    # Let's search for it, including deleted ones
    all_experiments = client.search_experiments()
    for exp in all_experiments:
        if exp.name == experiment_name:
            # Found the experiment - check its status
            if exp.lifecycle_stage == "deleted":
                logger.info(
                    f"Found deleted experiment '{experiment_name}' - restoring it"
                )
                # Get the ID before restoring
                experiment_id = exp.experiment_id

                # Restore the experiment
                client.restore_experiment(experiment_id)

                # Verify restoration worked
                restored_exp = client.get_experiment(experiment_id)
                if restored_exp.lifecycle_stage != "active":
                    # If restoration failed, create a new experiment with a slightly different name
                    new_name = (
                        f"{experiment_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    )
                    logger.warning(
                        f"Restoration failed, creating new experiment: {new_name}"
                    )
                    experiment_id = mlflow.create_experiment(new_name)
                return experiment_id
            else:
                # Experiment exists and is active
                logger.info(f"Using existing experiment: {experiment_name}")
                return exp.experiment_id

    # If we get here, the experiment wasn't found in the list but couldn't be created
    # Create one with a timestamp to avoid conflicts
    new_name = f"{experiment_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger.warning(f"Creating new experiment with timestamp: {new_name}")
    experiment_id = mlflow.create_experiment(new_name)
    return experiment_id


# Dictionary to keep track of pair-specific parent runs
_PAIR_PARENT_RUNS = {}


@contextlib.contextmanager
def active_run(
    pair_name: str, run_name: Optional[str] = None, run_id: Optional[str] = None
) -> Generator[mlflow.ActiveRun, None, None]:
    """
    Get or create an MLflow run within the appropriate experiment for a cryptocurrency pair.

    This function will either:
    1. Create a new parent run if one doesn't exist for this pair
    2. Use an existing parent run if available
    3. Use a specific run ID if provided

    Args:
        pair_name (str): Name of the cryptocurrency pair
        run_name (str, optional): Name of the run, defaults to pair_name_timestamp
        run_id (str, optional): Specific run ID to use, if provided

    Yields:
        mlflow.ActiveRun: The active MLflow run
    """
    # Get or create the experiment
    experiment_id = get_or_create_experiment(pair_name)

    # Set the experiment
    try:
        mlflow.set_experiment(experiment_id=experiment_id)
        logger.debug(f"Set active experiment ID: {experiment_id}")
    except Exception as e:
        logger.error(f"Error setting experiment: {str(e)}")
        # Try creating a new experiment with timestamp as fallback
        new_name = f"{config.mlflow_experiment_name}_{pair_name.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        experiment_id = mlflow.create_experiment(new_name)
        mlflow.set_experiment(experiment_id=experiment_id)
        logger.warning(f"Created fallback experiment: {new_name}")

    # Generate run name if not provided
    if run_name is None:
        run_name = f"{pair_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # If a specific run_id is provided, use it
    if run_id is not None:
        try:
            # Use the provided run_id
            with mlflow.start_run(run_id=run_id) as run:
                logger.debug(f"Using provided run ID: {run_id}")
                yield run
                return
        except Exception as e:
            logger.error(f"Error using provided run ID {run_id}: {str(e)}")
            # Fall through to other options

    # Check if we already have a parent run for this pair
    parent_run_id = _PAIR_PARENT_RUNS.get(pair_name)

    if parent_run_id:
        try:
            # Use existing parent run
            with mlflow.start_run(run_id=parent_run_id) as parent_run:
                logger.debug(f"Using existing parent run: {parent_run_id}")
                yield parent_run
                return
        except Exception as e:
            logger.error(f"Error using existing parent run {parent_run_id}: {str(e)}")
            # Remove the invalid parent run ID
            _PAIR_PARENT_RUNS.pop(pair_name, None)
            # Fall through to creating a new run

    # Create a new parent run if we get here
    try:
        with mlflow.start_run(run_name=run_name) as run:
            # Store this run as the parent run for this pair
            _PAIR_PARENT_RUNS[pair_name] = run.info.run_id
            logger.debug(f"Created new parent run: {run.info.run_id} for {pair_name}")
            yield run
    except Exception as e:
        logger.error(f"Error creating new run: {str(e)}")
        # Fallback to a new run with unique name
        with mlflow.start_run(run_name=f"{run_name}_retry") as run:
            _PAIR_PARENT_RUNS[pair_name] = run.info.run_id
            logger.debug(
                f"Created fallback parent run: {run.info.run_id} for {pair_name}"
            )
            yield run


def log_data_to_mlflow(
    pair_name: str, df: pd.DataFrame, log_params: bool = True
) -> None:
    """
    Log data and profile report to MLflow for a specific cryptocurrency pair

    Args:
        pair_name (str): Name of the cryptocurrency pair
        df (pandas.DataFrame): Data to log
        log_params (bool): Whether to log parameters
    """
    # Log basic data stats
    if log_params:
        mlflow.log_params(
            {
                "pair": pair_name,
                "data_rows": len(df),
                "data_columns": len(df.columns),
                "timestamp": datetime.now().isoformat(),
            }
        )

    # Log sample data directly
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        artifact_name = (
            f"{pair_name}_data_samples_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        df.head(100).to_csv(tmp.name, index=False)
        mlflow.log_artifact(tmp.name, artifact_name)
        os.unlink(tmp.name)  # Clean up the temporary file

        logger.info(f"Logged data samples for {pair_name} to MLflow")


def log_profile_report_to_mlflow(pair_name: str, df: pd.DataFrame) -> None:
    """Log profile report to MLflow

    Args:
        pair_name (str): Name of the cryptocurrency pair
        df (pandas.DataFrame): Data to log
    """
    profile = ydata_profiling.ProfileReport(
        df, title=f"Technical Indicators Profile - {pair_name}", explorative=True
    )

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
        artifact_name = f"{pair_name}_profile_reports_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        profile.to_file(tmp.name)
        mlflow.log_artifact(tmp.name, artifact_name)
        os.unlink(tmp.name)  # Clean up the temporary file

    logger.info(f"Logged profile report for {pair_name} to MLflow")


def log_to_mlflow(pair_name: str, data: Union[pd.DataFrame, Tuple]) -> str:
    """
    Log data and profile report to MLflow for a specific cryptocurrency pair.
    This function ensures that all logging happens within the same MLflow run.

    Args:
        pair_name (str): Name of the cryptocurrency pair
        data: Either a DataFrame or a tuple of (X, y, scaler) returned from prepare_time_series_data

    Returns:
        str: The active run ID
    """
    try:
        with active_run(pair_name) as run:
            run_id = run.info.run_id

            # Check if data is a DataFrame or a tuple from prepare_time_series_data
            if isinstance(data, pd.DataFrame):
                log_data_to_mlflow(pair_name, data)
                log_profile_report_to_mlflow(pair_name, data)
            elif isinstance(data, tuple) and len(data) >= 2:
                # Assuming data is (X, y, scaler) from prepare_time_series_data
                X, y = data[0], data[1]

                # Log X features
                log_data_to_mlflow(f"{pair_name}_features", X)

                # Log y target as a DataFrame
                y_df = pd.DataFrame(y)
                log_data_to_mlflow(f"{pair_name}_target", y_df)

                # Log combined data for profiling
                combined_df = X.copy()
                combined_df["target"] = y
                log_profile_report_to_mlflow(pair_name, combined_df)
            else:
                logger.warning(
                    f"Unsupported data type for MLflow logging: {type(data)}"
                )

        return run_id
    except Exception as e:
        logger.error(f"Error logging to MLflow: {str(e)}")
        # Return a placeholder if logging failed
        return f"logging_failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def log_models_to_mlflow(
    models_df: pd.DataFrame,
    pair_name: str,
    top_n_models: Optional[int] = None,
    top_models_list: Optional[List[str]] = None,
) -> None:
    """
    Log model comparison results from LazyRegressor to MLflow for a specific pair.

    This function logs model metrics in a comprehensive way, including:
    - Complete model metrics table as CSV
    - Best model information as parameters
    - Top N models performance metrics as parameters
    - Visualizations of model performance (coming soon)

    Args:
        models_df (pandas.DataFrame): DataFrame containing model metrics from LazyRegressor
        pair_name (str): Name of the cryptocurrency pair
        top_n_models (int, optional): Number of top models to log metrics for
        top_models_list (List[str], optional): List of top model names (if already selected)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if models_df is None or models_df.empty:
        logger.warning(f"No models to log for {pair_name}")
        return

    try:
        # Use the existing parent run for this pair to ensure consistent logging
        with active_run(pair_name) as run:
            # Log total number of models
            mlflow.log_param(f"{pair_name}_total_models", len(models_df))

            # Determine top models
            if top_models_list is None:
                if top_n_models is None:
                    top_n_models = min(
                        5, len(models_df)
                    )  # Default to top 5 or all if fewer

                top_models_list = models_df["Model"].tolist()[:top_n_models]

            # Log top models as a parameter
            mlflow.log_param(f"{pair_name}_top_models", ", ".join(top_models_list))

            # Log best model details as parameters
            if len(models_df) > 0:
                best_model = models_df.iloc[0]
                best_model_name = best_model["Model"]

                best_model_metrics = {
                    f"{pair_name}_best_model": best_model_name,
                }

                # Log key metrics for the best model
                for metric in ["R-Squared", "RMSE", "Time Taken"]:
                    if metric in best_model:
                        best_model_metrics[f"{pair_name}_best_model_{metric}"] = (
                            best_model[metric]
                        )

                mlflow.log_params(best_model_metrics)

            # Log detailed metrics for top N models
            for i, model_name in enumerate(top_models_list):
                model_row = models_df[models_df["Model"] == model_name]
                if not model_row.empty:
                    model_data = model_row.iloc[0]
                    for metric in ["R-Squared", "RMSE", "Time Taken"]:
                        if metric in model_data:
                            try:
                                mlflow.log_metric(
                                    f"{pair_name}_{model_name}_{metric}",
                                    float(model_data[metric]),
                                )
                            except Exception as e:
                                logger.warning(
                                    f"Failed to log metric {metric} for {model_name}: {str(e)}"
                                )

            # Log full model comparison as CSV artifact
            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
                models_df.to_csv(tmp.name, index=False)
                mlflow.log_artifact(
                    tmp.name,
                    f"model_metrics/{pair_name}_models_comparison_{timestamp}.csv",
                )
                os.unlink(tmp.name)

            # Log top N models as separate CSV for quick reference
            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
                top_models_df = models_df[models_df["Model"].isin(top_models_list)]
                top_models_df.to_csv(tmp.name, index=False)
                mlflow.log_artifact(
                    tmp.name,
                    f"model_metrics/{pair_name}_top_{len(top_models_list)}_models_{timestamp}.csv",
                )
                os.unlink(tmp.name)

            # Also log as MLflow table format for better UI rendering
            try:
                mlflow.log_table(
                    data=models_df,
                    artifact_file=f"model_metrics/{pair_name}_models_comparison_{timestamp}.json",
                )
            except Exception as e:
                logger.warning(f"Failed to log model table: {str(e)}")

            logger.success(
                f"Model comparison results logged for {pair_name} (Run ID: {run.info.run_id})"
            )
    except Exception as e:
        logger.error(f"Error logging models to MLflow: {str(e)}")


def get_active_run_id(pair_name: Optional[str] = None) -> Optional[str]:
    """
    Get the current active run ID for a particular pair.

    Args:
        pair_name (str, optional): If provided, get the parent run ID for this pair

    Returns:
        str: The active run ID or None if no run is active
    """
    try:
        # If pair_name is provided and we have a parent run for it, return that
        if pair_name is not None and pair_name in _PAIR_PARENT_RUNS:
            return _PAIR_PARENT_RUNS[pair_name]

        # Otherwise check for any active run
        run = mlflow.active_run()
        return run.info.run_id if run is not None else None
    except Exception as e:
        logger.error(f"Error getting active run ID: {str(e)}")
        return None


def reset_parent_runs():
    """
    Reset the parent runs dictionary. Useful for testing or
    when you want to start fresh with new runs.
    """
    _PAIR_PARENT_RUNS.clear()
