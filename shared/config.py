"""Configuration management for tools."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from pydantic import BaseModel


class BaseConfig(BaseModel):
    """Base configuration class."""

    debug: bool = False
    log_level: str = "INFO"
    output_format: str = "table"  # table, json, csv

    class Config:
        """Pydantic config."""

        extra = "allow"


def load_env(env_file: Optional[str] = None) -> None:
    """
    Load environment variables from .env file.

    Args:
        env_file: Path to .env file (defaults to .env in current directory)
    """
    if env_file:
        env_path = Path(env_file)
    else:
        env_path = Path(".env")

    if env_path.exists():
        load_dotenv(dotenv_path=env_path)


def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get environment variable.

    Args:
        key: Environment variable name
        default: Default value if not found

    Returns:
        Environment variable value or default
    """
    return os.getenv(key, default)


def parse_config_file(config_path: Path) -> Dict[str, Any]:
    """
    Parse configuration file (JSON or YAML).

    Args:
        config_path: Path to config file

    Returns:
        Configuration dictionary
    """
    import json

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    if config_path.suffix == ".json":
        with open(config_path) as f:
            return json.load(f)
    elif config_path.suffix in [".yaml", ".yml"]:
        try:
            import yaml

            with open(config_path) as f:
                return yaml.safe_load(f)
        except ImportError:
            raise ImportError("PyYAML is required for YAML config files")
    else:
        raise ValueError(f"Unsupported config file format: {config_path.suffix}")
