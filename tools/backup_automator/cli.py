"""CLI for the Backup Automator."""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .automator import (
    BackupAutomator,
    BackupConfig,
    BackupDestination,
    BackupType,
    CompressionType,
    DestinationType,
)

console = Console()


@click.group()
def main() -> None:
    """Backup Automator - Automated incremental backups with compression and retention."""
    pass


@main.command()
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.argument("destination", type=click.Path(path_type=Path))
@click.option(
    "--type",
    "backup_type",
    type=click.Choice(["full", "incremental"]),
    default="full",
    help="Type of backup to create",
)
@click.option(
    "--compression",
    type=click.Choice(["none", "gzip", "bzip2", "xz"]),
    default="gzip",
    help="Compression algorithm to use",
)
@click.option(
    "--exclude",
    multiple=True,
    help="Patterns to exclude (can be specified multiple times)",
)
@click.option(
    "--retention-days",
    type=int,
    default=30,
    help="Number of days to retain backups",
)
@click.option(
    "--max-backups",
    type=int,
    help="Maximum number of backups to keep",
)
@click.option(
    "--prefix",
    default="backup",
    help="Prefix for backup filenames",
)
def create(
    source: Path,
    destination: Path,
    backup_type: str,
    compression: str,
    exclude: tuple,
    retention_days: int,
    max_backups: Optional[int],
    prefix: str,
) -> None:
    """Create a backup of SOURCE to DESTINATION.

    Examples:

        # Full backup with default settings
        backup-auto create /path/to/source /path/to/backups

        # Incremental backup with custom compression
        backup-auto create /path/to/source /path/to/backups --type incremental --compression xz

        # Backup with exclusions
        backup-auto create /path/to/source /path/to/backups --exclude "*.log" --exclude "node_modules"
    """
    try:
        # Create configuration
        config = BackupConfig(
            source_path=source,
            destinations=[
                BackupDestination(
                    type=DestinationType.LOCAL,
                    path=destination,
                    enabled=True,
                )
            ],
            compression=CompressionType(compression),
            retention_days=retention_days,
            max_backups=max_backups,
            exclude_patterns=list(exclude),
            backup_name_prefix=prefix,
        )

        # Create automator
        automator = BackupAutomator(config)

        # Create backup
        console.print(f"\n[cyan]Creating {backup_type} backup...[/cyan]")
        result = automator.create_backup(BackupType(backup_type))

        if result.success and result.backup_file and result.metadata:
            # Display success
            info_table = Table(show_header=False, box=None)
            info_table.add_column("Key", style="cyan")
            info_table.add_column("Value", style="white")

            info_table.add_row("Backup File", str(result.backup_file.name))
            info_table.add_row("Type", result.metadata.backup_type.value.upper())
            info_table.add_row("Files", str(result.metadata.file_count))
            info_table.add_row(
                "Size", _format_size(result.metadata.total_size)
            )
            info_table.add_row("Compression", result.metadata.compression.value)
            info_table.add_row("Duration", f"{result.duration_seconds:.2f}s")
            info_table.add_row("Hash (SHA256)", result.metadata.file_hash[:16] + "...")

            console.print(
                Panel(
                    info_table,
                    title="[green]✓ Backup Created Successfully[/green]",
                    border_style="green",
                )
            )

        else:
            console.print(
                Panel(
                    f"[red]Error: {result.error}[/red]",
                    title="[red]✗ Backup Failed[/red]",
                    border_style="red",
                )
            )
            sys.exit(1)

    except Exception as e:
        console.print(
            Panel(
                f"[red]Error: {str(e)}[/red]",
                title="[red]✗ Backup Failed[/red]",
                border_style="red",
            )
        )
        sys.exit(1)


