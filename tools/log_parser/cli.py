"""CLI interface for Log Parser."""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from shared.cli import create_table, error, handle_errors, info, print_table, success
from shared.logger import setup_logger

from .parser import LogEntry, LogFormat, LogParser

console = Console()


def display_entries(entries: list[LogEntry], limit: Optional[int] = None) -> None:
    """Display log entries in a table."""
    if not entries:
        info("No log entries found")
        return

    display_count = len(entries) if limit is None else min(limit, len(entries))

    table = create_table(title=f"Log Entries ({display_count} of {len(entries)})")
    table.add_column("#", justify="right", style="dim", width=6)
    table.add_column("Time", style="cyan", width=20)
    table.add_column("Level", width=10)
    table.add_column("Message", no_wrap=False)

    for entry in entries[:display_count]:
        # Color level
        if entry.level:
            level_upper = entry.level.upper()
            if "ERROR" in level_upper or "CRIT" in level_upper or "FATAL" in level_upper:
                level_str = f"[bold red]{entry.level}[/bold red]"
            elif "WARN" in level_upper:
                level_str = f"[bold yellow]{entry.level}[/bold yellow]"
            elif "INFO" in level_upper:
                level_str = f"[green]{entry.level}[/green]"
            else:
                level_str = entry.level
        else:
            level_str = "-"

        timestamp_str = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S") if entry.timestamp else "-"

        table.add_row(
            str(entry.line_number),
            timestamp_str,
            level_str,
            entry.message[:100],
        )

    print_table(table)


def display_statistics(stats: dict) -> None:
    """Display statistics."""
    console.print(Panel("[bold cyan]Log Statistics[/bold cyan]"))

    console.print(f"\n[bold yellow]📊 Overview:[/bold yellow]")
    console.print(f"  Total Entries: {stats['total']:,}")

    if stats.get("first_timestamp"):
        console.print(f"  First Entry:   {stats['first_timestamp']}")
        console.print(f"  Last Entry:    {stats['last_timestamp']}")

        if stats.get("time_span_seconds"):
            hours = stats["time_span_seconds"] / 3600
            console.print(f"  Time Span:     {hours:.2f} hours")

    # Level distribution
    if stats.get("levels"):
        console.print(f"\n[bold yellow]📈 Level Distribution:[/bold yellow]")

        levels = stats["levels"]
        total_with_level = sum(levels.values())

        table = create_table(title=None)
        table.add_column("Level", style="bold")
        table.add_column("Count", justify="right", style="cyan")
        table.add_column("Percentage", justify="right")
        table.add_column("Visual", width=30)

        for level, count in sorted(levels.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_with_level * 100) if total_with_level > 0 else 0
            bar_length = int((percentage / 100) * 25)
            bar = "█" * bar_length + "░" * (25 - bar_length)

            table.add_row(level, f"{count:,}", f"{percentage:.1f}%", bar)

        print_table(table)

    # Top errors
    if stats.get("top_errors"):
        console.print(f"\n[bold yellow]🔥 Top Errors:[/bold yellow]")
        for idx, (message, count) in enumerate(stats["top_errors"][:10], 1):
            console.print(f"  {idx}. [{count}x] {message[:80]}")

    # Sources
    if stats.get("sources"):
        console.print(f"\n[bold yellow]📍 Top Sources:[/bold yellow]")
        for source, count in list(stats["sources"].items())[:10]:
            console.print(f"  {source}: {count:,}")

    console.print()


