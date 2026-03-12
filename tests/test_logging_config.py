"""Tests for logging configuration."""

import json
import logging
import tempfile
import shutil
import pytest
from pathlib import Path

from core.monitoring.logging_config import JSONFormatter, setup_logging, StructuredLogger


@pytest.fixture
def temp_log_dir():
    """Create a temporary log directory."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


class TestJSONFormatter:
    """Tests for JSONFormatter."""

    @pytest.mark.unit
    def test_format_produces_valid_json(self):
        """Output should be valid JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=10, msg="Test message", args=(), exc_info=None
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["message"] == "Test message"
        assert data["logger"] == "test"
        assert data["line"] == 10

    @pytest.mark.unit
    def test_format_includes_timestamp(self):
        """Output should include an ISO timestamp."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.DEBUG, pathname="test.py",
            lineno=1, msg="hi", args=(), exc_info=None
        )
        data = json.loads(formatter.format(record))
        assert "timestamp" in data

    @pytest.mark.unit
    def test_format_includes_exception(self):
        """Output should include exception info when present."""
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="test.py",
            lineno=1, msg="error occurred", args=(), exc_info=exc_info
        )
        data = json.loads(formatter.format(record))
        assert "exception" in data
        assert "ValueError" in data["exception"]

    @pytest.mark.unit
    def test_format_includes_extra_fields(self):
        """Output should include extra fields when attached to record."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="msg", args=(), exc_info=None
        )
        record.extra_fields = {"user_id": "123", "action": "login"}
        data = json.loads(formatter.format(record))
        assert data["user_id"] == "123"
        assert data["action"] == "login"


class TestSetupLogging:
    """Tests for setup_logging."""

    @pytest.mark.unit
    def test_creates_log_directory(self, temp_log_dir):
        """Should create the log directory."""
        log_dir = Path(temp_log_dir) / "sublogs"
        setup_logging(log_dir=str(log_dir))
        assert log_dir.exists()

    @pytest.mark.unit
    def test_configures_root_logger(self, temp_log_dir):
        """Should configure the root logger with handlers."""
        setup_logging(log_level="DEBUG", log_dir=temp_log_dir)
        root = logging.getLogger()
        assert root.level == logging.DEBUG
        assert len(root.handlers) > 0

    @pytest.mark.unit
    def test_creates_log_files(self, temp_log_dir):
        """Should create JSON and error log files after logging."""
        setup_logging(log_dir=temp_log_dir)
        logger = logging.getLogger("test_setup")
        logger.info("test info message")
        logger.error("test error message")

        log_path = Path(temp_log_dir)
        assert (log_path / "swarm_network.json.log").exists()
        assert (log_path / "errors.log").exists()

    @pytest.mark.unit
    def test_suppresses_noisy_loggers(self, temp_log_dir):
        """Should suppress urllib3, asyncio, and websockets loggers."""
        setup_logging(log_dir=temp_log_dir)
        assert logging.getLogger("urllib3").level == logging.WARNING
        assert logging.getLogger("asyncio").level == logging.WARNING
        assert logging.getLogger("websockets").level == logging.WARNING


class TestStructuredLogger:
    """Tests for StructuredLogger."""

    @pytest.mark.unit
    def test_info_log(self):
        """Should log info messages."""
        slogger = StructuredLogger("test_structured")
        # Should not raise
        slogger.info("Test info message", user_id="123")

    @pytest.mark.unit
    def test_error_log(self):
        """Should log error messages."""
        slogger = StructuredLogger("test_structured")
        slogger.error("Test error", error_code=500)

    @pytest.mark.unit
    def test_debug_log(self):
        """Should log debug messages."""
        slogger = StructuredLogger("test_structured")
        slogger.debug("Debug info", detail="something")

    @pytest.mark.unit
    def test_warning_log(self):
        """Should log warning messages."""
        slogger = StructuredLogger("test_structured")
        slogger.warning("Watch out", severity="medium")

    @pytest.mark.unit
    def test_critical_log(self):
        """Should log critical messages."""
        slogger = StructuredLogger("test_structured")
        slogger.critical("System down", component="database")
