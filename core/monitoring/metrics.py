"""Prometheus metrics for monitoring."""

import time
import functools
from typing import Callable
import logging

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry

logger = logging.getLogger(__name__)

# Create a custom registry
registry = CollectorRegistry()

# Message metrics
message_counter = Counter(
    'swarm_messages_total',
    'Total number of messages processed',
    ['node_id', 'message_type'],
    registry=registry
)

message_processing_time = Histogram(
    'swarm_message_processing_seconds',
    'Time spent processing messages',
    ['node_id'],
    registry=registry
)

# Participant metrics
active_participants = Gauge(
    'swarm_active_participants',
    'Number of active participants',
    ['node_id', 'participant_type'],
    registry=registry
)

# Memory metrics
memory_size = Gauge(
    'swarm_memory_size_bytes',
    'Size of memory storage in bytes',
    ['node_id'],
    registry=registry
)

memory_entries = Gauge(
    'swarm_memory_entries_total',
    'Total number of memory entries',
    ['node_id'],
    registry=registry
)

# Error metrics
error_counter = Counter(
    'swarm_errors_total',
    'Total number of errors',
    ['node_id', 'error_type'],
    registry=registry
)

# WebSocket metrics
websocket_connections = Gauge(
    'swarm_websocket_connections',
    'Number of active WebSocket connections',
    registry=registry
)

# API metrics
api_requests = Counter(
    'swarm_api_requests_total',
    'Total number of API requests',
    ['method', 'endpoint', 'status'],
    registry=registry
)

api_request_duration = Histogram(
    'swarm_api_request_duration_seconds',
    'API request duration in seconds',
    ['method', 'endpoint'],
    registry=registry
)

# Redis metrics
redis_operations = Counter(
    'swarm_redis_operations_total',
    'Total number of Redis operations',
    ['operation', 'status'],
    registry=registry
)

# Agent metrics
agent_inference_time = Histogram(
    'swarm_agent_inference_seconds',
    'Time spent on AI agent inference',
    ['node_id', 'agent_id'],
    registry=registry
)

agent_tokens = Counter(
    'swarm_agent_tokens_total',
    'Total number of tokens processed by agents',
    ['node_id', 'agent_id', 'token_type'],
    registry=registry
)


def track_time(metric: Histogram, labels: dict = None):
    """
    Decorator to track execution time of async functions.

    Args:
        metric: Prometheus Histogram metric
        labels: Optional labels for the metric

    Returns:
        Decorated function
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                if labels:
                    metric.labels(**labels).observe(duration)
                else:
                    metric.observe(duration)
        return wrapper
    return decorator


def track_time_sync(metric: Histogram, labels: dict = None):
    """
    Decorator to track execution time of synchronous functions.

    Args:
        metric: Prometheus Histogram metric
        labels: Optional labels for the metric

    Returns:
        Decorated function
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                if labels:
                    metric.labels(**labels).observe(duration)
                else:
                    metric.observe(duration)
        return wrapper
    return decorator


def increment_counter(counter: Counter, labels: dict = None, amount: float = 1):
    """
    Helper function to safely increment a counter.

    Args:
        counter: Prometheus Counter metric
        labels: Optional labels for the metric
        amount: Amount to increment by
    """
    try:
        if labels:
            counter.labels(**labels).inc(amount)
        else:
            counter.inc(amount)
    except Exception as e:
        logger.error(f"Failed to increment counter: {e}")


def set_gauge(gauge: Gauge, value: float, labels: dict = None):
    """
    Helper function to safely set a gauge value.

    Args:
        gauge: Prometheus Gauge metric
        value: Value to set
        labels: Optional labels for the metric
    """
    try:
        if labels:
            gauge.labels(**labels).set(value)
        else:
            gauge.set(value)
    except Exception as e:
        logger.error(f"Failed to set gauge: {e}")
