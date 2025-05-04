"""Config settings for the candles service"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE_NAME = "settings.env"
ENV_FILE_PATH = Path(__file__).resolve().parents[2] / ENV_FILE_NAME

class Settings(BaseSettings):
    """Config settings for the candles service"""
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH), env_file_encoding='utf-8'
    )

    kafka_broker_address: str
    kafka_input_topic: str
    kafka_output_topic: str
    kafka_consumer_group: str
    window_in_sec: int
    emit_intermediate_candles: bool


config = Settings()
