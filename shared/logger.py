"""Logging configuration using rich for beautiful console output."""

import logging
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

console = Console()


def setup_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    Configure and return a logger with rich formatting.

    Args:
        name: Name of the logger (usually __name__)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """
    log_level = getattr(logging, level.upper()) if level else logging.INFO

    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )

    logger = logging.getLogger(name)
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get an existing logger or create a new one."""
    return logging.getLogger(name)
