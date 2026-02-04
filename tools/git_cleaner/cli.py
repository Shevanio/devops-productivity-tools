"""CLI interface for Git Branch Cleaner."""

import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import click

from shared.cli import confirm, create_table, error, handle_errors, info, print_table, success, warning
from shared.logger import setup_logger

from .cleaner import BranchInfo, GitBranchCleaner


def format_time_ago(dt: datetime) -> str:
    """
    Format datetime as relative time ago.

    Args:
        dt: Datetime to format

    Returns:
        Human-readable time ago string
    """
    now = datetime.now()
    diff = now - dt

    if diff.days > 365:
        years = diff.days // 365
        return f"{years} year{'s' if years != 1 else ''} ago"
    elif diff.days > 30:
        months = diff.days // 30
        return f"{months} month{'s' if months != 1 else ''} ago"
    elif diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "just now"


def display_branches(branches: List[BranchInfo], title: str = "Merged Branches") -> None:
    """
    Display branches in a table.

    Args:
        branches: List of BranchInfo to display
        title: Table title
    """
    if not branches:
        info("No branches found")
        return

    table = create_table(title=title)
    table.add_column("Branch", style="cyan")
    table.add_column("Last Commit", style="yellow")
    table.add_column("Author", style="dim")
    table.add_column("Type", style="magenta")

    for branch in branches:
        time_ago = format_time_ago(branch.last_commit_date)
        branch_type = "remote" if branch.is_remote else "local"

        table.add_row(
            branch.name,
            time_ago,
            branch.author,
            branch_type,
        )

    print_table(table)


@click.command()
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Path to git repository (defaults to current directory)",
)
@click.option(
    "--base-branch",
    "-b",
    help="Base branch to check merges against (defaults to current branch)",
)
@click.option(
    "--older-than",
    type=int,
    help="Only show branches older than N days",
)
@click.option(
    "--author",
    help="Filter by author name (partial match)",
)
@click.option(
    "--remote",
    is_flag=True,
    help="Include remote branches",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be deleted without actually deleting",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Skip confirmation prompts",
)
@click.option(
    "--backup",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Create backup file before deletion",
)
@click.option(
    "--protected",
    multiple=True,
    help="Additional branches to protect from deletion (can be specified multiple times)",
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@handle_errors
def main(
    path: Optional[Path],
    base_branch: Optional[str],
    older_than: Optional[int],
    author: Optional[str],
    remote: bool,
    dry_run: bool,
    force: bool,
    backup: Optional[Path],
    protected: tuple,
    verbose: bool,
):
    """
    Git Branch Cleaner - Clean up merged branches automatically.

    By default, this tool will:
    - Find all merged local branches
    - Exclude protected branches (main, master, develop, etc.)
    - Ask for confirmation before deletion
    - Create a backup if requested

    Examples:

        \b
        # Interactive cleanup of merged branches
        git-cleaner

        \b
        # Dry run to see what would be deleted
        git-cleaner --dry-run

        \b
        # Delete branches older than 60 days
        git-cleaner --older-than 60

        \b
        # Include remote branches
        git-cleaner --remote --dry-run

        \b
        # Filter by author
        git-cleaner --author "john" --dry-run

        \b
        # Protect additional branches
        git-cleaner --protected staging --protected hotfix
    """
    # Setup logging
    log_level = "DEBUG" if verbose else "INFO"
    setup_logger(__name__, level=log_level)

    # Initialize cleaner
    try:
        cleaner = GitBranchCleaner(repo_path=path, additional_protected=list(protected))
        current_branch = cleaner.get_current_branch()
        info(f"Repository: {cleaner.repo_path}")
        info(f"Current branch: {current_branch}")
    except ValueError as e:
        error(str(e))
        sys.exit(1)

    # Get merged branches
    info(f"Finding merged branches (base: {base_branch or current_branch})...")
    branches = cleaner.get_merged_branches(base_branch=base_branch, include_remote=remote)

    if not branches:
        success("No merged branches found. Repository is clean!")
        sys.exit(0)

    # Apply filters
    if older_than:
        branches = cleaner.filter_by_age(branches, older_than_days=older_than)
        info(f"Filtered to branches older than {older_than} days")

    if author:
        branches = cleaner.filter_by_author(branches, author=author)
        info(f"Filtered to branches by author: {author}")

    if not branches:
        info("No branches match the specified filters")
        sys.exit(0)

    # Display branches
    title = "Branches to Delete" if not dry_run else "Branches (Dry Run)"
    display_branches(branches, title=title)

    # Dry run exit
    if dry_run:
        info(f"Dry run complete. {len(branches)} branch(es) would be deleted")
        sys.exit(0)

    # Create backup if requested
    if backup:
        cleaner.create_backup(branches, backup)
        success(f"Backup created: {backup}")

    # Confirmation
    if not force:
        warning(f"About to delete {len(branches)} branch(es)")
        if not confirm("Do you want to proceed?", default=False):
            info("Operation cancelled")
            sys.exit(0)

    # Delete branches
    deleted_count = 0
    failed_count = 0

    for branch in branches:
        if branch.is_remote:
            success_flag = cleaner.delete_remote_branch(branch.name)
        else:
            success_flag = cleaner.delete_branch(branch.name)

        if success_flag:
            deleted_count += 1
            success(f"Deleted: {branch.name}")
        else:
            failed_count += 1
            error(f"Failed to delete: {branch.name}")

    # Summary
    info(f"\nSummary:")
    info(f"  Deleted: {deleted_count}")
    if failed_count > 0:
        warning(f"  Failed: {failed_count}")

    if deleted_count > 0:
        success("Branch cleanup completed!")
    else:
        error("No branches were deleted")
        sys.exit(1)


if __name__ == "__main__":
    main()
