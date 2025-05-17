"""
Module for hyperparameter tuning of machine learning models using Optuna and MLflow.

This module provides functionality to:
- Tune hyperparameters for sklearn regression models using Optuna
- Register the best models in MLflow model registry
- Track all tuning experiments with metrics and visualizations
"""

import importlib
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Type

import mlflow
import numpy as np
import optuna
import pandas as pd
from loguru import logger
from optuna.visualization import (
    plot_optimization_history,
    plot_parallel_coordinate,
    plot_param_importances,
    plot_slice,
)
from sklearn.base import BaseEstimator
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import cross_val_score


class ModelTuner:
    """
    Class for tuning hyperparameters of machine learning models using Optuna.

    This class takes the top-performing models identified by the ModelTrainer
    and performs hyperparameter optimization to further improve their performance.
    Results are logged to MLflow for tracking.
    """

    def __init__(
        self,
        n_trials: int = 100,
        timeout: Optional[int] = None,
        cv_folds: int = 5,
        random_state: int = 42,
    ):
        """
        Initialize the ModelTuner.

        Args:
            n_trials: Maximum number of trials for Optuna to perform.
            timeout: Maximum time in seconds for optimization (None = no limit).
            cv_folds: Number of cross-validation folds.
            random_state: Random seed for reproducibility.
        """
        self.n_trials = n_trials
        self.timeout = timeout
        self.cv_folds = cv_folds
        self.random_state = random_state

    def _import_model_class(self, model_name: str) -> Optional[Type[BaseEstimator]]:
        """
        Dynamically import a regressor class by name from common ML libraries.

        Args:
            model_name: Name of the regressor class.

        Returns:
            The regressor class if found, None otherwise.
        """
        # Define common ML library modules to try
        model_modules = [
            "sklearn.ensemble",
            "sklearn.linear_model",
            "sklearn.tree",
            "sklearn.svm",
            "sklearn.neighbors",
            "xgboost",
            "lightgbm",
            "catboost",
        ]

        # First try to import from each module
        for module_name in model_modules:
            try:
                module = importlib.import_module(module_name)
                if hasattr(module, model_name):
                    return getattr(module, model_name)
            except (ImportError, AttributeError):
                continue

        # If not found in common modules, try to guess from model name
        if "Regressor" in model_name or "Regression" in model_name:
            # Try to infer the module from the model name
            possible_modules = []

            if (
                "RandomForest" in model_name
                or "GradientBoosting" in model_name
                or "AdaBoost" in model_name
                or "ExtraTrees" in model_name
            ):
                possible_modules.append("sklearn.ensemble")
            elif (
                "Linear" in model_name
                or "Ridge" in model_name
                or "Lasso" in model_name
                or "ElasticNet" in model_name
            ):
                possible_modules.append("sklearn.linear_model")
            elif "Tree" in model_name:
                possible_modules.append("sklearn.tree")
            elif "SV" in model_name:
                possible_modules.append("sklearn.svm")
            elif "KNeighbors" in model_name:
                possible_modules.append("sklearn.neighbors")
            elif "XGB" in model_name:
                possible_modules.append("xgboost")
            elif "LGBM" in model_name:
                possible_modules.append("lightgbm")
            elif "CatBoost" in model_name:
                possible_modules.append("catboost")

            for module_name in possible_modules:
                try:
                    module = importlib.import_module(module_name)
                    if hasattr(module, model_name):
                        return getattr(module, model_name)
                except (ImportError, AttributeError):
                    continue

        logger.warning(f"Could not import model class: {model_name}")
        return None

    def _define_search_space(
        self, trial: optuna.Trial, model_name: str, model_class=None
    ) -> Dict[str, Any]:
        """
        Define the search space for a specific model type.

        Args:
            trial: Optuna trial object.
            model_name: Name of the model class.
            model_class: Optional model class for parameter inference.

        Returns:
            Dictionary of hyperparameters to try.
        """
        params = {}

        # Tree-based ensemble models
        if model_name == "RandomForestRegressor":
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 50, 500),
                "max_depth": trial.suggest_int("max_depth", 3, 30),
                "min_samples_split": trial.suggest_int("min_samples_split", 2, 20),
                "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 10),
                "max_features": trial.suggest_categorical(
                    "max_features", ["sqrt", "log2", None]
                ),
                "bootstrap": trial.suggest_categorical("bootstrap", [True, False]),
                "random_state": self.random_state,
            }

        elif model_name == "GradientBoostingRegressor":
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 50, 500),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3),
                "max_depth": trial.suggest_int("max_depth", 3, 10),
                "min_samples_split": trial.suggest_int("min_samples_split", 2, 20),
                "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 10),
                "subsample": trial.suggest_float("subsample", 0.7, 1.0),
                "max_features": trial.suggest_categorical(
                    "max_features", ["sqrt", "log2", None]
                ),
                "random_state": self.random_state,
            }

        elif model_name == "AdaBoostRegressor":
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 50, 500),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 1.0),
                "loss": trial.suggest_categorical(
                    "loss", ["linear", "square", "exponential"]
                ),
                "random_state": self.random_state,
            }

        elif model_name == "ExtraTreesRegressor":
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 50, 500),
                "max_depth": trial.suggest_int("max_depth", 3, 30),
                "min_samples_split": trial.suggest_int("min_samples_split", 2, 20),
                "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 10),
                "max_features": trial.suggest_categorical(
                    "max_features", ["sqrt", "log2", None]
                ),
                "bootstrap": trial.suggest_categorical("bootstrap", [True, False]),
                "random_state": self.random_state,
            }

        # Linear models
        elif model_name == "LinearRegression":
            params = {
                "fit_intercept": trial.suggest_categorical(
                    "fit_intercept", [True, False]
                ),
                "positive": trial.suggest_categorical("positive", [True, False]),
            }

        elif model_name in ["Ridge", "RidgeRegressor"]:
            params = {
                "alpha": trial.suggest_float("alpha", 0.01, 10.0, log=True),
                "fit_intercept": trial.suggest_categorical(
                    "fit_intercept", [True, False]
                ),
                "solver": trial.suggest_categorical(
                    "solver",
                    ["auto", "svd", "cholesky", "lsqr", "sparse_cg", "sag", "saga"],
                ),
                "random_state": self.random_state,
            }

        elif model_name in ["Lasso", "LassoRegressor"]:
            params = {
                "alpha": trial.suggest_float("alpha", 0.01, 10.0, log=True),
                "fit_intercept": trial.suggest_categorical(
                    "fit_intercept", [True, False]
                ),
                "random_state": self.random_state,
            }

        elif model_name == "ElasticNet":
            params = {
                "alpha": trial.suggest_float("alpha", 0.01, 10.0, log=True),
                "l1_ratio": trial.suggest_float("l1_ratio", 0.1, 0.9),
                "fit_intercept": trial.suggest_categorical(
                    "fit_intercept", [True, False]
                ),
                "random_state": self.random_state,
            }

        # SVM-based models
        elif model_name == "SVR":
            params = {
                "C": trial.suggest_float("C", 0.1, 100.0, log=True),
                "epsilon": trial.suggest_float("epsilon", 0.01, 1.0),
                "kernel": trial.suggest_categorical(
                    "kernel", ["linear", "rbf", "poly", "sigmoid"]
                ),
                "gamma": trial.suggest_categorical("gamma", ["scale", "auto"]),
                "degree": trial.suggest_int("degree", 2, 5)
                if trial.suggest_categorical("kernel", ["poly"])
                else 3,
            }

        # Decision Tree models
        elif model_name == "DecisionTreeRegressor":
            params = {
                "max_depth": trial.suggest_int("max_depth", 3, 30),
                "min_samples_split": trial.suggest_int("min_samples_split", 2, 20),
                "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 10),
                "max_features": trial.suggest_categorical(
                    "max_features", ["sqrt", "log2", None]
                ),
                "random_state": self.random_state,
            }

        # XGBoost
        elif model_name == "XGBRegressor":
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 50, 500),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3),
                "max_depth": trial.suggest_int("max_depth", 3, 12),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
                "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
                "gamma": trial.suggest_float("gamma", 0, 5),
                "reg_alpha": trial.suggest_float("reg_alpha", 0, 5),
                "reg_lambda": trial.suggest_float("reg_lambda", 0, 5),
                "random_state": self.random_state,
            }

        # LightGBM
        elif model_name == "LGBMRegressor":
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 50, 500),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3),
                "num_leaves": trial.suggest_int("num_leaves", 20, 100),
                "max_depth": trial.suggest_int("max_depth", 3, 12),
                "min_child_samples": trial.suggest_int("min_child_samples", 5, 100),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
                "reg_alpha": trial.suggest_float("reg_alpha", 0, 5),
                "reg_lambda": trial.suggest_float("reg_lambda", 0, 5),
                "random_state": self.random_state,
            }

        # CatBoost
        elif model_name == "CatBoostRegressor":
            params = {
                "iterations": trial.suggest_int("iterations", 50, 500),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3),
                "depth": trial.suggest_int("depth", 4, 10),
                "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1, 10),
                "random_strength": trial.suggest_float("random_strength", 0.1, 10),
                "bagging_temperature": trial.suggest_float(
                    "bagging_temperature", 0, 10
                ),
                "border_count": trial.suggest_int("border_count", 32, 255),
                "random_seed": self.random_state,
            }

        # K-Neighbors
        elif model_name == "KNeighborsRegressor":
            params = {
                "n_neighbors": trial.suggest_int("n_neighbors", 3, 50),
                "weights": trial.suggest_categorical(
                    "weights", ["uniform", "distance"]
                ),
                "algorithm": trial.suggest_categorical(
                    "algorithm", ["auto", "ball_tree", "kd_tree", "brute"]
                ),
                "p": trial.suggest_int("p", 1, 2),  # 1 = Manhattan, 2 = Euclidean
            }

        # Robust regression models
        elif model_name == "HuberRegressor":
            params = {
                "epsilon": trial.suggest_float(
                    "epsilon", 1.1, 2.0
                ),  # Values typically between 1.1 and 2.0
                "alpha": trial.suggest_float("alpha", 0.0001, 1.0, log=True),
                "fit_intercept": trial.suggest_categorical(
                    "fit_intercept", [True, False]
                ),
                "max_iter": trial.suggest_int("max_iter", 100, 1000),
            }

        elif model_name == "RANSACRegressor":
            params = {
                "min_samples": trial.suggest_float("min_samples", 0.1, 0.9),
                "max_trials": trial.suggest_int("max_trials", 50, 500),
                "max_skips": trial.suggest_int("max_skips", 50, 500),
                "random_state": self.random_state,
            }

        elif model_name == "TheilSenRegressor":
            params = {
                "max_subpopulation": trial.suggest_int(
                    "max_subpopulation", 1000, 10000
                ),
                "n_subsamples": trial.suggest_int(
                    "n_subsamples", None, None
                ),  # Default is None, using appropriate value based on sample size
                "max_iter": trial.suggest_int("max_iter", 100, 1000),
                "tol": trial.suggest_float("tol", 1e-6, 1e-3, log=True),
                "random_state": self.random_state,
            }

        # Handle other scikit-learn regressors with minimal hyperparameters
        elif hasattr(trial.study, "_storage") and model_class is not None:
            # Try to infer parameters from model's init signature
            import inspect

            try:
                sig = inspect.signature(model_class.__init__)
                for param_name, param in sig.parameters.items():
                    if param_name not in ["self", "args", "kwargs", "__class__"]:
                        # Add common parameters based on name
                        if param_name == "random_state" and param.default is not None:
                            params["random_state"] = self.random_state
                        elif (
                            param_name == "fit_intercept" and param.default is not None
                        ):
                            params["fit_intercept"] = trial.suggest_categorical(
                                "fit_intercept", [True, False]
                            )
                        elif param_name == "max_iter" and param.default is not None:
                            params["max_iter"] = trial.suggest_int(
                                "max_iter", 100, 1000
                            )
            except Exception as e:
                logger.warning(f"Error inferring parameters for {model_name}: {e}")

        return params

    def _create_objective_function(
        self,
        model_class: Type[BaseEstimator],
        model_name: str,
        X_train: pd.DataFrame,
        y_train: pd.Series,
    ) -> callable:
        """
        Create objective function for Optuna optimization.

        Args:
            model_class: The model class to optimize.
            model_name: Name of the model.
            X_train: Training features.
            y_train: Training target.

        Returns:
            Objective function for Optuna.
        """

        def objective(trial):
            # Get hyperparameters based on model type
            params = self._define_search_space(trial, model_name, model_class)

            # Handle empty params case
            if not params:
                logger.warning(
                    f"No search space defined for {model_name}, using default hyperparameters"
                )
                model = model_class()
            else:
                # Instantiate the model with parameters
                model = model_class(**params)

            # Perform cross-validation to get mean MAE
            mae_scores = cross_val_score(
                model,
                X_train,
                y_train,
                scoring="neg_mean_absolute_error",
                cv=self.cv_folds,
                n_jobs=-1,
            )

            # Return negative MAE (Optuna minimizes by default, but we want to maximize negative MAE)
            mean_mae = -1.0 * np.mean(mae_scores)

            return mean_mae

        return objective

    def _log_plotly_figure(self, figure, artifact_path):
        """
        Log a plotly figure to MLflow without saving to disk.

        Args:
            figure: Plotly figure to log
            artifact_path: Path within MLflow where the artifact should be saved
        """
        try:
            # Convert the figure to HTML and save to a BytesIO buffer
            import tempfile
            import os

            # Create a temporary file
            with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
                # Write the figure to the temp file
                figure.write_html(tmp.name)

                # Log the file to MLflow
                mlflow.log_artifact(tmp.name, artifact_path)

                # Clean up the temporary file
                tmp.close()
                os.unlink(tmp.name)

            logger.debug(f"Successfully logged visualization to {artifact_path}")
        except Exception as e:
            logger.warning(f"Error logging plotly figure: {str(e)}")
            import traceback

            logger.debug(f"Traceback: {traceback.format_exc()}")

    def tune_model(
        self,
        model_name: str,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        pair_name: str,
        parent_run_id: Optional[str] = None,
    ) -> Tuple[BaseEstimator, Dict[str, Any], float]:
        """
        Tune hyperparameters for a specific model using Optuna.

        Args:
            model_name: Name of the model class to tune.
            X_train: Training features.
            y_train: Training target.
            X_test: Test features.
            y_test: Test target.
            pair_name: Name of the cryptocurrency pair.
            parent_run_id: Optional parent run ID for proper nesting.

        Returns:
            Tuple containing:
                - Fitted model with best hyperparameters
                - Dictionary of best hyperparameters
                - Best score achieved (negative MAE)
        """
        logger.info(f"Tuning hyperparameters for {model_name} for {pair_name}")

        # Dynamically import the model class
        model_class = self._import_model_class(model_name)
        if model_class is None:
            logger.error(f"Could not import model class: {model_name}")
            return None, {}, float("inf")

        # Generate a unique study name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        study_name = f"{pair_name}_{model_name}_{timestamp}"

        try:
            # Start a nested run for this model's hyperparameter tuning
            with mlflow.start_run(
                run_name=f"{model_name}_tuning", nested=True
            ) as model_run:
                # Define the objective function
                objective = self._create_objective_function(
                    model_class, model_name, X_train, y_train
                )

                # Create the study
                study = optuna.create_study(
                    study_name=study_name,
                    direction="minimize",  # Minimize MAE
                    sampler=optuna.samplers.TPESampler(seed=self.random_state),
                )

                # Log study parameters
                mlflow.log_param("study_name", study_name)
                mlflow.log_param("model_name", model_name)

                # Optimize hyperparameters
                study.optimize(objective, n_trials=self.n_trials, timeout=self.timeout)

                # Get best hyperparameters
                best_params = study.best_params
                best_value = study.best_value

                # Train the final model with best hyperparameters
                best_model = model_class(**best_params)
                best_model.fit(X_train, y_train)

                # Evaluate model on test set
                y_pred = best_model.predict(X_test)
                test_mae = mean_absolute_error(y_test, y_pred)

                # Log best parameters and metrics - use simpler names here
                # Format parameters for logging (flatten nested objects if any)
                formatted_params = {
                    f"best_{key}": str(value) for key, value in best_params.items()
                }

                # Log key metrics
                metrics = {
                    "best_mae": test_mae,
                    "best_cv_mae": best_value,
                    "n_trials_completed": study.trials_dataframe().shape[0],
                }

                # Log parameters and metrics to MLflow
                mlflow.log_params(formatted_params)
                for metric_name, metric_value in metrics.items():
                    mlflow.log_metric(metric_name, metric_value)

                # Log hyperparameter tuning results as a CSV for analysis
                try:
                    import tempfile
                    import os

                    # Get the trials dataframe
                    trials_df = study.trials_dataframe()

                    if not trials_df.empty:
                        # Save trials to CSV
                        with tempfile.NamedTemporaryFile(
                            suffix=".csv", delete=False
                        ) as tmp:
                            trials_df.to_csv(tmp.name, index=False)
                            # Log the CSV file
                            mlflow.log_artifact(
                                tmp.name, f"optuna_results/{model_name}_trials.csv"
                            )
                            os.unlink(tmp.name)

                        logger.info(f"Logged {len(trials_df)} trials for {model_name}")
                except Exception as e:
                    logger.warning(f"Could not log trials data: {str(e)}")

                # Create and log Optuna visualization plots
                try:
                    # Only attempt to create visualizations if we have enough trials
                    if len(study.trials) >= 2:
                        # Optimization history plot
                        try:
                            history_fig = plot_optimization_history(study)
                            history_fig.update_layout(
                                title=f"Optimization History - {model_name}"
                            )
                            self._log_plotly_figure(
                                history_fig,
                                f"optuna_plots/{model_name}/optimization_history",
                            )
                        except Exception as e:
                            logger.warning(
                                f"Error creating optimization history plot: {str(e)}"
                            )

                        # Parameter importance plot (if we have parameters)
                        if best_params and len(best_params) >= 1:
                            try:
                                # Check if we have variance in the parameters
                                trials_df = study.trials_dataframe()
                                has_variance = False

                                for param in best_params.keys():
                                    param_col = f"params_{param}"
                                    if param_col in trials_df.columns:
                                        # Check if this parameter has any variance
                                        param_values = trials_df[param_col].astype(str)
                                        if len(param_values.unique()) > 1:
                                            has_variance = True
                                            break

                                if has_variance:
                                    importances_fig = plot_param_importances(study)
                                    importances_fig.update_layout(
                                        title=f"Parameter Importances - {model_name}"
                                    )
                                    self._log_plotly_figure(
                                        importances_fig,
                                        f"optuna_plots/{model_name}/param_importances",
                                    )
                                else:
                                    logger.warning(
                                        f"Not enough parameter variance to create importance plot for {model_name}"
                                    )
                            except Exception as e:
                                logger.warning(
                                    f"Error creating parameter importance plot: {str(e)}"
                                )
                                import traceback

                                logger.debug(f"Traceback: {traceback.format_exc()}")

                            # Parallel coordinate plot (if we have multiple parameters with variance)
                            if len(best_params) >= 2 and has_variance:
                                try:
                                    parallel_fig = plot_parallel_coordinate(study)
                                    parallel_fig.update_layout(
                                        title=f"Parallel Coordinate - {model_name}"
                                    )
                                    self._log_plotly_figure(
                                        parallel_fig,
                                        f"optuna_plots/{model_name}/parallel_coordinate",
                                    )
                                except Exception as e:
                                    logger.warning(
                                        f"Error creating parallel coordinate plot: {str(e)}"
                                    )

                            # Slice plot for the first parameter (if it has variance)
                            try:
                                slice_param = list(best_params.keys())[0]
                                param_col = f"params_{slice_param}"

                                if (
                                    param_col in trials_df.columns
                                    and len(trials_df[param_col].unique()) > 1
                                ):
                                    slice_fig = plot_slice(study, params=[slice_param])
                                    slice_fig.update_layout(
                                        title=f"Slice Plot - {model_name} - {slice_param}"
                                    )
                                    self._log_plotly_figure(
                                        slice_fig,
                                        f"optuna_plots/{model_name}/slice_plot",
                                    )
                            except Exception as e:
                                logger.warning(f"Error creating slice plot: {str(e)}")
                    else:
                        logger.warning(
                            f"Not enough trials ({len(study.trials)}) to create visualization plots for {model_name}"
                        )
                except Exception as e:
                    logger.warning(
                        f"Error creating or logging visualization plots: {e}"
                    )
                    import traceback

                    logger.debug(f"Traceback: {traceback.format_exc()}")

                # Register model in MLflow model registry for this specific model
                try:
                    # Get a sample of the input data for model signature
                    from mlflow.models.signature import infer_signature

                    # Create input example - just use a small sample of training data
                    input_example = X_train.iloc[:5].copy()

                    # Infer model signature from the data
                    prediction_sample = best_model.predict(input_example)
                    signature = infer_signature(input_example, prediction_sample)

                    # Log the model with a distinct path
                    model_path = f"models/{pair_name}/{model_name}"
                    mlflow.sklearn.log_model(
                        best_model,
                        model_path,
                        signature=signature,
                        input_example=input_example,
                    )
                    logger.info(f"Logged model {model_name} for {pair_name}")
                except Exception as e:
                    logger.warning(f"Error logging model in MLflow: {e}")
                    import traceback

                    logger.debug(f"Traceback: {traceback.format_exc()}")

                logger.info(
                    f"Completed hyperparameter tuning for {model_name} for {pair_name}"
                )
                logger.info(f"Best parameters: {best_params}")
                logger.info(f"Best MAE: {test_mae}")

                # Log a summary of best hyperparameters for easy reference
                try:
                    import json

                    summary = {
                        "model_name": model_name,
                        "best_params": best_params,
                        "best_mae": test_mae,
                        "best_cv_mae": best_value,
                        "trials_count": len(study.trials),
                        "timestamp": datetime.now().isoformat(),
                    }

                    with tempfile.NamedTemporaryFile(
                        mode="w", suffix=".json", delete=False
                    ) as tmp:
                        json.dump(summary, tmp, indent=2)
                        tmp.flush()
                        # Log the JSON file
                        mlflow.log_artifact(
                            tmp.name, f"optuna_results/{model_name}_summary.json"
                        )
                        os.unlink(tmp.name)
                except Exception as e:
                    logger.warning(f"Could not log summary: {str(e)}")

                return best_model, best_params, test_mae

        except Exception as e:
            logger.error(f"Error in hyperparameter tuning for {model_name}: {str(e)}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            return None, {}, float("inf")

    def tune_top_models(
        self,
        top_models: Dict[str, List[str]],
        train_val_test_data: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Tune the top-performing models for each cryptocurrency pair.

        Args:
            top_models: Dictionary mapping each pair to a list of its top performing models.
            train_val_test_data: Dictionary containing training, validation, and testing data for each pair.

        Returns:
            Dictionary mapping each pair to its best tuned model information.
        """
        best_tuned_models = {}

        for pair, models in top_models.items():
            if not models:
                logger.warning(f"No models to tune for {pair}")
                continue

            pair_data = train_val_test_data.get(pair)
            if not pair_data:
                logger.warning(f"No data available for {pair}")
                continue

            # Get data for this pair
            X_train = pair_data["X_train"]
            y_train = pair_data["y_train"]
            X_test = pair_data["X_test"]
            y_test = pair_data["y_test"]

            # Track best model for this pair
            best_model_info = {
                "model_name": None,
                "model": None,
                "params": None,
                "mae": float("inf"),
            }

            # Log that we're starting hyperparameter tuning for this pair
            logger.info(
                f"Starting hyperparameter tuning for {pair} with {len(models)} top models"
            )

            # Get the active run ID for this pair - this should be the parent run we want to use
            from predictor.mlflow_logger import get_active_run_id, active_run

            parent_run_id = get_active_run_id(pair)

            if not parent_run_id:
                logger.warning(f"No active run ID found for {pair}, will create one.")

            # Use the existing parent run for this pair
            with active_run(pair, run_id=parent_run_id) as parent_run:
                # Log tuning metrics (metrics can be updated unlike parameters)
                mlflow.log_metric("models_to_tune_count", len(models))
                mlflow.log_metric("tuning_trials", self.n_trials)

                # Create a summary of what we're tuning
                import json
                import tempfile
                import os

                try:
                    tuning_summary = {
                        "pair": pair,
                        "models_to_tune": models,
                        "trials": self.n_trials,
                        "cv_folds": self.cv_folds,
                        "timeout": self.timeout,
                        "random_state": self.random_state,
                        "timestamp": datetime.now().isoformat(),
                    }

                    with tempfile.NamedTemporaryFile(
                        mode="w", suffix=".json", delete=False
                    ) as tmp:
                        json.dump(tuning_summary, tmp, indent=2)
                        tmp.flush()
                        # Log the JSON file in the main tuning folder for easy reference
                        mlflow.log_artifact(tmp.name, f"tuning_config.json")
                        os.unlink(tmp.name)
                except Exception as e:
                    logger.warning(f"Could not log tuning summary: {str(e)}")

                # Tune each model using nested runs
                for model_name in models:
                    try:
                        # Pass the parent run ID to ensure proper nesting
                        tuned_model, best_params, test_mae = self.tune_model(
                            model_name,
                            X_train,
                            y_train,
                            X_test,
                            y_test,
                            pair,
                            parent_run_id=parent_run.info.run_id,
                        )

                        # Update best model if this one is better
                        if (
                            tuned_model is not None
                            and test_mae < best_model_info["mae"]
                        ):
                            best_model_info = {
                                "model_name": model_name,
                                "model": tuned_model,
                                "params": best_params,
                                "mae": test_mae,
                            }

                    except Exception as e:
                        logger.error(f"Error tuning {model_name} for {pair}: {str(e)}")
                        import traceback

                        logger.debug(f"Traceback: {traceback.format_exc()}")

                # Log the best model for this pair in the parent run
                if best_model_info["model"] is not None:
                    # Use metrics instead of parameters to avoid conflicts
                    mlflow.log_metric("best_tuned_model_mae", best_model_info["mae"])

                    # Create a comprehensive best model summary as JSON
                    try:
                        best_summary = {
                            "pair": pair,
                            "best_model": best_model_info["model_name"],
                            "mae": best_model_info["mae"],
                            "best_params": best_model_info["params"],
                            "timestamp": datetime.now().isoformat(),
                        }

                        with tempfile.NamedTemporaryFile(
                            mode="w", suffix=".json", delete=False
                        ) as tmp:
                            json.dump(best_summary, tmp, indent=2)
                            tmp.flush()
                            # Log the JSON file in the main folder for easy reference
                            mlflow.log_artifact(tmp.name, f"best_model_summary.json")
                            os.unlink(tmp.name)
                    except Exception as e:
                        logger.warning(f"Could not log best model summary: {str(e)}")

                    # Register the best model with a special tag to indicate it's the best for this pair
                    try:
                        # Get a sample of the input data for model signature
                        from mlflow.models.signature import infer_signature

                        # Create input example
                        input_example = X_train.iloc[:5].copy()

                        # Infer model signature from the data
                        prediction_sample = best_model_info["model"].predict(
                            input_example
                        )
                        signature = infer_signature(input_example, prediction_sample)

                        model_path = f"models/{pair}/best_model"
                        mlflow.sklearn.log_model(
                            best_model_info["model"],
                            model_path,
                            registered_model_name=f"{pair}_best_model",
                            signature=signature,
                            input_example=input_example,
                        )
                        logger.info(
                            f"Registered best model {best_model_info['model_name']} for {pair}"
                        )
                    except Exception as e:
                        logger.warning(f"Error registering best model: {str(e)}")
                        import traceback

                        logger.debug(f"Traceback: {traceback.format_exc()}")

                    # Log tuning completion status as a metric
                    mlflow.log_metric("tuning_completed", 1)

            # Store best model for this pair
            best_tuned_models[pair] = best_model_info

            if best_model_info["model"] is not None:
                logger.info(
                    f"Best tuned model for {pair}: {best_model_info['model_name']} with MAE: {best_model_info['mae']}"
                )
            else:
                logger.warning(f"No successful model tuning for {pair}")

        return best_tuned_models
