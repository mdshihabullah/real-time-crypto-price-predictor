"""Main script for crypto price prediction workflow"""

from loguru import logger

from predictor.config import config
from predictor.data_fetcher import fetch_technical_indicators_data, get_available_pairs
from predictor.data_preprocessor import prepare_time_series_data, split_timeseries_data
from predictor.mlflow_logger import (
    log_data_to_mlflow,
    log_profile_report_to_mlflow,
    log_to_mlflow,
    active_run,
    setup_mlflow,
)
from predictor.model_trainer import ModelTrainer

if __name__ == "__main__":
    logger.info("Starting crypto price prediction workflow")

    # Setup MLflow
    setup_mlflow()

    # Get available pairs
    pairs = get_available_pairs()
    logger.info(f"Available pairs: {pairs}")

    technical_indicators_data = {}
    pair_run_ids = {}  # Keep track of run IDs for each pair

    # Process each pair
    for pair in pairs:
        logger.info(f"Fetching technical indicators data for pair: {pair}")
        data = fetch_technical_indicators_data(pair)

        if not data.empty:
            logger.info(f"Fetched {len(data)} rows of data for pair: {pair}")
            # Log data and save the run ID # TODO: for debug purpose, remove .head(N)
            run_id = log_to_mlflow(pair, data.head(100))
            pair_run_ids[pair] = run_id
            technical_indicators_data[pair] = data
        else:
            logger.warning(f"Skipping MLflow logging for {pair} due to empty dataset")

    logger.info("Data profiling and MLflow logging completed for all pairs")

    # Prepare time series data using prepare_time_series_data function
    features_data = {}
    target_data = {}
    train_val_test_data = {}

    for pair in pairs:
        # Skip pairs with no data
        if pair not in technical_indicators_data:
            logger.warning(f"Skipping data preparation for {pair} due to no data")
            continue

        logger.info(f"Preparing time series data for pair: {pair}")

        # Use the active_run context for this pair to ensure all logs go to the same run
        with active_run(pair) as run:
            features_df, target, scaler = prepare_time_series_data(
                technical_indicators_data[pair],
                prediction_horizon=config.prediction_horizon,
                handle_na_strategy=config.handle_na_strategy,
            )
            logger.info(f"Time series data prepared for pair: {pair}")
            features_data[pair] = features_df
            target_data[pair] = target

            # These logs will go to the same run
            log_data_to_mlflow(pair, features_df, log_params=False)
            log_profile_report_to_mlflow(pair, features_df)

            # Split data into train and test sets
            logger.info(f"Splitting data into train and test sets for pair: {pair}")
            X_train, X_val, X_test = split_timeseries_data(
                features_df,
                n_splits=config.n_splits if hasattr(config, "n_splits") else 5,
                test_size=config.test_size if hasattr(config, "test_size") else None,
            )

            # Get corresponding target values
            y_train = target.loc[X_train.index]
            y_val = target.loc[X_val.index]
            y_test = target.loc[X_test.index]

            # Store the split data
            train_val_test_data[pair] = {
                "X_train": X_train.drop(columns=["pair"]),
                "y_train": y_train,
                "X_val": X_val.drop(columns=["pair"]),
                "y_val": y_val,
                "X_test": X_test.drop(columns=["pair"]),
                "y_test": y_test,
                "scaler": scaler,
            }

            logger.info(
                f"Data split for {pair}: X_train: {X_train.shape}, y_train: {y_train.shape}, "
                f"X_val: {X_val.shape}, y_val: {y_val.shape}, "
                f"X_test: {X_test.shape}, y_test: {y_test.shape}"
            )

    logger.info("Time series data preparation and splitting completed for all pairs")

    # Initialize and use the ModelTrainer for training models on all pairs
    logger.info("Starting model training for all pairs")
    top_n_models_count = config.top_n_models if hasattr(config, "top_n_models") else 5
    model_trainer = ModelTrainer(top_n_models=top_n_models_count, ignore_warnings=False)

    try:
        # Train models for all pairs and get top models for each pair
        all_top_models = model_trainer.train_for_all_pairs(train_val_test_data)

        # Log the top models for each pair
        for pair, models in all_top_models.items():
            if models:
                logger.info(f"Top {len(models)} models for {pair}: {models}")
            else:
                logger.warning(f"No successful models for {pair}")

        # Save the top models for future reference
        logger.info("Model training and evaluation completed successfully")

    except Exception as e:
        logger.error(f"Error in model training phase: {str(e)}")

    logger.info("Crypto price prediction workflow completed")
