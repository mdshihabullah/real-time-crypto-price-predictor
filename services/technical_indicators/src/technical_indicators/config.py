"""
Configuration module for the *technical_indicators* service.

• Loads **required** settings from environment variables / .env  
• Loads **optional / override** settings from a YAML file  
• Merges the two sources (YAML wins) and validates everything with Pydantic
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime settings for the service."""

    # ------------------------------------------------------------------ #
    # Where pydantic should also look for key-value pairs
    # ------------------------------------------------------------------ #
    model_config = SettingsConfigDict(
        env_file="../../settings.env",
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

    # Technical-indicator-specific parameters (live in YAML by design)
    sma_periods: List[int] = [7, 14, 21, 60]

    # ------------------------------------------------------------------ #
    # Unified loader
    # ------------------------------------------------------------------ #
    @classmethod
    def load(
        cls,
        yaml_path: str | os.PathLike = "../../ti_config.yaml",
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
            # Absence of YAML is *not* fatal – we can run with pure env vars
            print(f"[settings] YAML file not found at {yaml_path}. Using env vars only.")

        # ---- 2) Parse env /.env  ---------------------------------------
        env_cfg = cls()  # reads env vars & .env thanks to BaseSettings

        # ---- 3) Merge (env overrides YAML) -----------------------------
        merged = {**yaml_cfg, **env_cfg.model_dump()}  # env wins

        # ---- 4) Validate final bundle and return -----------------------
        return cls(**merged)


# ---------------------------------------------------------------------- #
#  Public, ready-to-use configuration object
# ---------------------------------------------------------------------- #
config: Settings = Settings.load()
