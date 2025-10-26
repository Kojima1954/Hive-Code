"""Health check module with system metrics."""

import asyncio
import logging
from typing import Dict, Any
from datetime import datetime

import psutil
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class HealthChecker:
    """Health checker for system and service status."""

    def __init__(self, redis_client: redis.Redis = None):
        """
        Initialize health checker.

        Args:
            redis_client: Optional Redis client for connectivity checks
        """
        self.redis_client = redis_client
        self.start_time = datetime.utcnow()

    async def check_redis(self) -> Dict[str, Any]:
        """
        Check Redis connectivity and health.

        Returns:
            dict: Redis health status
        """
        if not self.redis_client:
            return {"status": "disabled", "message": "Redis client not configured"}

        try:
            await asyncio.wait_for(self.redis_client.ping(), timeout=2.0)
            info = await self.redis_client.info()
            
            return {
                "status": "healthy",
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "uptime_seconds": info.get("uptime_in_seconds", 0),
            }
        except asyncio.TimeoutError:
            logger.error("Redis health check timed out")
            return {"status": "unhealthy", "message": "Connection timeout"}
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {"status": "unhealthy", "message": str(e)}

    def check_system_metrics(self) -> Dict[str, Any]:
        """
        Get system resource metrics.

        Returns:
            dict: System metrics
        """
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "cpu_percent": cpu_percent,
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                    "used": memory.used,
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": disk.percent,
                },
            }
        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            return {"error": str(e)}

    def check_uptime(self) -> Dict[str, Any]:
        """
        Get application uptime.

        Returns:
            dict: Uptime information
        """
        now = datetime.utcnow()
        uptime = now - self.start_time
        
        return {
            "start_time": self.start_time.isoformat(),
            "current_time": now.isoformat(),
            "uptime_seconds": int(uptime.total_seconds()),
            "uptime_human": str(uptime),
        }

    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get complete health status.

        Returns:
            dict: Complete health status
        """
        health = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": self.check_uptime(),
            "system": self.check_system_metrics(),
        }

        # Check Redis if configured
        if self.redis_client:
            redis_health = await self.check_redis()
            health["redis"] = redis_health
            
            # Mark overall status as unhealthy if Redis is down
            if redis_health["status"] != "healthy":
                health["status"] = "degraded"

        # Check system thresholds
        system = health["system"]
        if not isinstance(system, dict) or "error" in system:
            health["status"] = "unhealthy"
        elif "memory" in system and system["memory"]["percent"] > 90:
            health["status"] = "degraded"
            health["warnings"] = health.get("warnings", [])
            health["warnings"].append("High memory usage")
        elif "cpu_percent" in system and system["cpu_percent"] > 90:
            health["status"] = "degraded"
            health["warnings"] = health.get("warnings", [])
            health["warnings"].append("High CPU usage")
        elif "disk" in system and system["disk"]["percent"] > 90:
            health["status"] = "degraded"
            health["warnings"] = health.get("warnings", [])
            health["warnings"].append("High disk usage")

        return health

    async def is_healthy(self) -> bool:
        """
        Simple boolean health check.

        Returns:
            bool: True if healthy, False otherwise
        """
        status = await self.get_health_status()
        return status["status"] in ["healthy", "degraded"]
