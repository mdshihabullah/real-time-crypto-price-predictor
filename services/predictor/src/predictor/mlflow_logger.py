"""
This module provides functionality to log data and profile reports to MLflow.

It includes functions to:
- Set up MLflow tracking
- Log data and profile reports for specific cryptocurrency pairs
"""

import contextlib
import os
import tempfile
from datetime import datetime
from typing import Generator, List, Optional, Tuple, Union

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


# Dictionary to keep track of pair-specific runs
_PAIR_RUNS = {}


@contextlib.contextmanager
def active_run(
    pair_name: str, run_name: Optional[str] = None, run_id: Optional[str] = None
) -> Generator[mlflow.ActiveRun, None, None]:
    """
    Get or create an MLflow run within the appropriate experiment for a cryptocurrency pair.

    This function will either:
    1. Use a specific run ID if provided
    2. Use an existing run for this pair if available
    3. Create a new run if needed

    Each pair will always have its own separate run to ensure metrics are properly isolated.

    Args:
        pair_name (str): Name of the cryptocurrency pair
        run_name (str, optional): Name of the run, defaults to pair_name_timestamp
        run_id (str, optional): Specific run ID to use, if provided

    Yields:
        mlflow.ActiveRun: The active MLflow run
    """
    # Get or create the experiment
    try:
        experiment_id = get_or_create_experiment(pair_name)
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

    # First, check if there's already an active run that's specifically for this pair
    current_run = mlflow.active_run()
    if current_run is not None:
        # Only use the current run if it's for this pair (check params)
        try:
            client = mlflow.tracking.MlflowClient()
            run_data = client.get_run(current_run.info.run_id)
            if run_data.data.params.get("pair") == pair_name:
                logger.debug(
                    f"Using current active run for {pair_name}: {current_run.info.run_id}"
                )
                yield current_run
                return
            else:
                # End the current run if it's for a different pair to avoid mixing metrics
                logger.debug(
                    f"Ending active run for different pair: {current_run.info.run_id}"
                )
                mlflow.end_run()
        except Exception as e:
            logger.error(f"Error checking current run: {str(e)}")
            mlflow.end_run()  # End the run to be safe

    # Option 1: Use a specific run_id if provided
    if run_id is not None:
        try:
            run = mlflow.start_run(run_id=run_id)
            logger.debug(f"Using provided run ID for {pair_name}: {run_id}")
            _PAIR_RUNS[pair_name] = run_id  # Update the dictionary
            yield run
            return
        except Exception as e:
            logger.error(f"Error using provided run ID {run_id}: {str(e)}")
            # Fall through to other options

    # Option 2: Use the existing run for this pair
    existing_run_id = _PAIR_RUNS.get(pair_name)
    if existing_run_id:
        try:
            run = mlflow.start_run(run_id=existing_run_id)
            logger.debug(f"Using existing run for {pair_name}: {existing_run_id}")
            yield run
            return
        except Exception as e:
            logger.error(f"Error using existing run {existing_run_id}: {str(e)}")
            # Remove the invalid run ID
            _PAIR_RUNS.pop(pair_name, None)
            # Fall through to creating a new run

    # Option 3: Create a new run
    try:
        run = mlflow.start_run(run_name=run_name)
        # Store this run for this pair
        _PAIR_RUNS[pair_name] = run.info.run_id
        logger.debug(f"Created new run for {pair_name}: {run.info.run_id}")

        # Log essential parameters
        try:
            mlflow.log_param("pair", pair_name)
            mlflow.log_param("creation_timestamp", datetime.now().isoformat())
        except Exception as param_error:
            logger.warning(f"Could not log initial parameters: {str(param_error)}")

        yield run
        return
    except Exception as e:
        logger.error(f"Error creating new run: {str(e)}")
        # One final attempt with a unique name
        try:
            fallback_name = (
                f"{run_name}_retry_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            run = mlflow.start_run(run_name=fallback_name)
            _PAIR_RUNS[pair_name] = run.info.run_id
            logger.debug(f"Created fallback run: {run.info.run_id} for {pair_name}")

            try:
                mlflow.log_param("pair", pair_name)
            except Exception:
                pass  # Just ignore errors at this point

            yield run
            return
        except Exception as final_e:
            logger.error(f"All attempts to create an MLflow run failed: {str(final_e)}")
            # Create a dummy run object to avoid breaking calling code
            yield type(
                "DummyRun",
                (),
                {"info": type("DummyInfo", (), {"run_id": "dummy_run_error"})},
            )
            return


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
        try:
            # Use metrics instead of parameters for things that might change
            mlflow.log_metric("data_rows", len(df))
            mlflow.log_metric("data_columns", len(df.columns))

            # Use a unique parameter name with timestamp to avoid conflicts
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            param_prefix = f"data_{timestamp}"

            # Log parameters that are safe to log once
            mlflow.log_param(f"{param_prefix}_pair", pair_name)
        except Exception as e:
            logger.warning(f"Could not log data parameters: {str(e)}")

    # Log sample data directly
    try:
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            artifact_name = f"{pair_name}_data_samples_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            df.head(100).to_csv(tmp.name, index=False)
            mlflow.log_artifact(tmp.name, artifact_name)
            os.unlink(tmp.name)  # Clean up the temporary file

            logger.info(f"Logged data samples for {pair_name} to MLflow")
    except Exception as e:
        logger.warning(f"Could not log data samples: {str(e)}")


def log_profile_report_to_mlflow(pair_name: str, df: pd.DataFrame) -> None:
    """Log profile report to MLflow

    Args:
        pair_name (str): Name of the cryptocurrency pair
        df (pandas.DataFrame): Data to log
    """
    try:
        profile = ydata_profiling.ProfileReport(
            df, title=f"Technical Indicators Profile - {pair_name}", explorative=True
        )

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            artifact_name = f"{pair_name}_profile_reports_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            profile.to_file(tmp.name)
            mlflow.log_artifact(tmp.name, artifact_name)
            os.unlink(tmp.name)  # Clean up the temporary file

        logger.info(f"Logged profile report for {pair_name} to MLflow")
    except Exception as e:
        logger.warning(f"Error creating profile report for {pair_name}: {str(e)}")
        import traceback

        logger.debug(f"Traceback: {traceback.format_exc()}")


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
    # Check if we already have a run for this pair
    pair_run_id = _PAIR_RUNS.get(pair_name)
    is_new_run = pair_run_id is None

    try:
        # Use the active_run context to either get existing run or create a new one
        with active_run(pair_name, run_id=pair_run_id) as run:
            # Save this run ID for future reference
            run_id = run.info.run_id
            _PAIR_RUNS[pair_name] = run_id

            # Only log workflow parameters if this is a new run to avoid conflicts
            if is_new_run:
                try:
                    # Create a unique workflow ID for this logging session
                    workflow_id = f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    mlflow.log_param(f"{workflow_id}_step", "initial_data_logging")
                except Exception as e:
                    logger.warning(f"Could not log workflow parameters: {str(e)}")

            # Check if data is a DataFrame or a tuple from prepare_time_series_data
            if isinstance(data, pd.DataFrame):
                log_data_to_mlflow(pair_name, data, log_params=is_new_run)
                try:
                    log_profile_report_to_mlflow(pair_name, data)
                except Exception as e:
                    logger.warning(
                        f"Error generating or logging profile report: {str(e)}"
                    )
            elif isinstance(data, tuple) and len(data) >= 2:
                # Assuming data is (X, y, scaler) from prepare_time_series_data
                X, y = data[0], data[1]

                # Log X features
                log_data_to_mlflow(f"{pair_name}_features", X, log_params=is_new_run)

                # Log y target as a DataFrame
                y_df = pd.DataFrame(y)
                log_data_to_mlflow(f"{pair_name}_target", y_df, log_params=is_new_run)

                # Log combined data for profiling
                try:
                    combined_df = X.copy()
                    combined_df["target"] = y
                    log_profile_report_to_mlflow(pair_name, combined_df)
                except Exception as e:
                    logger.warning(
                        f"Error generating or logging combined profile report: {str(e)}"
                    )
            else:
                logger.warning(
                    f"Unsupported data type for MLflow logging: {type(data)}"
                )

        logger.info(f"Logged data to MLflow run {run_id} for {pair_name}")
        return run_id
    except Exception as e:
        logger.error(f"Error logging to MLflow: {str(e)}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
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
                for metric in [
                    "mean_absolute_error_metric",
                    "R-Squared",
                    "RMSE",
                    "Time Taken",
                ]:
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
                    for metric in [
                        "mean_absolute_error_metric",
                        "R-Squared",
                        "RMSE",
                        "Time Taken",
                    ]:
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
        pair_name (str, optional): If provided, get the run ID for this pair

    Returns:
        str: The active run ID or None if no run is active
    """
    if pair_name is not None:
        # First check if we have a stored run ID for this pair
        if pair_name in _PAIR_RUNS:
            return _PAIR_RUNS.get(pair_name)

    # If no pair name is provided or no run exists for the pair,
    # try to get the current active run
    active_run = mlflow.active_run()
    if active_run:
        return active_run.info.run_id

    return None


def reset_pair_runs():
    """
    Reset the runs dictionary. Useful for testing or
    when you want to start fresh with new runs.

    This forces the system to create new runs for each pair
    instead of reusing existing runs from a previous session.
    """
    global _PAIR_RUNS
    if _PAIR_RUNS:
        logger.info(f"Resetting {len(_PAIR_RUNS)} pair runs")
        _PAIR_RUNS = {}
    else:
        logger.debug("No pair runs to reset")


# Keep the old function name for backward compatibility
def reset_parent_runs():
    """
    Alias for reset_pair_runs for backward compatibility.
    """
    return reset_pair_runs()
