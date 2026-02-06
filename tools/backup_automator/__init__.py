"""Backup Automator - Automated incremental backups with compression and retention policies."""

from .automator import BackupAutomator, BackupConfig, BackupDestination

__all__ = ["BackupAutomator", "BackupConfig", "BackupDestination"]