@click.command()
@click.argument("log_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--format",
    "-f",
    type=click.Choice(["nginx", "apache", "json", "syslog", "python", "docker", "auto"], case_sensitive=False),
    default="auto",
    help="Log format (auto-detect by default)",
)
@click.option(
    "--level",
    "-l",
    multiple=True,
    help="Filter by log level (ERROR, WARNING, etc.)",
)
@click.option(
    "--pattern",
    "-p",
    help="Filter by regex pattern",
)
@click.option(
    "--since",
    help="Filter entries after this time (e.g., '2024-01-01 12:00:00')",
)
@click.option(
    "--until",
    help="Filter entries before this time",
)
@click.option(
    "--last",
    type=str,
    help="Show entries from last N hours/minutes (e.g., '1h', '30m')",
)
@click.option(
    "--stats",
    "-s",
    is_flag=True,
    help="Show statistics",
)
@click.option(
    "--errors-only",
    "-e",
    is_flag=True,
    help="Show only errors",
)
@click.option(
    "--limit",
    type=int,
    default=50,
    help="Limit number of entries shown",
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    help="Output format",
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@handle_errors
def main(
    log_file: Path,
    format: str,
    level: tuple,
    pattern: Optional[str],
    since: Optional[str],
    until: Optional[str],
    last: Optional[str],
    stats: bool,
    errors_only: bool,
    limit: int,
    output: str,
    verbose: bool,
):
    """
    Log Parser - Extract insights from log files.

    Supports nginx, Apache, JSON, syslog, Python, and Docker logs.

    Examples:

        \b
        # Parse and show stats
        log-parser /var/log/nginx/access.log --stats

        \b
        # Show only errors
        log-parser app.log --errors-only

        \b
        # Filter by level
        log-parser app.log --level ERROR --level CRITICAL

        \b
        # Filter by pattern
        log-parser app.log --pattern "database.*error"

        \b
        # Last hour
        log-parser app.log --last 1h

        \b
        # Time range
        log-parser app.log --since "2024-01-01 10:00:00" --until "2024-01-01 12:00:00"

        \b
        # JSON output
        log-parser app.log --output json > report.json
    """
    # Setup logging
    log_level = "DEBUG" if verbose else "INFO"
    setup_logger(__name__, level=log_level)

    # Initialize parser
    log_format = LogFormat(format.lower())
    parser = LogParser(format=log_format)

    # Parse file
    info(f"Parsing log file: {log_file}")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
    ) as progress:
        task = progress.add_task("Parsing...", total=None)
        try:
            parser.parse_file(log_file)
            progress.update(task, completed=True)
        except Exception as e:
            error(f"Failed to parse log file: {e}")
            sys.exit(1)

    if not parser.entries:
        warning("No log entries found")
        sys.exit(0)

    success(f"Parsed {len(parser.entries)} entries")

    # Apply filters
    filtered_entries = parser.entries

    if errors_only:
        filtered_entries = parser.filter_by_level(["ERROR", "CRITICAL", "FATAL"])
        info(f"Filtered to {len(filtered_entries)} error entries")

    elif level:
        filtered_entries = parser.filter_by_level(list(level))
        info(f"Filtered to {len(filtered_entries)} entries with levels: {', '.join(level)}")

    if pattern:
        filtered_entries = parser.filter_by_pattern(pattern)
        info(f"Filtered to {len(filtered_entries)} entries matching pattern")

    # Time filters
    if last:
        # Parse last format (e.g., "1h", "30m")
        match = re.match(r"(\d+)([hm])", last)
        if not match:
            error("Invalid --last format. Use format like '1h' or '30m'")
            sys.exit(1)

        value = int(match.group(1))
        unit = match.group(2)

        now = datetime.now()
        if unit == "h":
            since_time = now - timedelta(hours=value)
        else:  # m
            since_time = now - timedelta(minutes=value)

        filtered_entries = parser.filter_by_time_range(start=since_time)
        info(f"Filtered to {len(filtered_entries)} entries from last {last}")

    elif since or until:
        since_time = datetime.fromisoformat(since) if since else None
        until_time = datetime.fromisoformat(until) if until else None

        filtered_entries = parser.filter_by_time_range(start=since_time, end=until_time)
        info(f"Filtered to {len(filtered_entries)} entries in time range")

    # Output
    if output == "json":
        data = {
            "total": len(filtered_entries),
            "entries": [
                {
                    "line": e.line_number,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                    "level": e.level,
                    "message": e.message,
                    "source": e.source,
                }
                for e in filtered_entries
            ],
        }

        if stats:
            data["statistics"] = parser.get_statistics()

        print(json.dumps(data, indent=2))
        sys.exit(0)

    # Table output
    if stats:
        statistics = parser.get_statistics()
        display_statistics(statistics)

    if not stats or len(filtered_entries) > 0:
        display_entries(filtered_entries, limit=limit if not stats else 20)

    if len(filtered_entries) > limit and not stats:
        info(f"Showing {limit} of {len(filtered_entries)} entries. Use --limit to show more.")

    sys.exit(0)


if __name__ == "__main__":
    import re  # Import needed for last filter
    main()
