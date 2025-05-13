"""Module for training and evaluating predictive models using LazyPredict."""

import os
from typing import Dict, List, Tuple, Any, Optional, Union

import numpy as np
import pandas as pd
from lazypredict.Supervised import LazyRegressor
from loguru import logger
from sklearn.metrics import mean_absolute_error

from predictor.mlflow_logger import log_models_to_mlflow, get_active_run_id


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
            logger.debug(f"Temporarily removed MLflow URI for LazyPredict: {mlflow_uri}")

        # Initialize LazyRegressor
        reg = LazyRegressor(
            ignore_warnings=self.ignore_warnings,
            custom_metric=self.mean_absolute_error_metric,
            verbose=True,
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

            # Train models
            logger.info(f"Starting model training for {pair_name} with LazyPredict")
            models, predictions = reg.fit(
                X_train_f32, X_test_f32, y_train_f32, y_test_f32
            )

            # Process results
            if models is not None:
                models.reset_index(inplace=True)
                logger.info(
                    f"Successfully trained {len(models)} models for {pair_name}"
                )

                # Get top N models
                top_models = models["Model"].tolist()[: self.top_n_models]
                logger.info(
                    f"Top {len(top_models)} models for {pair_name}: {top_models}"
                )

                # Restore MLflow URI before logging
                if mlflow_uri:
                    os.environ["MLFLOW_TRACKING_URI"] = mlflow_uri
                    logger.debug(f"Restored MLflow URI: {mlflow_uri}")
                
                # Log model metrics with the enhanced function
                try:
                    log_models_to_mlflow(
                        models_df=models,
                        pair_name=pair_name,
                        top_n_models=self.top_n_models,
                        top_models_list=top_models,
                    )
                except Exception as e:
                    logger.error(f"Error logging models to MLflow: {str(e)}")

                return models, top_models
            else:
                logger.warning(f"No models were successfully trained for {pair_name}")
                return None, []

        except Exception as e:
            logger.error(f"Error training models for {pair_name}: {str(e)}")
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
                # Check if we already have an active run for this pair
                active_run_id = get_active_run_id(pair)
                if active_run_id:
                    logger.info(f"Using existing MLflow run {active_run_id} for {pair}")
                
                models_df, top_models = self.train_models(
                    data["X_train"],
                    data["X_test"],
                    data["y_train"],
                    data["y_test"],
                    pair,
                )
                
                if models_df is not None and len(top_models) > 0:
                    top_n_models[pair] = top_models
                    logger.info(f"Successfully trained models for {pair}, top model: {top_models[0]}")
                else:
                    logger.warning(f"No models trained successfully for {pair}")
                    top_n_models[pair] = []
                    
            except Exception as e:
                logger.error(f"Failed to train models for {pair}: {str(e)}")
                top_n_models[pair] = []

        return top_n_models
