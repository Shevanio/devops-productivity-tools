"""Common CLI utilities and helpers."""

from typing import Any, Callable, Optional

import click
from rich.console import Console
from rich.table import Table

console = Console()


def success(message: str) -> None:
    """Print success message."""
    console.print(f"✅ {message}", style="bold green")


def error(message: str) -> None:
    """Print error message."""
    console.print(f"❌ {message}", style="bold red")


def warning(message: str) -> None:
    """Print warning message."""
    console.print(f"⚠️  {message}", style="bold yellow")


def info(message: str) -> None:
    """Print info message."""
    console.print(f"ℹ️  {message}", style="bold blue")


def confirm(message: str, default: bool = False) -> bool:
    """
    Ask for user confirmation.

    Args:
        message: Confirmation message
        default: Default value if user just presses Enter

    Returns:
        True if confirmed, False otherwise
    """
    return click.confirm(message, default=default)


def create_table(title: Optional[str] = None) -> Table:
    """
    Create a rich table with consistent styling.

    Args:
        title: Optional table title

    Returns:
        Configured Table instance
    """
    return Table(title=title, show_header=True, header_style="bold cyan")


def print_table(table: Table) -> None:
    """Print a table to console."""
    console.print(table)


def handle_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator to handle common CLI errors gracefully.

    Usage:
        @click.command()
        @handle_errors
        def my_command():
            ...
    """

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            console.print("\n⚠️  Operation cancelled by user", style="yellow")
            raise click.Abort()
        except Exception as e:
            error(f"Unexpected error: {e}")
            if kwargs.get("debug"):
                raise
            raise click.Abort()

    return wrapper
