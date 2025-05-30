"""Config settings for the predictor service"""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE_NAME = "settings.env"
ENV_FILE_PATH = Path(__file__).resolve().parents[2] / ENV_FILE_NAME

# Default window sizes for time-based splitting of data
DEFAULT_TRAIN_WINDOW = 60  # in days
DEFAULT_VALIDATION_WINDOW = 14  # in days
DEFAULT_TEST_WINDOW = 7  # in days

# Default prediction horizon in minutes
DEFAULT_PREDICTION_HORIZON = 5

# RisingWave DB default parameters
DEFAULT_RW_HOST = "localhost"
DEFAULT_RW_PORT = 4567
DEFAULT_RW_DB = "dev"
DEFAULT_RW_USER = "root"
DEFAULT_RW_PASSWORD = ""

# Default max number of hyperparameter tuning trials
DEFAULT_MAX_TRIALS = 3


class Settings(BaseSettings):
    """Config settings for the predictor service"""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH), env_file_encoding="utf-8"
    )

    # RisingWave DB settings
    risingwave_host: str = DEFAULT_RW_HOST
    risingwave_port: int = DEFAULT_RW_PORT
    risingwave_db: str = DEFAULT_RW_DB
    risingwave_user: str = DEFAULT_RW_USER
    risingwave_password: str = DEFAULT_RW_PASSWORD

    # MLflow settings
    mlflow_tracking_uri: str
    mlflow_experiment_name: str = "crypto_price_prediction"
    mlflow_tracking_username: str
    mlflow_tracking_password: str

    # Model settings
    prediction_horizon: int = DEFAULT_PREDICTION_HORIZON
    handle_na_strategy: str = "drop"
    train_window: int = DEFAULT_TRAIN_WINDOW
    validation_window: int = DEFAULT_VALIDATION_WINDOW
    test_window: int = DEFAULT_TEST_WINDOW
    max_trials: int = DEFAULT_MAX_TRIALS
    top_n_models: int = 1
    # Default number of days to use for training data, None for all available data
    training_data_horizon: Optional[int] = None

    # Available pairs for prediction, if empty all pairs will be used
    pairs: Optional[str] = None


config = Settings()
