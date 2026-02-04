"""Core log parsing logic."""

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Pattern

from shared.logger import get_logger

logger = get_logger(__name__)


class LogFormat(str, Enum):
    """Supported log formats."""

    NGINX = "nginx"
    APACHE = "apache"
    JSON = "json"
    SYSLOG = "syslog"
    PYTHON = "python"
    DOCKER = "docker"
    AUTO = "auto"


class LogLevel(str, Enum):
    """Log severity levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    FATAL = "FATAL"


@dataclass
class LogEntry:
    """Parsed log entry."""

    timestamp: Optional[datetime]
    level: Optional[str]
    message: str
    source: Optional[str] = None
    extra: Dict[str, str] = None
    line_number: int = 0

    def __post_init__(self):
        if self.extra is None:
            self.extra = {}


# Regex patterns for different log formats
PATTERNS: Dict[LogFormat, Pattern] = {
    # Nginx: 127.0.0.1 - - [01/Jan/2024:12:00:00 +0000] "GET / HTTP/1.1" 200 1234
    LogFormat.NGINX: re.compile(
        r'(?P<ip>[\d.]+) - - \[(?P<timestamp>[^\]]+)\] "(?P<method>\w+) (?P<path>[^ ]+) HTTP/[\d.]+" '
        r'(?P<status>\d+) (?P<size>\d+)'
    ),
    # Apache: 127.0.0.1 - - [01/Jan/2024:12:00:00 +0000] "GET / HTTP/1.1" 200 1234
    LogFormat.APACHE: re.compile(
        r'(?P<ip>[\d.]+) - - \[(?P<timestamp>[^\]]+)\] "(?P<method>\w+) (?P<path>[^ ]+) HTTP/[\d.]+" '
        r'(?P<status>\d+) (?P<size>\d+)'
    ),
    # Syslog: Jan 1 12:00:00 hostname service[1234]: message
    LogFormat.SYSLOG: re.compile(
        r'(?P<timestamp>\w+ \d+ \d+:\d+:\d+) (?P<host>\S+) (?P<service>\w+)(\[(?P<pid>\d+)\])?: (?P<message>.*)'
    ),
    # Python: 2024-01-01 12:00:00,123 - module - LEVEL - message
    LogFormat.PYTHON: re.compile(
        r'(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (?P<module>\S+) - (?P<level>\w+) - (?P<message>.*)'
    ),
    # Docker: 2024-01-01T12:00:00.123456789Z [level] message
    LogFormat.DOCKER: re.compile(
        r'(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z) \[(?P<level>\w+)\] (?P<message>.*)'
    ),
}


class LogParser:
    """
    Parse and analyze log files.

    Supports multiple log formats and provides statistics.
    """

    def __init__(self, format: LogFormat = LogFormat.AUTO):
        """
        Initialize log parser.

        Args:
            format: Log format to use (AUTO for auto-detection)
        """
        self.format = format
        self.entries: List[LogEntry] = []
        logger.debug(f"Initialized LogParser with format: {format}")

    def parse_file(
        self,
        filepath: Path,
        encoding: str = "utf-8",
        errors: str = "ignore",
    ) -> List[LogEntry]:
        """
        Parse a log file.

        Args:
            filepath: Path to log file
            encoding: File encoding
            errors: How to handle encoding errors

        Returns:
            List of parsed LogEntry objects
        """
        logger.info(f"Parsing log file: {filepath}")

        if not filepath.exists():
            raise FileNotFoundError(f"Log file not found: {filepath}")

        self.entries = []

        with open(filepath, "r", encoding=encoding, errors=errors) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                entry = self.parse_line(line, line_num)
                if entry:
                    self.entries.append(entry)

        logger.info(f"Parsed {len(self.entries)} log entries")
        return self.entries

    def parse_line(self, line: str, line_number: int = 0) -> Optional[LogEntry]:
        """
        Parse a single log line.

        Args:
            line: Log line string
            line_number: Line number in file

        Returns:
            LogEntry or None if parsing fails
        """
        # JSON format
        if line.startswith("{"):
            try:
                data = json.loads(line)
                return LogEntry(
                    timestamp=self._parse_timestamp(data.get("timestamp") or data.get("time")),
                    level=data.get("level") or data.get("severity"),
                    message=data.get("message") or data.get("msg") or str(data),
                    source=data.get("source") or data.get("logger"),
                    extra=data,
                    line_number=line_number,
                )
            except json.JSONDecodeError:
                pass

        # Try format-specific patterns
        if self.format != LogFormat.AUTO and self.format in PATTERNS:
            match = PATTERNS[self.format].match(line)
            if match:
                return self._create_entry_from_match(match, line, line_number)

        # Auto-detect format
        if self.format == LogFormat.AUTO:
            for fmt, pattern in PATTERNS.items():
                match = pattern.match(line)
                if match:
                    return self._create_entry_from_match(match, line, line_number, fmt)

        # Fallback: create basic entry
        return self._create_fallback_entry(line, line_number)

    def _create_entry_from_match(
        self,
        match: re.Match,
        line: str,
        line_number: int,
        detected_format: Optional[LogFormat] = None,
    ) -> LogEntry:
        """Create LogEntry from regex match."""
        groups = match.groupdict()

        timestamp_str = groups.get("timestamp")
        timestamp = self._parse_timestamp(timestamp_str) if timestamp_str else None

        level = groups.get("level") or self._detect_level(line)
        message = groups.get("message", line)

        # Determine source
        source = groups.get("service") or groups.get("module") or groups.get("host")

        return LogEntry(
            timestamp=timestamp,
            level=level,
            message=message,
            source=source,
            extra=groups,
            line_number=line_number,
        )

    def _create_fallback_entry(self, line: str, line_number: int) -> LogEntry:
        """Create fallback entry when parsing fails."""
        level = self._detect_level(line)
        timestamp = self._extract_timestamp(line)

        return LogEntry(
            timestamp=timestamp,
            level=level,
            message=line,
            line_number=line_number,
        )

    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse timestamp string to datetime."""
        if not timestamp_str:
            return None

        # Try common formats
        formats = [
            "%Y-%m-%d %H:%M:%S,%f",  # Python
            "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO8601
            "%d/%b/%Y:%H:%M:%S %z",  # Nginx/Apache
            "%b %d %H:%M:%S",  # Syslog (no year)
        ]

        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue

        return None

    def _extract_timestamp(self, line: str) -> Optional[datetime]:
        """Try to extract timestamp from line."""
        # Common timestamp patterns
        patterns = [
            r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}",  # ISO format
            r"\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2}",  # Web log format
        ]

        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                return self._parse_timestamp(match.group())

        return None

    def _detect_level(self, line: str) -> Optional[str]:
        """Detect log level from line content."""
        line_upper = line.upper()

        for level in LogLevel:
            if level.value in line_upper:
                return level.value

        # Common aliases
        if "WARN" in line_upper:
            return LogLevel.WARNING.value
        if "ERR" in line_upper:
            return LogLevel.ERROR.value
        if "CRIT" in line_upper or "FATAL" in line_upper:
            return LogLevel.CRITICAL.value

        return None

    def filter_by_level(self, levels: List[str]) -> List[LogEntry]:
        """Filter entries by log level."""
        levels_upper = [l.upper() for l in levels]
        return [e for e in self.entries if e.level and e.level.upper() in levels_upper]

    def filter_by_time_range(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[LogEntry]:
        """Filter entries by time range."""
        filtered = self.entries

        if start:
            filtered = [e for e in filtered if e.timestamp and e.timestamp >= start]

        if end:
            filtered = [e for e in filtered if e.timestamp and e.timestamp <= end]

        return filtered

    def filter_by_pattern(self, pattern: str, case_sensitive: bool = False) -> List[LogEntry]:
        """Filter entries by message pattern."""
        flags = 0 if case_sensitive else re.IGNORECASE
        regex = re.compile(pattern, flags)

        return [e for e in self.entries if regex.search(e.message)]

    def get_statistics(self) -> Dict[str, any]:
        """
        Generate statistics from parsed logs.

        Returns:
            Dictionary with statistics
        """
        total = len(self.entries)

        if total == 0:
            return {"total": 0}

        # Level distribution
        level_counts = Counter(e.level for e in self.entries if e.level)

        # Timeline
        entries_with_time = [e for e in self.entries if e.timestamp]
        if entries_with_time:
            first_timestamp = min(e.timestamp for e in entries_with_time)
            last_timestamp = max(e.timestamp for e in entries_with_time)
            time_span = last_timestamp - first_timestamp
        else:
            first_timestamp = None
            last_timestamp = None
            time_span = None

        # Top errors (if ERROR/CRITICAL)
        error_entries = self.filter_by_level(["ERROR", "CRITICAL", "FATAL"])
        error_messages = Counter(e.message[:100] for e in error_entries)

        # Source distribution
        source_counts = Counter(e.source for e in self.entries if e.source)

        return {
            "total": total,
            "levels": dict(level_counts),
            "first_timestamp": first_timestamp.isoformat() if first_timestamp else None,
            "last_timestamp": last_timestamp.isoformat() if last_timestamp else None,
            "time_span_seconds": time_span.total_seconds() if time_span else None,
            "top_errors": error_messages.most_common(10),
            "sources": dict(source_counts.most_common(10)),
        }

    def get_timeline(self, interval_minutes: int = 60) -> Dict[str, int]:
        """
        Get entry count timeline.

        Args:
            interval_minutes: Time interval in minutes

        Returns:
            Dict of timestamp -> count
        """
        entries_with_time = [e for e in self.entries if e.timestamp]

        if not entries_with_time:
            return {}

        # Group by interval
        timeline = defaultdict(int)

        for entry in entries_with_time:
            # Round down to interval
            minutes_since_epoch = int(entry.timestamp.timestamp() / 60)
            interval_key = (minutes_since_epoch // interval_minutes) * interval_minutes
            timeline[interval_key] += 1

        # Convert keys to datetime strings
        return {
            datetime.fromtimestamp(k * 60).isoformat(): v for k, v in sorted(timeline.items())
        }