@main.command()
@click.argument("backup_file", type=click.Path(exists=True, path_type=Path))
@click.argument("restore_path", type=click.Path(path_type=Path))
def restore(backup_file: Path, restore_path: Path) -> None:
    """Restore a backup to RESTORE_PATH.

    Examples:

        # Restore backup to original location
        backup-auto restore /backups/backup_full_20240101_120000.tar.gz /path/to/restore
    """
    try:
        # Create minimal config (not used for restore)
        config = BackupConfig(
            source_path=Path("."),
            destinations=[],
        )

        automator = BackupAutomator(config)

        console.print(f"\n[cyan]Restoring backup...[/cyan]")
        success = automator.restore_backup(backup_file, restore_path)

        if success:
            console.print(
                Panel(
                    f"[green]Backup restored to: {restore_path}[/green]",
                    title="[green]✓ Restore Successful[/green]",
                    border_style="green",
                )
            )
        else:
            console.print(
                Panel(
                    "[red]Failed to restore backup[/red]",
                    title="[red]✗ Restore Failed[/red]",
                    border_style="red",
                )
            )
            sys.exit(1)

    except Exception as e:
        console.print(
            Panel(
                f"[red]Error: {str(e)}[/red]",
                title="[red]✗ Restore Failed[/red]",
                border_style="red",
            )
        )
        sys.exit(1)


@main.command()
@click.argument("backup_file", type=click.Path(exists=True, path_type=Path))
def verify(backup_file: Path) -> None:
    """Verify the integrity of a backup.

    Examples:

        # Verify backup integrity
        backup-auto verify /backups/backup_full_20240101_120000.tar.gz
    """
    try:
        # Create minimal config
        config = BackupConfig(
            source_path=Path("."),
            destinations=[],
        )

        automator = BackupAutomator(config)

        console.print(f"\n[cyan]Verifying backup...[/cyan]")
        is_valid = automator.verify_backup(backup_file)

        if is_valid:
            console.print(
                Panel(
                    "[green]Backup integrity verified successfully[/green]",
                    title="[green]✓ Valid Backup[/green]",
                    border_style="green",
                )
            )
        else:
            console.print(
                Panel(
                    "[red]Backup verification failed - file may be corrupted[/red]",
                    title="[red]✗ Invalid Backup[/red]",
                    border_style="red",
                )
            )
            sys.exit(1)

    except Exception as e:
        console.print(
            Panel(
                f"[red]Error: {str(e)}[/red]",
                title="[red]✗ Verification Failed[/red]",
                border_style="red",
            )
        )
        sys.exit(1)


@main.command()
@click.argument("destination", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--prefix",
    default="backup",
    help="Filter by backup prefix",
)
def list(destination: Path, prefix: str) -> None:
    """List all backups in DESTINATION.

    Examples:

        # List all backups
        backup-auto list /path/to/backups

        # List backups with custom prefix
        backup-auto list /path/to/backups --prefix mybackup
    """
    try:
        # Create minimal config
        config = BackupConfig(
            source_path=Path("."),
            destinations=[
                BackupDestination(
                    type=DestinationType.LOCAL,
                    path=destination,
                    enabled=True,
                )
            ],
            backup_name_prefix=prefix,
        )

        automator = BackupAutomator(config)
        backups = automator.list_backups()

        if not backups:
            console.print(
                Panel(
                    f"[yellow]No backups found in {destination}[/yellow]",
                    title="[yellow]No Backups[/yellow]",
                    border_style="yellow",
                )
            )
            return

        # Display backups table
        table = Table(title=f"\n[cyan]Backups in {destination}[/cyan]")
        table.add_column("Timestamp", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Files", style="yellow")
        table.add_column("Size", style="green")
        table.add_column("Compression", style="blue")
        table.add_column("Hash", style="white")

        for backup in backups:
            table.add_row(
                backup.timestamp,
                backup.backup_type.value.upper(),
                str(backup.file_count),
                _format_size(backup.total_size),
                backup.compression.value,
                backup.file_hash[:12] + "...",
            )

        console.print(table)
        console.print(f"\n[cyan]Total backups: {len(backups)}[/cyan]\n")

    except Exception as e:
        console.print(
            Panel(
                f"[red]Error: {str(e)}[/red]",
                title="[red]✗ List Failed[/red]",
                border_style="red",
            )
        )
        sys.exit(1)


def _format_size(size_bytes: int) -> str:
    """Format bytes to human-readable size.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


if __name__ == "__main__":
    main()
