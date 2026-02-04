"""CLI interface for Docker Image Analyzer."""

import json
import sys
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn

from shared.cli import create_table, error, handle_errors, info, print_table, success, warning
from shared.logger import setup_logger

from .analyzer import DockerAnalyzer, ImageAnalysis

console = Console()


def create_size_bar(size: int, max_size: int, width: int = 30) -> str:
    """
    Create ASCII bar for size visualization.

    Args:
        size: Current size
        max_size: Maximum size for scaling
        width: Width of bar in characters

    Returns:
        ASCII bar string
    """
    if max_size == 0:
        return ""

    filled = int((size / max_size) * width)
    bar = "█" * filled + "░" * (width - filled)
    return bar


def display_analysis(analysis: ImageAnalysis, show_layers: bool = True) -> None:
    """
    Display image analysis with rich formatting.

    Args:
        analysis: ImageAnalysis object
        show_layers: Whether to show layer breakdown
    """
    if analysis.error:
        error(f"Failed to analyze {analysis.name}")
        error(f"Error: {analysis.error}")
        return

    # Header
    console.print(Panel(f"[bold cyan]{analysis.name}[/bold cyan]", title="Docker Image Analysis"))

    # Basic info
    console.print("\n[bold yellow]Image Information:[/bold yellow]")
    console.print(f"  ID:           {analysis.id[:20]}...")
    console.print(f"  Tags:         {', '.join(analysis.tags) if analysis.tags else 'None'}")
    console.print(f"  Size:         [bold]{analysis.size_human}[/bold]")
    console.print(f"  Layers:       {analysis.layer_count}")
    console.print(f"  Architecture: {analysis.architecture}")
    console.print(f"  OS:           {analysis.os}")
    console.print(f"  Created:      {analysis.created[:19] if len(analysis.created) > 19 else analysis.created}")

    # Show layers if requested
    if show_layers and analysis.layers:
        console.print("\n[bold yellow]Layer Breakdown:[/bold yellow]")

        table = create_table(title=None)
        table.add_column("#", justify="right", style="cyan", width=4)
        table.add_column("Size", justify="right", style="yellow")
        table.add_column("Visual", width=32)
        table.add_column("Command", style="dim")

        max_layer_size = max((l.size for l in analysis.layers), default=1)

        for idx, layer in enumerate(analysis.layers, 1):
            if layer.size > 0:  # Only show layers with size
                size_bar = create_size_bar(layer.size, max_layer_size)
                table.add_row(
                    str(idx),
                    layer.size_human,
                    size_bar,
                    layer.created_by[:60],
                )

        print_table(table)

        # Show largest layers
        console.print("\n[bold yellow]Largest Layers:[/bold yellow]")
        for idx, layer in enumerate(analysis.largest_layers[:5], 1):
            if layer.size > 0:
                console.print(f"  {idx}. [bold]{layer.size_human}[/bold] - {layer.created_by[:70]}")

    console.print()


def display_comparison(analysis1: ImageAnalysis, analysis2: ImageAnalysis) -> None:
    """
    Display side-by-side comparison of two images.

    Args:
        analysis1: First image analysis
        analysis2: Second image analysis
    """
    console.print(Panel("[bold cyan]Image Comparison[/bold cyan]"))

    # Comparison table
    table = create_table(title=None)
    table.add_column("Metric", style="bold")
    table.add_column(analysis1.name, style="cyan")
    table.add_column(analysis2.name, style="magenta")
    table.add_column("Difference", justify="right")

    # Size comparison
    size_diff = analysis2.size - analysis1.size
    size_diff_pct = (size_diff / analysis1.size * 100) if analysis1.size > 0 else 0
    size_diff_str = f"{'+' if size_diff > 0 else ''}{format_bytes(size_diff)} ({size_diff_pct:+.1f}%)"

    table.add_row(
        "Size",
        analysis1.size_human,
        analysis2.size_human,
        size_diff_str,
    )

    # Layer count comparison
    layer_diff = analysis2.layer_count - analysis1.layer_count
    table.add_row(
        "Layers",
        str(analysis1.layer_count),
        str(analysis2.layer_count),
        f"{layer_diff:+d}",
    )

    table.add_row("Architecture", analysis1.architecture, analysis2.architecture, "-")
    table.add_row("OS", analysis1.os, analysis2.os, "-")

    print_table(table)

    # Summary
    if size_diff < 0:
        success(f"\n✅ {analysis2.name} is {format_bytes(abs(size_diff))} smaller!")
    elif size_diff > 0:
        warning(f"\n⚠️  {analysis2.name} is {format_bytes(size_diff)} larger!")
    else:
        info("\nℹ️  Images are the same size")

    console.print()


