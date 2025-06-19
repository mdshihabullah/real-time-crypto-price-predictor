"""Module for training and evaluating predictive models using LazyPredict."""

import os
import traceback
from typing import Any, Dict, List, Optional, Tuple, Union

import mlflow
import numpy as np
import pandas as pd
from lazypredict.Supervised import LazyRegressor
from loguru import logger
from sklearn.metrics import mean_absolute_error

from predictor.mlflow_logger import active_run, get_active_run_id, log_models_to_mlflow


class ModelTrainer:
    """Class for training and evaluating predictive models using LazyPredict."""

    def __init__(self, top_n_models: int = 5, ignore_warnings: bool = True):
        """
        Initialize the ModelTrainer class.

        Args:
            top_n_models: Number of top models to return.
            ignore_warnings: Whether to ignore warnings during model training.
        """
        self.top_n_models = top_n_models
        self.ignore_warnings = ignore_warnings

    @staticmethod
    def mean_absolute_error_metric(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """
        Calculate mean absolute error metric.

        Args:
            y_true: True target values.
            y_pred: Predicted target values.

        Returns:
            Mean absolute error value.
        """
        return mean_absolute_error(y_true, y_pred)

    def train_models(
        self,
        X_train: pd.DataFrame,
        X_test: pd.DataFrame,
        y_train: Union[pd.Series, pd.DataFrame],
        y_test: Union[pd.Series, pd.DataFrame],
        pair_name: str,
    ) -> Tuple[Optional[pd.DataFrame], List[str]]:
        """
        Train multiple regression models using LazyPredict.

        Args:
            X_train: Training features.
            X_test: Testing features.
            y_train: Training target.
            y_test: Testing target.
            pair_name: Name of the trading pair being modeled.

        Returns:
            A tuple containing:
                - DataFrame with model performance metrics
                - List of top model names
        """
        logger.info(f"Training models for {pair_name}")

        # Save MLflow URI since LazyPredict conflicts with MLflow
        mlflow_uri = os.environ.get("MLFLOW_TRACKING_URI")
        if mlflow_uri:
            # Save the URI and remove it temporarily
            del os.environ["MLFLOW_TRACKING_URI"]
            logger.debug(
                f"Temporarily removed MLflow URI for LazyPredict: {mlflow_uri}"
            )

        # Initialize LazyRegressor
        reg = LazyRegressor(
            ignore_warnings=self.ignore_warnings,
            custom_metric=self.mean_absolute_error_metric,
            verbose=True,
            predictions=False,
        )

        try:
            # Ensure data types are float32 for compatibility
            X_train_f32 = X_train.astype(np.float32)
            X_test_f32 = X_test.astype(np.float32)

            # Convert target data to proper format
            y_train_f32 = y_train.astype(np.float32)
            if isinstance(y_train, pd.DataFrame) and y_train.shape[1] == 1:
                y_train_f32 = y_train_f32.iloc[:, 0]

            y_test_f32 = y_test.astype(np.float32)
            if isinstance(y_test, pd.DataFrame) and y_test.shape[1] == 1:
                y_test_f32 = y_test_f32.iloc[:, 0]

            # Log data shapes and types
            logger.info(
                f"Training data shapes - X_train: {X_train_f32.shape}, y_train: {y_train_f32.shape}"
            )
            logger.info(
                f"Testing data shapes - X_test: {X_test_f32.shape}, y_test: {y_test_f32.shape}"
            )

            # Train models
            logger.info(f"Starting model training for {pair_name} with LazyPredict")
            models, _ = reg.fit(X_train_f32, X_test_f32, y_train_f32, y_test_f32)

            # Process results
            if models is not None:
                models.reset_index(inplace=True)
                # Sort models by MAE (ascending since lower MAE is better)
                models = models.sort_values(
                    by="mean_absolute_error_metric", ascending=True
                ).reset_index(drop=True)

                logger.info(
                    f"Successfully trained {len(models)} models for {pair_name}"
                )

                # Get top N models
                top_models = models["Model"].tolist()[: self.top_n_models]

                # Log detailed performance metrics for top models
                logger.info(f"Top {self.top_n_models} models for {pair_name}:")
                for i, (model_name, mae) in enumerate(
                    zip(
                        top_models,
                        models["mean_absolute_error_metric"].head(self.top_n_models),
                        strict=True,
                    )
                ):
                    logger.info(f"{i + 1}. {model_name}: MAE = {mae:.6f}")

                # Restore MLflow URI before logging
                if mlflow_uri:
                    os.environ["MLFLOW_TRACKING_URI"] = mlflow_uri
                    logger.debug(f"Restored MLflow URI: {mlflow_uri}")

                # Log model metrics (LazyPredict performance only - no trained models yet)
                try:
                    log_models_to_mlflow(
                        models_df=models,
                        pair_name=pair_name,
                        top_n_models=self.top_n_models,
                        top_models_list=top_models,
                        # No trained_models - these will be created during hyperparameter tuning
                    )
                except Exception as e:
                    logger.error(f"Error logging models to MLflow: {str(e)}")
                    # Continue even if MLflow logging fails

                return models, top_models
            else:
                logger.warning(f"No models were successfully trained for {pair_name}")
                return None, []

        except Exception as e:
            logger.error(f"Error training models for {pair_name}: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None, []
        finally:
            # Restore MLflow URI if it wasn't restored yet
            if mlflow_uri and "MLFLOW_TRACKING_URI" not in os.environ:
                os.environ["MLFLOW_TRACKING_URI"] = mlflow_uri
                logger.debug(f"Restored MLflow URI in finally block: {mlflow_uri}")

    def train_for_all_pairs(
        self, train_val_test_data: Dict[str, Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """
        Train models for all cryptocurrency pairs.

        Args:
            train_val_test_data: Dictionary containing training, validation, and testing data for each pair.

        Returns:
            Dictionary mapping each pair to a list of its top performing models.
        """
        top_n_models = {}

        for pair, data in train_val_test_data.items():
            try:
                # Use the active_run context manager to ensure consistent runs
                # Check if we already have a run for this pair
                existing_run_id = get_active_run_id(pair)
                is_new_run = existing_run_id is None

                with active_run(pair) as run:
                    logger.info(
                        f"Training models for {pair} within MLflow run {run.info.run_id}"
                    )

                    # Only log step parameters for new runs to avoid conflicts
                    if is_new_run:
                        try:
                            mlflow.log_param("step", "model_training")
                        except Exception as e:
                            logger.warning(f"Could not log step parameter: {str(e)}")

                    models_df, top_models = self.train_models(
                        data["X_train"],
                        data["X_test"],
                        data["y_train"],
                        data["y_test"],
                        pair,
                    )

                    if models_df is not None and len(top_models) > 0:
                        top_n_models[pair] = top_models
                        logger.info(
                            f"Successfully trained models for {pair}, top model: {top_models[0]}"
                        )

                        # Log metrics (metrics can be updated)
                        try:
                            mlflow.log_metric("total_models_trained", len(models_df))
                            mlflow.log_metric("top_models_count", len(top_models))
                        except Exception as e:
                            logger.warning(f"Could not log metrics: {str(e)}")
                    else:
                        logger.warning(f"No models trained successfully for {pair}")
                        top_n_models[pair] = []
                        # Do not log parameters that might conflict

            except Exception as e:
                logger.error(f"Failed to train models for {pair}: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                top_n_models[pair] = []

        return top_n_models
