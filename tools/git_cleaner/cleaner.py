"""Core git branch cleaning logic."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import git
from git import Repo

from shared.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BranchInfo:
    """Information about a git branch."""

    name: str
    last_commit_date: datetime
    author: str
    is_merged: bool
    is_remote: bool = False


# Protected branches that should never be deleted
PROTECTED_BRANCHES = {"main", "master", "develop", "development", "staging", "production"}


class GitBranchCleaner:
    """
    Git branch cleaner with safety checks.

    Attributes:
        repo_path: Path to git repository
        protected_branches: Set of branch names to protect from deletion
    """

    def __init__(
        self, repo_path: Optional[Path] = None, additional_protected: Optional[List[str]] = None
    ):
        """
        Initialize git branch cleaner.

        Args:
            repo_path: Path to git repository (defaults to current directory)
            additional_protected: Additional branch names to protect
        """
        self.repo_path = repo_path or Path.cwd()
        self.repo = self._load_repo()

        self.protected_branches = PROTECTED_BRANCHES.copy()
        if additional_protected:
            self.protected_branches.update(additional_protected)

    def _load_repo(self) -> Repo:
        """
        Load git repository.

        Returns:
            Git Repo object

        Raises:
            ValueError: If path is not a git repository
        """
        try:
            repo = Repo(self.repo_path)
            logger.debug(f"Loaded git repository from {self.repo_path}")
            return repo
        except git.exc.InvalidGitRepositoryError:
            raise ValueError(f"Not a git repository: {self.repo_path}")

    def get_current_branch(self) -> str:
        """Get name of current active branch."""
        return self.repo.active_branch.name

    def get_merged_branches(
        self, base_branch: Optional[str] = None, include_remote: bool = False
    ) -> List[BranchInfo]:
        """
        Get list of branches that have been merged.

        Args:
            base_branch: Branch to check merges against (defaults to current branch)
            include_remote: Include remote branches

        Returns:
            List of BranchInfo for merged branches
        """
        if base_branch is None:
            base_branch = self.get_current_branch()

        merged_branches = []

        # Local branches
        for branch in self.repo.heads:
            if branch.name in self.protected_branches:
                continue

            if branch.name == base_branch:
                continue

            is_merged = self.repo.is_ancestor(branch.commit, base_branch)

            if is_merged:
                commit = branch.commit
                branch_info = BranchInfo(
                    name=branch.name,
                    last_commit_date=datetime.fromtimestamp(commit.committed_date),
                    author=commit.author.name,
                    is_merged=True,
                    is_remote=False,
                )
                merged_branches.append(branch_info)

        # Remote branches (if requested)
        if include_remote:
            for ref in self.repo.remote().refs:
                branch_name = ref.name.split("/")[-1]  # origin/feature/X -> feature/X

                if branch_name in self.protected_branches:
                    continue

                try:
                    is_merged = self.repo.is_ancestor(ref.commit, base_branch)

                    if is_merged:
                        commit = ref.commit
                        branch_info = BranchInfo(
                            name=f"origin/{branch_name}",
                            last_commit_date=datetime.fromtimestamp(commit.committed_date),
                            author=commit.author.name,
                            is_merged=True,
                            is_remote=True,
                        )
                        merged_branches.append(branch_info)
                except Exception as e:
                    logger.debug(f"Error checking remote branch {ref.name}: {e}")

        merged_branches.sort(key=lambda x: x.last_commit_date, reverse=True)
        return merged_branches

    def filter_by_age(
        self, branches: List[BranchInfo], older_than_days: int
    ) -> List[BranchInfo]:
        """
        Filter branches by age.

        Args:
            branches: List of BranchInfo
            older_than_days: Only include branches older than this many days

        Returns:
            Filtered list of BranchInfo
        """
        cutoff_date = datetime.now() - timedelta(days=older_than_days)
        return [b for b in branches if b.last_commit_date < cutoff_date]

    def filter_by_author(self, branches: List[BranchInfo], author: str) -> List[BranchInfo]:
        """
        Filter branches by author.

        Args:
            branches: List of BranchInfo
            author: Author name (partial match)

        Returns:
            Filtered list of BranchInfo
        """
        author_lower = author.lower()
        return [b for b in branches if author_lower in b.author.lower()]

    def delete_branch(self, branch_name: str, force: bool = False) -> bool:
        """
        Delete a local branch.

        Args:
            branch_name: Name of branch to delete
            force: Force deletion even if not merged

        Returns:
            True if deleted successfully

        Raises:
            ValueError: If trying to delete protected branch
        """
        if branch_name in self.protected_branches:
            raise ValueError(f"Cannot delete protected branch: {branch_name}")

        if branch_name == self.get_current_branch():
            raise ValueError(f"Cannot delete current branch: {branch_name}")

        try:
            self.repo.delete_head(branch_name, force=force)
            logger.info(f"Deleted branch: {branch_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete branch {branch_name}: {e}")
            return False

    def delete_remote_branch(self, branch_name: str) -> bool:
        """
        Delete a remote branch.

        Args:
            branch_name: Name of branch (e.g., "origin/feature/x")

        Returns:
            True if deleted successfully
        """
        try:
            # Parse remote and branch name
            parts = branch_name.split("/", 1)
            if len(parts) != 2:
                raise ValueError(f"Invalid remote branch format: {branch_name}")

            remote_name, remote_branch = parts

            # Delete from remote
            remote = self.repo.remote(remote_name)
            remote.push(refspec=f":{remote_branch}")

            logger.info(f"Deleted remote branch: {branch_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete remote branch {branch_name}: {e}")
            return False

    def create_backup(self, branches: List[BranchInfo], backup_path: Path) -> None:
        """
        Create a backup file with branch information.

        Args:
            branches: List of branches to backup
            backup_path: Path to backup file
        """
        import json

        backup_data = {
            "timestamp": datetime.now().isoformat(),
            "repository": str(self.repo_path),
            "branches": [
                {
                    "name": b.name,
                    "last_commit": b.last_commit_date.isoformat(),
                    "author": b.author,
                    "is_remote": b.is_remote,
                }
                for b in branches
            ],
        }

        with open(backup_path, "w") as f:
            json.dump(backup_data, f, indent=2)

        logger.info(f"Created backup: {backup_path}")
