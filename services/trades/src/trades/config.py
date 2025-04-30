"""Config settings for the trades service"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Config settings for the trades service"""
    model_config = SettingsConfigDict(
        env_file="../../settings.env", env_file_encoding="utf-8"
    )
    product_ids: list[str] = ["BTC/EUR", "ETH/EUR", "SOL/EUR", "XRP/EUR"]
    kafka_broker_address: str
    kafka_topic: str


config = Settings()

print(config)
