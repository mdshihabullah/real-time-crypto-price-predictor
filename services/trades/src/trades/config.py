from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="services/trades/settings.env", env_file_encoding="utf-8"
    )
    product_ids: list[str] = ["BTC/EUR", "ETH/EUR", "SOL/EUR"]
    kafka_broker_address: str
    kafka_topic_name: str


config = Settings()

print(config)
