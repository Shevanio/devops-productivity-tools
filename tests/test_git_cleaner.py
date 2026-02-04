"""Tests for Git Branch Cleaner."""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import git
import pytest

from tools.git_cleaner.cleaner import PROTECTED_BRANCHES, BranchInfo, GitBranchCleaner


class TestBranchInfo:
    """Test BranchInfo dataclass."""

    def test_branch_info_creation(self):
        """Test creating a BranchInfo."""
        dt = datetime.now()
        info = BranchInfo(
            name="feature/test",
            last_commit_date=dt,
            author="John Doe",
            is_merged=True,
        )
        assert info.name == "feature/test"
        assert info.last_commit_date == dt
        assert info.author == "John Doe"
        assert info.is_merged is True
        assert info.is_remote is False

    def test_branch_info_remote(self):
        """Test BranchInfo for remote branch."""
        dt = datetime.now()
        info = BranchInfo(
            name="origin/feature/test",
            last_commit_date=dt,
            author="Jane Doe",
            is_merged=True,
            is_remote=True,
        )
        assert info.is_remote is True


class TestGitBranchCleaner:
    """Test GitBranchCleaner functionality."""

    def test_init_with_invalid_repo(self):
        """Test that invalid repository path raises ValueError."""
        with patch("git.Repo", side_effect=git.exc.InvalidGitRepositoryError):
            with pytest.raises(ValueError, match="Not a git repository"):
                GitBranchCleaner(repo_path=Path("/invalid/path"))

    def test_init_with_valid_repo(self):
        """Test initialization with valid repository."""
        mock_repo = MagicMock()

        with patch("git.Repo", return_value=mock_repo):
            cleaner = GitBranchCleaner(repo_path=Path("/valid/repo"))
            assert cleaner.repo == mock_repo
            assert cleaner.protected_branches == PROTECTED_BRANCHES

    def test_init_with_additional_protected(self):
        """Test initialization with additional protected branches."""
        mock_repo = MagicMock()

        with patch("git.Repo", return_value=mock_repo):
            cleaner = GitBranchCleaner(
                repo_path=Path("/valid/repo"),
                additional_protected=["staging", "hotfix"],
            )
            assert "staging" in cleaner.protected_branches
            assert "hotfix" in cleaner.protected_branches
            assert "main" in cleaner.protected_branches  # Still has defaults

    def test_get_current_branch(self):
        """Test getting current active branch."""
        mock_repo = MagicMock()
        mock_repo.active_branch.name = "feature/current"

        with patch("git.Repo", return_value=mock_repo):
            cleaner = GitBranchCleaner()
            assert cleaner.get_current_branch() == "feature/current"

    def test_protected_branches_contains_expected(self):
        """Test that protected branches include expected values."""
        assert "main" in PROTECTED_BRANCHES
        assert "master" in PROTECTED_BRANCHES
        assert "develop" in PROTECTED_BRANCHES
        assert "staging" in PROTECTED_BRANCHES
        assert "production" in PROTECTED_BRANCHES

    def test_filter_by_age(self):
        """Test filtering branches by age."""
        mock_repo = MagicMock()

        with patch("git.Repo", return_value=mock_repo):
            cleaner = GitBranchCleaner()

        now = datetime.now()
        old_branch = BranchInfo(
            name="old-feature",
            last_commit_date=now - timedelta(days=100),
            author="John",
            is_merged=True,
        )
        recent_branch = BranchInfo(
            name="recent-feature",
            last_commit_date=now - timedelta(days=10),
            author="Jane",
            is_merged=True,
        )

        branches = [old_branch, recent_branch]
        filtered = cleaner.filter_by_age(branches, older_than_days=60)

        assert len(filtered) == 1
        assert filtered[0].name == "old-feature"

    def test_filter_by_author(self):
        """Test filtering branches by author."""
        mock_repo = MagicMock()

        with patch("git.Repo", return_value=mock_repo):
            cleaner = GitBranchCleaner()

        now = datetime.now()
        john_branch = BranchInfo(
            name="feature-1",
            last_commit_date=now,
            author="John Doe",
            is_merged=True,
        )
        jane_branch = BranchInfo(
            name="feature-2",
            last_commit_date=now,
            author="Jane Smith",
            is_merged=True,
        )

        branches = [john_branch, jane_branch]
        filtered = cleaner.filter_by_author(branches, author="john")

        assert len(filtered) == 1
        assert filtered[0].author == "John Doe"

    def test_filter_by_author_case_insensitive(self):
        """Test that author filtering is case-insensitive."""
        mock_repo = MagicMock()

        with patch("git.Repo", return_value=mock_repo):
            cleaner = GitBranchCleaner()

        now = datetime.now()
        branch = BranchInfo(
            name="feature",
            last_commit_date=now,
            author="JOHN DOE",
            is_merged=True,
        )

        filtered = cleaner.filter_by_author([branch], author="john")
        assert len(filtered) == 1

    def test_delete_branch_protected_raises_error(self):
        """Test that deleting protected branch raises ValueError."""
        mock_repo = MagicMock()

        with patch("git.Repo", return_value=mock_repo):
            cleaner = GitBranchCleaner()

        with pytest.raises(ValueError, match="Cannot delete protected branch"):
            cleaner.delete_branch("main")

    def test_delete_branch_current_raises_error(self):
        """Test that deleting current branch raises ValueError."""
        mock_repo = MagicMock()
        mock_repo.active_branch.name = "feature/current"

        with patch("git.Repo", return_value=mock_repo):
            cleaner = GitBranchCleaner()

        with pytest.raises(ValueError, match="Cannot delete current branch"):
            cleaner.delete_branch("feature/current")

    def test_delete_branch_success(self):
        """Test successful branch deletion."""
        mock_repo = MagicMock()
        mock_repo.active_branch.name = "main"
        mock_repo.delete_head = MagicMock()

        with patch("git.Repo", return_value=mock_repo):
            cleaner = GitBranchCleaner()
            result = cleaner.delete_branch("feature/old")

        assert result is True
        mock_repo.delete_head.assert_called_once_with("feature/old", force=False)

    def test_delete_branch_force(self):
        """Test forced branch deletion."""
        mock_repo = MagicMock()
        mock_repo.active_branch.name = "main"
        mock_repo.delete_head = MagicMock()

        with patch("git.Repo", return_value=mock_repo):
            cleaner = GitBranchCleaner()
            result = cleaner.delete_branch("feature/unmerged", force=True)

        assert result is True
        mock_repo.delete_head.assert_called_once_with("feature/unmerged", force=True)

    def test_delete_branch_failure(self):
        """Test branch deletion failure."""
        mock_repo = MagicMock()
        mock_repo.active_branch.name = "main"
        mock_repo.delete_head = MagicMock(side_effect=Exception("Git error"))

        with patch("git.Repo", return_value=mock_repo):
            cleaner = GitBranchCleaner()
            result = cleaner.delete_branch("feature/broken")

        assert result is False

    def test_create_backup(self, tmp_path):
        """Test creating backup file."""
        mock_repo = MagicMock()

        with patch("git.Repo", return_value=mock_repo):
            cleaner = GitBranchCleaner()

        now = datetime.now()
        branches = [
            BranchInfo(
                name="feature-1",
                last_commit_date=now,
                author="John",
                is_merged=True,
            ),
            BranchInfo(
                name="feature-2",
                last_commit_date=now,
                author="Jane",
                is_merged=True,
            ),
        ]

        backup_path = tmp_path / "backup.json"
        cleaner.create_backup(branches, backup_path)

        assert backup_path.exists()

        import json

        with open(backup_path) as f:
            data = json.load(f)

        assert "timestamp" in data
        assert "repository" in data
        assert "branches" in data
        assert len(data["branches"]) == 2
        assert data["branches"][0]["name"] == "feature-1"
        assert data["branches"][1]["name"] == "feature-2"

    def test_get_merged_branches_excludes_protected(self):
        """Test that get_merged_branches excludes protected branches."""
        mock_repo = MagicMock()
        mock_repo.active_branch.name = "main"

        # Mock branches
        mock_branch_main = Mock()
        mock_branch_main.name = "main"

        mock_branch_feature = Mock()
        mock_branch_feature.name = "feature/test"
        mock_branch_feature.commit.committed_date = datetime.now().timestamp()
        mock_branch_feature.commit.author.name = "John"

        mock_repo.heads = [mock_branch_main, mock_branch_feature]
        mock_repo.is_ancestor.return_value = True

        with patch("git.Repo", return_value=mock_repo):
            cleaner = GitBranchCleaner()
            merged = cleaner.get_merged_branches()

        # Should only return feature branch, not main
        assert len(merged) == 1
        assert merged[0].name == "feature/test"

    def test_get_merged_branches_excludes_current(self):
        """Test that get_merged_branches excludes current branch."""
        mock_repo = MagicMock()
        mock_repo.active_branch.name = "feature/current"

        mock_branch_current = Mock()
        mock_branch_current.name = "feature/current"

        mock_branch_other = Mock()
        mock_branch_other.name = "feature/other"
        mock_branch_other.commit.committed_date = datetime.now().timestamp()
        mock_branch_other.commit.author.name = "John"

        mock_repo.heads = [mock_branch_current, mock_branch_other]
        mock_repo.is_ancestor.return_value = True

        with patch("git.Repo", return_value=mock_repo):
            cleaner = GitBranchCleaner()
            merged = cleaner.get_merged_branches()

        # Should only return other branch, not current
        assert len(merged) == 1
        assert merged[0].name == "feature/other"
