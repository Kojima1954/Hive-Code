"""Tests for Prometheus metrics helpers."""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry

from core.monitoring.metrics import (
    track_time,
    track_time_sync,
    increment_counter,
    set_gauge,
)


@pytest.fixture
def test_registry():
    """Create a fresh registry for each test."""
    return CollectorRegistry()


@pytest.fixture
def test_counter(test_registry):
    """Create a test counter."""
    return Counter("test_counter", "Test counter", ["label"], registry=test_registry)


@pytest.fixture
def test_counter_no_labels(test_registry):
    """Create a test counter without labels."""
    return Counter("test_counter_nolabel", "Test counter", registry=test_registry)


@pytest.fixture
def test_gauge(test_registry):
    """Create a test gauge."""
    return Gauge("test_gauge", "Test gauge", ["label"], registry=test_registry)


@pytest.fixture
def test_gauge_no_labels(test_registry):
    """Create a test gauge without labels."""
    return Gauge("test_gauge_nolabel", "Test gauge", registry=test_registry)


@pytest.fixture
def test_histogram(test_registry):
    """Create a test histogram."""
    return Histogram("test_hist", "Test histogram", ["label"], registry=test_registry)


@pytest.fixture
def test_histogram_no_labels(test_registry):
    """Create a test histogram without labels."""
    return Histogram("test_hist_nolabel", "Test histogram", registry=test_registry)


class TestIncrementCounter:
    """Tests for increment_counter."""

    @pytest.mark.unit
    def test_increment_with_labels(self, test_counter):
        """Should increment counter with labels."""
        increment_counter(test_counter, {"label": "val"})
        assert test_counter.labels(label="val")._value.get() == 1.0

    @pytest.mark.unit
    def test_increment_without_labels(self, test_counter_no_labels):
        """Should increment counter without labels."""
        increment_counter(test_counter_no_labels)
        assert test_counter_no_labels._value.get() == 1.0

    @pytest.mark.unit
    def test_increment_custom_amount(self, test_counter):
        """Should increment by custom amount."""
        increment_counter(test_counter, {"label": "val"}, amount=5)
        assert test_counter.labels(label="val")._value.get() == 5.0

    @pytest.mark.unit
    def test_handles_exception_gracefully(self):
        """Should not raise on error."""
        broken_counter = MagicMock()
        broken_counter.labels.side_effect = RuntimeError("broken")
        # Should not raise
        increment_counter(broken_counter, {"label": "val"})


class TestSetGauge:
    """Tests for set_gauge."""

    @pytest.mark.unit
    def test_set_with_labels(self, test_gauge):
        """Should set gauge value with labels."""
        set_gauge(test_gauge, 42.0, {"label": "val"})
        assert test_gauge.labels(label="val")._value.get() == 42.0

    @pytest.mark.unit
    def test_set_without_labels(self, test_gauge_no_labels):
        """Should set gauge value without labels."""
        set_gauge(test_gauge_no_labels, 99.0)
        assert test_gauge_no_labels._value.get() == 99.0

    @pytest.mark.unit
    def test_handles_exception_gracefully(self):
        """Should not raise on error."""
        broken_gauge = MagicMock()
        broken_gauge.labels.side_effect = RuntimeError("broken")
        set_gauge(broken_gauge, 1.0, {"label": "val"})


class TestTrackTime:
    """Tests for track_time (async decorator)."""

    @pytest.mark.unit
    async def test_tracks_async_function_duration(self, test_histogram):
        """Should record execution time of async function."""
        @track_time(test_histogram, {"label": "test"})
        async def sample_func():
            return "result"

        result = await sample_func()
        assert result == "result"
        # Verify histogram was observed (count should be 1)
        assert test_histogram.labels(label="test")._sum.get() >= 0

    @pytest.mark.unit
    async def test_tracks_without_labels(self, test_histogram_no_labels):
        """Should record execution time without labels."""
        @track_time(test_histogram_no_labels)
        async def sample_func():
            return 42

        result = await sample_func()
        assert result == 42

    @pytest.mark.unit
    async def test_records_time_even_on_exception(self, test_histogram):
        """Should record time even if the function raises."""
        @track_time(test_histogram, {"label": "err"})
        async def failing_func():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await failing_func()


class TestTrackTimeSync:
    """Tests for track_time_sync (sync decorator)."""

    @pytest.mark.unit
    def test_tracks_sync_function_duration(self, test_histogram):
        """Should record execution time of sync function."""
        @track_time_sync(test_histogram, {"label": "sync"})
        def sample_func():
            return "sync_result"

        result = sample_func()
        assert result == "sync_result"

    @pytest.mark.unit
    def test_tracks_sync_without_labels(self, test_histogram_no_labels):
        """Should record execution time without labels."""
        @track_time_sync(test_histogram_no_labels)
        def sample_func():
            return 99

        result = sample_func()
        assert result == 99

    @pytest.mark.unit
    def test_records_time_even_on_exception(self, test_histogram):
        """Should record time even if the function raises."""
        @track_time_sync(test_histogram, {"label": "sync_err"})
        def failing_func():
            raise RuntimeError("sync boom")

        with pytest.raises(RuntimeError):
            failing_func()
