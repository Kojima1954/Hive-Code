"""Logging configuration with structured JSON logging."""

import logging
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs logs in JSON format."""

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Args:
            record: Log record

        Returns:
            str: JSON-formatted log entry
        """
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data, default=str)


def setup_logging(
    log_level: str = "INFO",
    log_dir: str = "logs",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> None:
    """
    Set up application logging with JSON formatting and rotation.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files
        max_bytes: Maximum size of each log file
        backup_count: Number of backup files to keep
    """
    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    root_logger.handlers = []

    # Console handler with simple format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # JSON file handler for all logs
    json_handler = RotatingFileHandler(
        log_path / "swarm_network.json.log",
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    json_handler.setLevel(logging.DEBUG)
    json_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(json_handler)

    # Separate error log file
    error_handler = RotatingFileHandler(
        log_path / "errors.log",
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(error_handler)

    # Performance log file
    perf_handler = RotatingFileHandler(
        log_path / "performance.log",
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    perf_handler.setLevel(logging.INFO)
    perf_handler.setFormatter(JSONFormatter())
    
    # Only performance-related logs
    perf_logger = logging.getLogger("performance")
    perf_logger.addHandler(perf_handler)
    perf_logger.setLevel(logging.INFO)
    perf_logger.propagate = False

    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)

    logging.info(f"Logging initialized at {log_level} level")


class StructuredLogger:
    """Helper class for structured logging with extra fields."""

    def __init__(self, name: str):
        """
        Initialize structured logger.

        Args:
            name: Logger name
        """
        self.logger = logging.getLogger(name)

    def log(self, level: int, message: str, **extra_fields):
        """
        Log with extra structured fields.

        Args:
            level: Logging level
            message: Log message
            **extra_fields: Additional fields to include in log
        """
        extra = {"extra_fields": extra_fields}
        self.logger.log(level, message, extra=extra)

    def debug(self, message: str, **extra_fields):
        """Log debug message with extra fields."""
        self.log(logging.DEBUG, message, **extra_fields)

    def info(self, message: str, **extra_fields):
        """Log info message with extra fields."""
        self.log(logging.INFO, message, **extra_fields)

    def warning(self, message: str, **extra_fields):
        """Log warning message with extra fields."""
        self.log(logging.WARNING, message, **extra_fields)

    def error(self, message: str, **extra_fields):
        """Log error message with extra fields."""
        self.log(logging.ERROR, message, **extra_fields)

    def critical(self, message: str, **extra_fields):
        """Log critical message with extra fields."""
        self.log(logging.CRITICAL, message, **extra_fields)