def format_bytes(bytes_val: int) -> str:
    """Format bytes into human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024.0:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.2f} PB"


@click.command()
@click.option("--image", "-i", required=True, help="Image name or ID to analyze")
@click.option(
    "--compare",
    "-c",
    help="Second image to compare with",
)
@click.option(
    "--pull",
    is_flag=True,
    help="Pull image if not available locally",
)
@click.option(
    "--layers",
    "-l",
    is_flag=True,
    default=True,
    help="Show layer breakdown (default: true)",
)
@click.option(
    "--suggestions",
    "-s",
    is_flag=True,
    help="Show optimization suggestions",
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["rich", "json"], case_sensitive=False),
    default="rich",
    show_default=True,
    help="Output format",
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@handle_errors
def main(
    image: str,
    compare: Optional[str],
    pull: bool,
    layers: bool,
    suggestions: bool,
    output: str,
    verbose: bool,
):
    """
    Docker Image Analyzer - Analyze Docker images for size optimization.

    Analyze Docker images layer-by-layer to identify optimization
    opportunities and compare different image versions.

    Examples:

        \b
        # Analyze an image
        docker-analyzer --image nginx:latest

        \b
        # Compare two images
        docker-analyzer --image myapp:v1.0 --compare myapp:v2.0

        \b
        # Pull and analyze
        docker-analyzer --image python:3.11-alpine --pull

        \b
        # Show optimization suggestions
        docker-analyzer --image myapp:latest --suggestions

        \b
        # JSON output
        docker-analyzer --image nginx --output json
    """
    # Setup logging
    log_level = "DEBUG" if verbose else "INFO"
    setup_logger(__name__, level=log_level)

    try:
        analyzer = DockerAnalyzer()
    except ConnectionError as e:
        error(str(e))
        error("Make sure Docker is running and you have permission to access it")
        sys.exit(1)

    # Pull image if requested
    if pull:
        info(f"Pulling image: {image}")
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        ) as progress:
            task = progress.add_task(f"Pulling {image}...", total=100)
            success_pull = analyzer.pull_image(image)
            progress.update(task, completed=100)

        if not success_pull:
            error(f"Failed to pull image: {image}")
            sys.exit(1)

        if compare:
            info(f"Pulling comparison image: {compare}")
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            ) as progress:
                task = progress.add_task(f"Pulling {compare}...", total=100)
                success_pull2 = analyzer.pull_image(compare)
                progress.update(task, completed=100)

            if not success_pull2:
                error(f"Failed to pull comparison image: {compare}")
                sys.exit(1)

    # Analyze image(s)
    if compare:
        # Comparison mode
        info(f"Comparing {image} with {compare}")
        analysis1, analysis2 = analyzer.compare_images(image, compare)

        if analysis1.error or analysis2.error:
            if analysis1.error:
                error(f"{image}: {analysis1.error}")
            if analysis2.error:
                error(f"{compare}: {analysis2.error}")
            sys.exit(1)

        if output == "rich":
            display_comparison(analysis1, analysis2)
        else:
            # JSON output
            data = {
                "image1": {
                    "name": analysis1.name,
                    "size": analysis1.size,
                    "size_human": analysis1.size_human,
                    "layers": analysis1.layer_count,
                },
                "image2": {
                    "name": analysis2.name,
                    "size": analysis2.size,
                    "size_human": analysis2.size_human,
                    "layers": analysis2.layer_count,
                },
                "size_diff": analysis2.size - analysis1.size,
                "layer_diff": analysis2.layer_count - analysis1.layer_count,
            }
            print(json.dumps(data, indent=2))

    else:
        # Single image analysis
        info(f"Analyzing image: {image}")
        analysis = analyzer.analyze_image(image)

        if analysis.error:
            error(f"Failed to analyze: {analysis.error}")
            sys.exit(1)

        if output == "rich":
            display_analysis(analysis, show_layers=layers)

            # Show suggestions if requested
            if suggestions:
                suggestions_list = analyzer.get_optimization_suggestions(analysis)
                console.print("[bold yellow]Optimization Suggestions:[/bold yellow]")
                for suggestion in suggestions_list:
                    console.print(f"  {suggestion}")
                console.print()

        else:
            # JSON output
            data = {
                "name": analysis.name,
                "tags": analysis.tags,
                "size": analysis.size,
                "size_human": analysis.size_human,
                "layers": analysis.layer_count,
                "architecture": analysis.architecture,
                "os": analysis.os,
            }

            if suggestions:
                data["suggestions"] = analyzer.get_optimization_suggestions(analysis)

            print(json.dumps(data, indent=2))

    success("Analysis completed!")
    sys.exit(0)


if __name__ == "__main__":
    main()
