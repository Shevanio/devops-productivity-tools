"""Backup automation with incremental backups, compression, and retention policies."""

import hashlib
import json
import os
import shutil
import subprocess
import tarfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set


class BackupType(Enum):
    """Type of backup to perform."""

    FULL = "full"
    INCREMENTAL = "incremental"


class CompressionType(Enum):
    """Compression algorithm to use."""

    NONE = "none"
    GZIP = "gzip"
    BZIP2 = "bzip2"
    XZ = "xz"


class DestinationType(Enum):
    """Type of backup destination."""

    LOCAL = "local"
    # Future: S3 = "s3", SFTP = "sftp"


@dataclass
class BackupDestination:
    """Configuration for a backup destination."""

    type: DestinationType
    path: Path
    enabled: bool = True


@dataclass
class BackupConfig:
    """Configuration for backup operations."""

    source_path: Path
    destinations: List[BackupDestination]
    compression: CompressionType = CompressionType.GZIP
    retention_days: int = 30
    max_backups: Optional[int] = None
    exclude_patterns: List[str] = field(default_factory=list)
    backup_name_prefix: str = "backup"


@dataclass
class BackupMetadata:
    """Metadata for a backup."""

    timestamp: str
    backup_type: BackupType
    source_path: str
    file_count: int
    total_size: int
    compression: CompressionType
    file_hash: str
    parent_backup: Optional[str] = None


@dataclass
class BackupResult:
    """Result of a backup operation."""

    success: bool
    backup_file: Optional[Path]
    metadata: Optional[BackupMetadata]
    error: Optional[str]
    duration_seconds: float


