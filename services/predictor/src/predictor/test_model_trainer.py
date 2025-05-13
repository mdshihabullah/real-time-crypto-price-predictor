"""Test script for the ModelTrainer class"""

import numpy as np
import pandas as pd
from sklearn.datasets import fetch_california_housing
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from loguru import logger

from predictor.model_trainer import ModelTrainer


def test_model_trainer():
    """Test the ModelTrainer class with a small dataset"""
    logger.info("Testing ModelTrainer with the California housing dataset")
    
    # Load a sample dataset
    housing_dataset = fetch_california_housing(as_frame=True)
    X = housing_dataset.data
    y = housing_dataset.target
    
    # Add a dummy 'pair' column to simulate the cryptocurrency pair
    X["pair"] = "BTC_USD"
    
    # Split the data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    # Scale features (typically done in cryptocurrency data preprocessing)
    scaler = StandardScaler()
    X_train_scaled = pd.DataFrame(
        scaler.fit_transform(X_train.drop(columns=["pair"])),
        columns=X_train.columns.drop("pair"),
        index=X_train.index,
    )
    X_test_scaled = pd.DataFrame(
        scaler.transform(X_test.drop(columns=["pair"])),
        columns=X_test.columns.drop("pair"),
        index=X_test.index,
    )
    
    # Prepare data structure similar to what's used in main.py
    train_val_test_data = {
        "BTC_USD": {
            "X_train": X_train_scaled,
            "y_train": y_train,
            "X_test": X_test_scaled,
            "y_test": y_test,
            "scaler": scaler,
        }
    }
    
    # Initialize and test ModelTrainer
    model_trainer = ModelTrainer(top_n_models=3, ignore_warnings=True)
    
    # Test individual model training
    logger.info("Testing individual model training")
    models_df, top_models = model_trainer.train_models(
        X_train_scaled, 
        X_test_scaled, 
        y_train, 
        y_test, 
        "BTC_USD"
    )
    
    if models_df is not None:
        logger.info(f"Successfully trained {len(models_df)} models")
        logger.info(f"Top 3 models: {top_models}")
    else:
        logger.error("Model training failed")
        return False
    
    # Test training for all pairs
    logger.info("Testing training for all pairs")
    top_n_models = model_trainer.train_for_all_pairs(train_val_test_data)
    
    if "BTC_USD" in top_n_models and top_n_models["BTC_USD"]:
        logger.info(f"Successfully trained models for all pairs")
        logger.info(f"Top models for BTC_USD: {top_n_models['BTC_USD']}")
        return True
    else:
        logger.error("Training for all pairs failed")
        return False


if __name__ == "__main__":
    success = test_model_trainer()
    if success:
        logger.info("ModelTrainer testing completed successfully")
    else:
        logger.error("ModelTrainer testing failed")
