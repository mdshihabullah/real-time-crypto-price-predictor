"""Config settings for the trades service"""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE_NAME = "settings.env"
ENV_FILE_PATH = Path(__file__).resolve().parents[2] / ENV_FILE_NAME

# Product IDs to fetch from Kraken
PRODUCT_IDS = ["BTC/EUR", "ETH/EUR", "SOL/EUR", "XRP/EUR"]


# Number of days to fetch from Kraken
LAST_N_DAYS = 180

class Settings(BaseSettings):
    """Config settings for the trades service"""
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH), env_file_encoding="utf-8"
    )
    product_ids: list[str] = PRODUCT_IDS
    kafka_broker_address: str
    kafka_topic: str
    kraken_api_mode: Literal["REST", "WS"]
    last_n_days: int = LAST_N_DAYS

config = Settings()

print(config)