class BackupAutomator:
    """Handles automated backups with incremental support and retention."""

    def __init__(self, config: BackupConfig):
        """Initialize the backup automator.

        Args:
            config: Backup configuration
        """
        self.config = config
        self._metadata_cache: Dict[str, BackupMetadata] = {}

    def create_backup(
        self, backup_type: BackupType = BackupType.FULL, destination: Optional[Path] = None
    ) -> BackupResult:
        """Create a backup of the configured source.

        Args:
            backup_type: Type of backup (full or incremental)
            destination: Override default destination (optional)

        Returns:
            BackupResult with operation details
        """
        start_time = datetime.now()

        try:
            # Validate source
            if not self.config.source_path.exists():
                return BackupResult(
                    success=False,
                    backup_file=None,
                    metadata=None,
                    error=f"Source path does not exist: {self.config.source_path}",
                    duration_seconds=0.0,
                )

            # Determine destination
            dest = destination or self._get_primary_destination()
            if not dest:
                return BackupResult(
                    success=False,
                    backup_file=None,
                    metadata=None,
                    error="No enabled destination found",
                    duration_seconds=0.0,
                )

            # Create destination directory
            dest.mkdir(parents=True, exist_ok=True)

            # Get files to backup
            files_to_backup = self._get_files_to_backup(backup_type)

            if not files_to_backup:
                return BackupResult(
                    success=False,
                    backup_file=None,
                    metadata=None,
                    error="No files to backup",
                    duration_seconds=0.0,
                )

            # Create backup archive
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{self.config.backup_name_prefix}_{backup_type.value}_{timestamp}"
            backup_file = self._create_archive(dest, backup_filename, files_to_backup)

            # Calculate metadata
            metadata = self._create_metadata(backup_file, backup_type, len(files_to_backup))

            # Save metadata
            self._save_metadata(backup_file, metadata)

            # Apply retention policy
            self._apply_retention_policy(dest)

            duration = (datetime.now() - start_time).total_seconds()

            return BackupResult(
                success=True,
                backup_file=backup_file,
                metadata=metadata,
                error=None,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return BackupResult(
                success=False,
                backup_file=None,
                metadata=None,
                error=str(e),
                duration_seconds=duration,
            )

    def restore_backup(self, backup_file: Path, restore_path: Path) -> bool:
        """Restore a backup to the specified location.

        Args:
            backup_file: Path to backup archive
            restore_path: Path to restore to

        Returns:
            True if successful, False otherwise
        """
        try:
            if not backup_file.exists():
                raise FileNotFoundError(f"Backup file not found: {backup_file}")

            # Create restore directory
            restore_path.mkdir(parents=True, exist_ok=True)

            # Extract archive
            compression_mode = self._get_tar_mode_for_extraction(backup_file)
            with tarfile.open(backup_file, compression_mode) as tar:
                tar.extractall(restore_path)

            return True

        except Exception:
            return False

    def verify_backup(self, backup_file: Path) -> bool:
        """Verify the integrity of a backup.

        Args:
            backup_file: Path to backup archive

        Returns:
            True if backup is valid, False otherwise
        """
        try:
            if not backup_file.exists():
                return False

            # Load metadata
            metadata = self._load_metadata(backup_file)
            if not metadata:
                return False

            # Verify file hash
            calculated_hash = self._calculate_file_hash(backup_file)
            if calculated_hash != metadata.file_hash:
                return False

            # Try to open archive
            compression_mode = self._get_tar_mode_for_extraction(backup_file)
            with tarfile.open(backup_file, compression_mode) as tar:
                # Verify archive can be read
                tar.getmembers()

            return True

        except Exception:
            return False

    def list_backups(self, destination: Optional[Path] = None) -> List[BackupMetadata]:
        """List all backups in the destination.

        Args:
            destination: Destination to list (optional, uses primary if not provided)

        Returns:
            List of backup metadata
        """
        dest = destination or self._get_primary_destination()
        if not dest or not dest.exists():
            return []

        backups = []
        for backup_file in dest.glob(f"{self.config.backup_name_prefix}_*"):
            if backup_file.is_file():
                metadata = self._load_metadata(backup_file)
                if metadata:
                    backups.append(metadata)

        # Sort by timestamp (newest first)
        backups.sort(key=lambda x: x.timestamp, reverse=True)
        return backups

    def _get_primary_destination(self) -> Optional[Path]:
        """Get the primary (first enabled) destination."""
        for dest in self.config.destinations:
            if dest.enabled:
                return dest.path
        return None

    def _get_files_to_backup(self, backup_type: BackupType) -> List[Path]:
        """Get list of files to backup based on type.

        Args:
            backup_type: Type of backup

        Returns:
            List of file paths to backup
        """
        all_files = []

        # Walk the source directory
        for root, dirs, files in os.walk(self.config.source_path):
            # Filter directories based on exclude patterns
            dirs[:] = [
                d for d in dirs if not self._should_exclude(Path(root) / d)
            ]

            for file in files:
                file_path = Path(root) / file
                if not self._should_exclude(file_path):
                    all_files.append(file_path)

        # For incremental, filter files modified since last backup
        if backup_type == BackupType.INCREMENTAL:
            last_backup_time = self._get_last_backup_time()
            if last_backup_time:
                all_files = [
                    f for f in all_files
                    if datetime.fromtimestamp(f.stat().st_mtime) > last_backup_time
                ]

        return all_files

    def _should_exclude(self, path: Path) -> bool:
        """Check if a path should be excluded.

        Args:
            path: Path to check

        Returns:
            True if should be excluded
        """
        for pattern in self.config.exclude_patterns:
            if path.match(pattern):
                return True
        return False

    def _get_last_backup_time(self) -> Optional[datetime]:
        """Get the timestamp of the last backup."""
        dest = self._get_primary_destination()
        if not dest or not dest.exists():
            return None

        backups = self.list_backups(dest)
        if not backups:
            return None

        # Get most recent backup
        last_backup = backups[0]
        return datetime.fromisoformat(last_backup.timestamp)

    def _create_archive(
        self, destination: Path, filename: str, files: List[Path]
    ) -> Path:
        """Create a compressed archive of the files.

        Args:
            destination: Destination directory
            filename: Base filename (without extension)
            files: List of files to archive

        Returns:
            Path to created archive
        """
        # Determine compression mode and extension
        mode, extension = self._get_tar_mode_and_extension()
        archive_path = destination / f"{filename}{extension}"

        # Create archive
        with tarfile.open(archive_path, mode) as tar:
            for file in files:
                # Store relative to source path
                arcname = file.relative_to(self.config.source_path)
                tar.add(file, arcname=arcname)

        return archive_path

    def _get_tar_mode_and_extension(self) -> tuple[str, str]:
        """Get tar mode and file extension for compression type."""
        compression_map = {
            CompressionType.NONE: ("w", ".tar"),
            CompressionType.GZIP: ("w:gz", ".tar.gz"),
            CompressionType.BZIP2: ("w:bz2", ".tar.bz2"),
            CompressionType.XZ: ("w:xz", ".tar.xz"),
        }
        return compression_map.get(
            self.config.compression, ("w:gz", ".tar.gz")
        )

    def _get_tar_mode_for_extraction(self, backup_file: Path) -> str:
        """Get tar mode for extracting a backup file."""
        if backup_file.suffix == ".gz" or backup_file.name.endswith(".tar.gz"):
            return "r:gz"
        elif backup_file.suffix == ".bz2" or backup_file.name.endswith(".tar.bz2"):
            return "r:bz2"
        elif backup_file.suffix == ".xz" or backup_file.name.endswith(".tar.xz"):
            return "r:xz"
        else:
            return "r"

    def _create_metadata(
        self, backup_file: Path, backup_type: BackupType, file_count: int
    ) -> BackupMetadata:
        """Create metadata for a backup.

        Args:
            backup_file: Path to backup archive
            backup_type: Type of backup
            file_count: Number of files in backup

        Returns:
            BackupMetadata instance
        """
        file_hash = self._calculate_file_hash(backup_file)

        return BackupMetadata(
            timestamp=datetime.now().isoformat(),
            backup_type=backup_type,
            source_path=str(self.config.source_path),
            file_count=file_count,
            total_size=backup_file.stat().st_size,
            compression=self.config.compression,
            file_hash=file_hash,
        )

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file.

        Args:
            file_path: Path to file

        Returns:
            Hex digest of file hash
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _save_metadata(self, backup_file: Path, metadata: BackupMetadata) -> None:
        """Save metadata alongside backup file.

        Args:
            backup_file: Path to backup archive
            metadata: Metadata to save
        """
        metadata_file = backup_file.with_suffix(backup_file.suffix + ".meta")
        with open(metadata_file, "w") as f:
            json.dump(
                {
                    "timestamp": metadata.timestamp,
                    "backup_type": metadata.backup_type.value,
                    "source_path": metadata.source_path,
                    "file_count": metadata.file_count,
                    "total_size": metadata.total_size,
                    "compression": metadata.compression.value,
                    "file_hash": metadata.file_hash,
                    "parent_backup": metadata.parent_backup,
                },
                f,
                indent=2,
            )

    def _load_metadata(self, backup_file: Path) -> Optional[BackupMetadata]:
        """Load metadata for a backup file.

        Args:
            backup_file: Path to backup archive

        Returns:
            BackupMetadata if found, None otherwise
        """
        metadata_file = backup_file.with_suffix(backup_file.suffix + ".meta")
        if not metadata_file.exists():
            return None

        try:
            with open(metadata_file, "r") as f:
                data = json.load(f)

            return BackupMetadata(
                timestamp=data["timestamp"],
                backup_type=BackupType(data["backup_type"]),
                source_path=data["source_path"],
                file_count=data["file_count"],
                total_size=data["total_size"],
                compression=CompressionType(data["compression"]),
                file_hash=data["file_hash"],
                parent_backup=data.get("parent_backup"),
            )
        except Exception:
            return None

    def _apply_retention_policy(self, destination: Path) -> None:
        """Apply retention policy to remove old backups.

        Args:
            destination: Destination directory
        """
        backups = self.list_backups(destination)

        # Filter by retention days
        cutoff_date = datetime.now() - timedelta(days=self.config.retention_days)
        backups_to_remove = [
            b
            for b in backups
            if datetime.fromisoformat(b.timestamp) < cutoff_date
        ]

        # Filter by max backups count
        if self.config.max_backups and len(backups) > self.config.max_backups:
            # Keep the newest max_backups
            backups_sorted = sorted(backups, key=lambda x: x.timestamp, reverse=True)
            backups_to_remove.extend(backups_sorted[self.config.max_backups :])

        # Remove old backups
        for backup_meta in backups_to_remove:
            self._remove_backup(destination, backup_meta)

    def _remove_backup(self, destination: Path, metadata: BackupMetadata) -> None:
        """Remove a backup and its metadata.

        Args:
            destination: Destination directory
            metadata: Metadata of backup to remove
        """
        # Find backup file by timestamp
        for backup_file in destination.glob(f"{self.config.backup_name_prefix}_*"):
            if backup_file.is_file():
                file_metadata = self._load_metadata(backup_file)
                if file_metadata and file_metadata.timestamp == metadata.timestamp:
                    # Remove backup file
                    backup_file.unlink()
                    # Remove metadata file
                    metadata_file = backup_file.with_suffix(backup_file.suffix + ".meta")
                    if metadata_file.exists():
                        metadata_file.unlink()
                    break
