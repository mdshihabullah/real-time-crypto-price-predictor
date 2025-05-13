"""
Configuration module for the *technical_indicators* service.

• Loads **required** settings from environment variables / .env
• Loads **optional / override** settings from a YAML file
• Merges the two sources and validates everything with Pydantic
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE_NAME = "settings.env"
ENV_FILE_PATH = Path(__file__).resolve().parents[2] / ENV_FILE_NAME

CONFIG_FILE_NAME = "ti_config.yaml"
CONFIG_FILE_PATH = Path(__file__).resolve().parents[2] / CONFIG_FILE_NAME

class Settings(BaseSettings):
    """All runtime settings for the service."""

    # ------------------------------------------------------------------ #
    # Where pydantic should also look for key-value pairs
    # ------------------------------------------------------------------ #
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
    )

    # ------------------------------------------------------------------ #
    # Mandatory settings (must come from env /.env or YAML)
    # ------------------------------------------------------------------ #
    kafka_broker_address: str
    kafka_input_topic: str
    kafka_output_topic: str
    kafka_consumer_group: str
    window_in_sec: int
    risingwave_table_name: str


    # ------------------------------------------------------------------ #
    # Optional settings with sane defaults
    # ------------------------------------------------------------------ #
    max_candles_in_state: int = 60

    # ───── indicator specific ─────
    # Declared with default so an env-only instantiation passes validation.
    periods: List[int] = []

    # ------------------------------------------------------------------ #
    # Unified loader
    # ------------------------------------------------------------------ #
    @classmethod
    def load(
        cls,
        yaml_path: str | os.PathLike = str(CONFIG_FILE_PATH),
    ) -> "Settings":
        """
        Build a Settings instance from two sources:

        1.   Environment variables / `.env` (higher priority)
        2.   YAML file (lower priority)

        The YAML file is still useful for structured or lengthy parameters
        (lists, dicts, etc.) while env vars remain convenient for secrets
        and quick overrides.
        """
        # ---- 1) Parse YAML if it exists --------------------------------
        yaml_cfg: dict = {}
        yaml_path = Path(yaml_path)
        if yaml_path.exists():
            try:
                yaml_cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as exc:
                raise ValueError(f"Could not parse YAML config: {exc}") from exc
        else:
            # YAML file is required for periods configuration
            raise FileNotFoundError(f"YAML configuration file not found at {yaml_path}.\
                    This file is required for technical indicators configuration.")

        # ---- 2) Parse env /.env  ---------------------------------------
        env_settings = cls()  # reads env vars & .env thanks to BaseSettings
        env_dump = env_settings.model_dump()
        
        # Get default field values to avoid overriding YAML with defaults
        default_settings = cls()
        default_values = {k: v for k, v in default_settings.__dict__.items() 
                         if not k.startswith('_')}
        
        # Only include env values that are explicitly set (different from defaults)
        explicit_env_values = {}
        for key, value in env_dump.items():
            # If this field isn't in defaults or the value differs from default
            if key not in default_values or value != default_values[key]:
                explicit_env_values[key] = value

        # ---- 3) Merge (explicit env overrides YAML) --------------------
        merged = {**yaml_cfg, **explicit_env_values}  # explicit env wins

        # ---- 4) Validate final bundle and return -----------------------
        return cls(**merged)


# ---------------------------------------------------------------------- #
#  Public, ready-to-use configuration object
# ---------------------------------------------------------------------- #
config: Settings = Settings.load()
