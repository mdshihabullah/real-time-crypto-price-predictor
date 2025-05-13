"""Main script for crypto price prediction workflow"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import mlflow
import pandas as pd
from loguru import logger

from predictor.config import config
from predictor.data_fetcher import fetch_technical_indicators_data, fetch_available_pairs
from predictor.data_validator import validate_timeseries_data
from predictor.data_profiler import profile_dataframe, ensure_reports_dir, REPORTS_DIR
from predictor.data_preprocessor import (
    handle_missing_values,
    create_target_variable,
    split_timeseries_data,
    create_feature_matrix,
    normalize_features
)
from predictor.model_trainer import (
    create_baseline_model,
    find_best_models_with_lazypredict,
    tune_model_hyperparameters,
    evaluate_model,
    log_model_to_mlflow,
    import_model_class
)
from predictor.drift_analyzer import (
    generate_drift_report,
    compare_models_performance,
    analyze_model_drift_over_time
)


def setup_logger(log_file=None):
    """Set up logger configuration"""
    # Remove default logger
    logger.remove()
    
    # Add stderr logger with INFO level
    logger.add(sys.stderr, level="INFO")
    
    # Add file logger if specified
    if log_file:
        log_dir = Path(log_file).parent
        os.makedirs(log_dir, exist_ok=True)
        logger.add(log_file, rotation="10 MB", level="DEBUG")
    
    return logger


def setup_mlflow():
    """Set up MLflow tracking"""
    # Set MLflow tracking URI from config
    mlflow.set_tracking_uri(config.mlflow_tracking_uri)
    
    # Set or create the experiment
    experiment = mlflow.get_experiment_by_name(config.mlflow_experiment_name)
    if experiment is None:
        mlflow.create_experiment(config.mlflow_experiment_name)
    
    # Set the experiment as active
    mlflow.set_experiment(config.mlflow_experiment_name)
    
    logger.info(f"MLflow configured with tracking URI: {config.mlflow_tracking_uri}")
    logger.info(f"Using experiment: {config.mlflow_experiment_name}")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Crypto Price Predictor")
    
    # Main settings
    parser.add_argument(
        "--pairs", 
        type=str, 
        nargs="+", 
        default=None, 
        help="Cryptocurrency pairs to process (e.g., BTC/EUR ETH/USD). If not specified, all available pairs will be used."
    )
    
    # Prediction horizon
    parser.add_argument(
        "--prediction-horizon", 
        type=int, 
        default=None, 
        help=f"Prediction horizon in minutes (default: {config.prediction_horizon})"
    )
    
    # TimeSeriesSplit parameters
    parser.add_argument(
        "--n-splits", 
        type=int, 
        default=5, 
        help="Number of splits for TimeSeriesSplit (default: 5)"
    )
    parser.add_argument(
        "--test-size", 
        type=int, 
        default=None, 
        help="Size of test set for each split in TimeSeriesSplit"
    )
    
    # Hyperparameter tuning
    parser.add_argument(
        "--max-trials", 
        type=int, 
        default=None, 
        help=f"Maximum number of hyperparameter optimization trials (default: {config.max_trials})"
    )
    parser.add_argument(
        "--top-models", 
        type=int, 
        default=3, 
        help="Number of top models to select from LazyPredict (default: 3)"
    )
    
    # Logging and reporting
    parser.add_argument(
        "--log-file", 
        type=str, 
        default=None, 
        help="Path to log file. If not specified, logs will only be sent to stderr."
    )
    parser.add_argument(
        "--generate-reports", 
        action="store_true", 
        help="Generate data profiling and drift reports"
    )
    
    return parser.parse_args()


def run_full_workflow(args):
    """Run the full crypto price prediction workflow"""
    # Initialize logger
    setup_logger(args.log_file)
    
    # Print configuration
    logger.info("Starting crypto price prediction workflow")
    logger.info(f"Using prediction horizon: {config.prediction_horizon} minutes")
    logger.info(f"Using TimeSeriesSplit with n_splits={args.n_splits}, test_size={args.test_size or 'auto'}")
    
    # Override config values with command line arguments if provided
    if args.prediction_horizon is not None:
        config.prediction_horizon = args.prediction_horizon
    if args.max_trials is not None:
        config.max_trials = args.max_trials
    
    # Setup MLflow
    setup_mlflow()
    
    # Get pairs to process
    if args.pairs is None or len(args.pairs) == 0:
        # If no pairs specified, fetch all available pairs
        available_pairs = fetch_available_pairs()
        if not available_pairs:
            logger.error("No cryptocurrency pairs found in database")
            return 1
        pairs_to_process = available_pairs
    else:
        pairs_to_process = args.pairs
    
    logger.info(f"Processing {len(pairs_to_process)} pairs: {', '.join(pairs_to_process)}")
    
    # Process each pair
    results = {}
    
    for pair in pairs_to_process:
        with mlflow.start_run(run_name=f"prediction_{pair}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"):
            # Log parameters
            mlflow.log_params({
                "pair": pair,
                "prediction_horizon": config.prediction_horizon,
                "n_splits": args.n_splits,
                "test_size": args.test_size,
                "max_trials": config.max_trials
            })
            
            try:
                logger.info(f"Processing pair: {pair}")
                
                # 1. Fetch technical indicators data
                logger.info(f"Fetching technical indicators data for {pair}")
                data = fetch_technical_indicators(pair)
                if data.empty:
                    logger.warning(f"No data found for pair {pair}. Skipping.")
                    mlflow.log_param("data_fetched", False)
                    continue
                
                logger.info(f"Fetched {len(data)} records for {pair}")
                mlflow.log_param("data_fetched", True)
                mlflow.log_metric("data_records", len(data))
                
                # 2. Validate data
                logger.info("Validating data")
                is_valid, validation_results = validate_timeseries_data(data)
                mlflow.log_param("data_valid", is_valid)
                
                if not is_valid:
                    logger.warning("Data validation failed. Skipping this pair.")
                    continue
                
                # 3. Generate data profile if requested
                if args.generate_reports:
                    logger.info("Generating data profile report")
                    ensure_reports_dir()
                    profile = profile_dataframe(
                        data, 
                        title=f"Technical Indicators Profile - {pair}"
                    )
                    profile_path = str(REPORTS_DIR / f"profile_{pair.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
                    profile.to_file(profile_path)
                    mlflow.log_artifact(profile_path)
                
                # 4. Preprocess data
                logger.info("Preprocessing data")
                
                # Handle missing values
                data = handle_missing_values(data)
                
                # Create target variable based on prediction horizon
                target_column = f"future_close_{config.prediction_horizon}m"
                data = create_target_variable(
                    data, 
                    prediction_horizon=config.prediction_horizon,
                    target_column=target_column
                )
                
                # Split data into train/validation/test sets using TimeSeriesSplit
                logger.info("Splitting data with TimeSeriesSplit")
                train_data, val_data, test_data = split_timeseries_data(
                    data,
                    n_splits=args.n_splits,
                    test_size=args.test_size
                )
                
                mlflow.log_metrics({
                    "train_size": len(train_data),
                    "validation_size": len(val_data),
                    "test_size": len(test_data)
                })
                
                # Create feature matrices and target variables
                train_X, train_y = create_feature_matrix(train_data, target_column)
                val_X, val_y = create_feature_matrix(val_data, target_column)
                test_X, test_y = create_feature_matrix(test_data, target_column)
                
                # Normalize features
                train_X_scaled, val_X_scaled, test_X_scaled, _ = normalize_features(train_X, val_X, test_X)
                
                # 5. Create baseline model
                logger.info("Creating baseline model")
                baseline_metrics = create_baseline_model(
                    train_X, train_y, test_X, test_y
                )
                
                # Log baseline model metrics
                mlflow.log_metrics({
                    "baseline_mae": baseline_metrics["test_mae"],
                    "baseline_rmse": baseline_metrics["test_rmse"],
                    "baseline_r2": baseline_metrics["test_r2"]
                })
                
                # 6. Find best models with LazyPredict
                logger.info("Finding best models with LazyPredict")
                lazy_models_results, predictions = find_best_models_with_lazypredict(
                    train_X_scaled, train_y, val_X_scaled, val_y, top_n=args.top_models
                )
                
                # Get top N models
                top_n = min(args.top_models, len(lazy_models_results))
                top_models = lazy_models_results.head(top_n)
                
                logger.info(f"Top {top_n} models:")
                for idx, (model_name, row) in enumerate(top_models.iterrows()):
                    if 'MAE' in row and 'R-Squared' in row:
                        logger.info(f"  {idx + 1}. {model_name}: MAE={row['MAE']:.4f}, R^2={row['R-Squared']:.4f}")
                    else:
                        logger.info(f"  {idx + 1}. {model_name}: {row}")
                
                # 7. Hyperparameter tuning for top models
                best_model = None
                best_model_name = None
                best_metrics = None
                
                for model_name in top_models.index:
                    logger.info(f"Tuning hyperparameters for {model_name}")
                    
                    try:
                        with mlflow.start_run(run_name=f"tuning_{model_name}", nested=True):
                            mlflow.log_param("model_name", model_name)
                            
                            # Import model class
                            model_class = import_model_class(model_name)
                            if model_class is None:
                                logger.warning(f"Could not import model class for {model_name}. Skipping.")
                                continue
                            
                            # Tune hyperparameters using Optuna
                            tuned_model, best_params, study = tune_model_hyperparameters(
                                model_class, 
                                train_X_scaled, train_y, 
                                val_X_scaled, val_y,
                                n_trials=config.max_trials
                            )
                            
                            # Evaluate on test data
                            metrics, _, _ = evaluate_model(tuned_model, train_X_scaled, train_y, test_X_scaled, test_y)
                            
                            mlflow.log_metrics({
                                "test_mae": metrics["test_mae"],
                                "test_rmse": metrics["test_rmse"],
                                "test_r2": metrics["test_r2"]
                            })
                            
                            # Log best parameters
                            mlflow.log_params(best_params)
                            
                            # Update best model if this one is better (lower MAE)
                            if best_metrics is None:
                                best_model = tuned_model
                                best_model_name = model_name
                                best_metrics = metrics
                            elif metrics["test_mae"] < best_metrics["test_mae"]:
                                best_model = tuned_model
                                best_model_name = model_name
                                best_metrics = metrics
                    except Exception as e:
                        logger.error(f"Error tuning {model_name}: {str(e)}")
                        continue
                
                # 8. Compare best model with baseline
                if best_model is not None:
                    logger.info(f"Best model: {best_model_name} with MAE={best_metrics['test_mae']:.4f}")
                    logger.info(f"Baseline MAE: {baseline_metrics['test_mae']:.4f}")
                    
                    improvement = ((baseline_metrics["test_mae"] - best_metrics["test_mae"]) / 
                                  baseline_metrics["test_mae"]) * 100
                    
                    logger.info(f"Improvement over baseline: {improvement:.2f}%")
                    
                    mlflow.log_metrics({
                        "best_model_mae": best_metrics["test_mae"],
                        "best_model_rmse": best_metrics["test_rmse"],
                        "best_model_r2": best_metrics["test_r2"],
                        "improvement_pct": improvement
                    })
                    
                    # Log the best model
                    mlflow.sklearn.log_model(best_model, f"models/{best_model_name}")
                    
                    # 9. Generate drift reports
                    if args.generate_reports:
                        logger.info("Generating drift reports")
                        
                        # Make predictions with best model
                        best_model_preds = best_model.predict(test_X_scaled)
                        baseline_preds = test_X['close'] if 'close' in test_X.columns else train_y.mean()
                        
                        # Compare model performance
                        report, report_path = compare_models_performance(
                            baseline_preds, best_model_preds, test_y, pair
                        )
                        
                        # Log the report as an artifact
                        mlflow.log_artifact(report_path)
                        
                        # Add time information back for drift analysis
                        test_X_with_time = test_X.copy()
                        if 'timestamp' in test_data.columns:
                            test_X_with_time['timestamp'] = test_data.iloc[-len(test_X):]['timestamp'].values
                        elif 'window_start_ms' in test_data.columns:
                            test_X_with_time['timestamp'] = pd.to_datetime(test_data.iloc[-len(test_X):]['window_start_ms'], unit='ms')
                        
                        # Analyze model drift over time
                        drift_metrics = analyze_model_drift_over_time(
                            best_model, test_X_with_time, test_y
                        )
                        
                        # Save drift metrics to CSV
                        from predictor.drift_analyzer import DRIFT_REPORTS_DIR
                        os.makedirs(DRIFT_REPORTS_DIR, exist_ok=True)
                        drift_csv_path = DRIFT_REPORTS_DIR / f"drift_metrics_{pair.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                        drift_metrics.to_csv(drift_csv_path)
                        mlflow.log_artifact(str(drift_csv_path))
                    
                    # Store results
                    results[pair] = {
                        "best_model": best_model,
                        "best_model_name": best_model_name,
                        "best_metrics": best_metrics,
                        "baseline_metrics": baseline_metrics,
                        "improvement_pct": improvement
                    }
                else:
                    logger.warning("No best model found after hyperparameter tuning")
            
            except Exception as e:
                logger.error(f"Error processing pair {pair}: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
    
    # Print summary
    logger.info("\n--- SUMMARY ---")
    logger.info(f"Processed {len(pairs_to_process)} pairs")
    logger.info(f"Successfully modeled {len(results)} pairs")
    
    if results:
        best_pair = None
        best_improvement = -float('inf')
        
        for pair, result in results.items():
            logger.info(f"{pair}: {result['best_model_name']} - " +
                       f"MAE={result['best_metrics']['test_mae']:.4f}, " +
                       f"improvement={result['improvement_pct']:.2f}%")
            
            if result['improvement_pct'] > best_improvement:
                best_improvement = result['improvement_pct']
                best_pair = pair
        
        if best_pair:
            logger.info(f"\nBest overall model: {best_pair} with {results[best_pair]['improvement_pct']:.2f}% improvement")
    
    return 0


if __name__ == "__main__":
    args = parse_args()
    sys.exit(run_full_workflow(args)) 