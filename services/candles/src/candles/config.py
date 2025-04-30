"""Config settings for the candles service"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Config settings for the candles service"""
    model_config = SettingsConfigDict(
        env_file='../../settings.env', env_file_encoding='utf-8'
    )

    kafka_broker_address: str
    kafka_input_topic: str
    kafka_output_topic: str
    kafka_consumer_group: str
    window_in_sec: int
    emit_intermediate_candles: bool


config = Settings()
