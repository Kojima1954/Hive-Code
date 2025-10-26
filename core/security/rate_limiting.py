"""Rate limiting and DDoS protection module."""

import time
from typing import Optional, Tuple
from datetime import datetime, timedelta
import logging

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis

logger = logging.getLogger(__name__)

# Constants
DEFAULT_BAN_DURATION = 3600  # 1 hour in seconds
VIOLATION_WINDOW = 300  # 5 minutes in seconds
MAX_VIOLATIONS_BEFORE_BAN = 5
DEFAULT_API_RATE_LIMIT = (100, 60)  # (requests, window_seconds)
DEFAULT_WS_RATE_LIMIT = (30, 60)
DEFAULT_METRICS_RATE_LIMIT = (10, 60)


class RateLimiter:
    """Redis-based rate limiter using sliding window algorithm."""

    def __init__(self, redis_client: redis.Redis):
        """
        Initialize rate limiter.

        Args:
            redis_client: Async Redis client
        """
        self.redis = redis_client

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window: int
    ) -> Tuple[bool, int]:
        """
        Check if request exceeds rate limit using sliding window.

        Args:
            key: Unique identifier (e.g., IP address or user ID)
            limit: Maximum number of requests allowed (must be positive)
            window: Time window in seconds (must be positive)

        Returns:
            Tuple of (allowed: bool, remaining: int)
            
        Raises:
            ValueError: If limit or window are not positive integers
        """
        # Validate inputs
        if limit <= 0:
            raise ValueError(f"Rate limit must be positive, got {limit}")
        if window <= 0:
            raise ValueError(f"Time window must be positive, got {window}")
        
        now = time.time()
        window_start = now - window

        try:
            # Remove old entries
            await self.redis.zremrangebyscore(key, 0, window_start)

            # Count requests in current window
            current_count = await self.redis.zcard(key)

            if current_count < limit:
                # Add current request
                await self.redis.zadd(key, {str(now): now})
                await self.redis.expire(key, window)
                return True, limit - current_count - 1
            else:
                return False, 0

        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail open - allow request if Redis is down
            return True, limit


class DDoSProtection:
    """DDoS protection with IP banning and advanced rate limiting."""

    def __init__(self, redis_client: redis.Redis, ban_duration: int = DEFAULT_BAN_DURATION):
        """
        Initialize DDoS protection.

        Args:
            redis_client: Async Redis client
            ban_duration: Duration to ban IPs in seconds (default: 1 hour)
        """
        self.redis = redis_client
        self.ban_duration = ban_duration
        self.rate_limiter = RateLimiter(redis_client)

    async def is_banned(self, ip: str) -> bool:
        """
        Check if IP address is banned.

        Args:
            ip: IP address to check

        Returns:
            bool: True if banned, False otherwise
        """
        try:
            ban_key = f"banned:{ip}"
            banned = await self.redis.get(ban_key)
            return banned is not None
        except Exception as e:
            logger.error(f"Failed to check ban status: {e}")
            return False

    async def ban_ip(self, ip: str, reason: str = "Rate limit exceeded"):
        """
        Ban an IP address.

        Args:
            ip: IP address to ban
            reason: Reason for ban
        """
        try:
            ban_key = f"banned:{ip}"
            await self.redis.setex(ban_key, self.ban_duration, reason)
            logger.warning(f"Banned IP {ip}: {reason}")
        except Exception as e:
            logger.error(f"Failed to ban IP: {e}")

    async def check_request(
        self,
        ip: str,
        endpoint: str,
        limit: int = 100,
        window: int = 60
    ) -> bool:
        """
        Check if request should be allowed.

        Args:
            ip: Client IP address
            endpoint: Request endpoint
            limit: Rate limit
            window: Time window in seconds

        Returns:
            bool: True if allowed, False if blocked
        """
        # Check if IP is banned
        if await self.is_banned(ip):
            logger.warning(f"Blocked request from banned IP: {ip}")
            return False

        # Check rate limit
        key = f"ratelimit:{ip}:{endpoint}"
        allowed, remaining = await self.rate_limiter.check_rate_limit(key, limit, window)

        if not allowed:
            # Ban IP if it exceeds limit multiple times
            violation_key = f"violations:{ip}"
            violations = await self.redis.incr(violation_key)
            await self.redis.expire(violation_key, VIOLATION_WINDOW)  # 5 minutes

            if violations >= MAX_VIOLATIONS_BEFORE_BAN:
                await self.ban_ip(ip, "Multiple rate limit violations")

            logger.warning(f"Rate limit exceeded for {ip} on {endpoint}")
            return False

        return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting."""

    def __init__(self, app, redis_client: redis.Redis, rules: Optional[dict] = None):
        """
        Initialize rate limit middleware.

        Args:
            app: FastAPI application
            redis_client: Async Redis client
            rules: Rate limit rules per endpoint pattern
        """
        super().__init__(app)
        self.ddos_protection = DDoSProtection(redis_client)
        self.rules = rules or {
            "/api/": DEFAULT_API_RATE_LIMIT,      # 100 requests per minute
            "/ws/": DEFAULT_WS_RATE_LIMIT,         # 30 connections per minute
            "/metrics": DEFAULT_METRICS_RATE_LIMIT, # 10 requests per minute
        }

    def get_client_ip(self, request: Request) -> str:
        """
        Extract client IP from request.

        Args:
            request: FastAPI request

        Returns:
            str: Client IP address
        """
        # Check X-Forwarded-For header for proxied requests
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host

    async def dispatch(self, request: Request, call_next):
        """
        Process request with rate limiting.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response
        """
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/healthz"]:
            return await call_next(request)

        ip = self.get_client_ip(request)
        path = request.url.path

        # Find matching rule
        limit, window = 100, 60  # Default
        for pattern, (rule_limit, rule_window) in self.rules.items():
            if path.startswith(pattern):
                limit, window = rule_limit, rule_window
                break

        # Check rate limit
        allowed = await self.ddos_protection.check_request(ip, path, limit, window)

        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later."
            )

        response = await call_next(request)
        return response
