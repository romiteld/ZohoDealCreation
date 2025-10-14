"""
Health Check Endpoint with Circuit Breaker Status
Provides comprehensive health monitoring for Teams Bot services
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from datetime import datetime
import logging

# Import circuit breaker health check
from teams_bot.app.services.circuit_breaker import get_circuit_breaker_health

# Import service health checks
from well_shared.cache.redis_manager import get_redis_health_status
from well_shared.database.connection import get_connection_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check() -> Dict[str, Any]:
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "teams-bot"
    }


@router.get("/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """
    Detailed health check including all dependencies
    Returns comprehensive status of all services and circuit breakers
    """
    health_report = {
        "timestamp": datetime.now().isoformat(),
        "service": "teams-bot",
        "overall_status": "healthy",
        "components": {}
    }

    # Check circuit breakers
    try:
        circuit_breaker_health = await get_circuit_breaker_health()
        health_report["components"]["circuit_breakers"] = circuit_breaker_health

        # Update overall status based on circuit breakers
        if circuit_breaker_health["status"] == "degraded":
            health_report["overall_status"] = "degraded"
    except Exception as e:
        logger.error(f"Error checking circuit breakers: {e}")
        health_report["components"]["circuit_breakers"] = {
            "status": "error",
            "error": str(e)
        }
        health_report["overall_status"] = "degraded"

    # Check Redis
    try:
        redis_health = await get_redis_health_status()
        health_report["components"]["redis"] = redis_health

        if redis_health.get("status") != "healthy":
            health_report["overall_status"] = "degraded"
    except Exception as e:
        logger.error(f"Error checking Redis: {e}")
        health_report["components"]["redis"] = {
            "status": "error",
            "error": str(e)
        }
        health_report["overall_status"] = "degraded"

    # Check PostgreSQL
    try:
        db_manager = await get_connection_manager()
        db_health = db_manager.get_health_report()
        health_report["components"]["postgresql"] = {
            "status": "healthy" if db_health["status"]["is_healthy"] else "unhealthy",
            "details": db_health
        }

        if not db_health["status"]["is_healthy"]:
            health_report["overall_status"] = "degraded"
    except Exception as e:
        logger.error(f"Error checking PostgreSQL: {e}")
        health_report["components"]["postgresql"] = {
            "status": "error",
            "error": str(e)
        }
        health_report["overall_status"] = "degraded"

    # Add recommendations if degraded
    if health_report["overall_status"] == "degraded":
        health_report["recommendations"] = _generate_recommendations(health_report["components"])

    return health_report


@router.get("/circuit-breakers")
async def circuit_breaker_status() -> Dict[str, Any]:
    """
    Get detailed circuit breaker status
    Returns state of all circuit breakers and their metrics
    """
    try:
        return await get_circuit_breaker_health()
    except Exception as e:
        logger.error(f"Error getting circuit breaker status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get circuit breaker status: {str(e)}")


@router.get("/dependencies")
async def dependency_health() -> Dict[str, Any]:
    """
    Check health of all external dependencies
    Returns status of Redis, PostgreSQL, Zoho API, etc.
    """
    dependencies = {
        "timestamp": datetime.now().isoformat(),
        "dependencies": {}
    }

    # Redis
    try:
        redis_status = await get_redis_health_status()
        dependencies["dependencies"]["redis"] = {
            "available": redis_status.get("connection_status") == "connected",
            "details": redis_status
        }
    except Exception as e:
        dependencies["dependencies"]["redis"] = {
            "available": False,
            "error": str(e)
        }

    # PostgreSQL
    try:
        db_manager = await get_connection_manager()
        db_health = db_manager.get_health_status()
        dependencies["dependencies"]["postgresql"] = {
            "available": db_health.is_healthy,
            "details": db_health.to_dict()
        }
    except Exception as e:
        dependencies["dependencies"]["postgresql"] = {
            "available": False,
            "error": str(e)
        }

    # Zoho API (check circuit breaker state instead of making actual call)
    from teams_bot.app.services.circuit_breaker import get_breaker_status
    zoho_breaker = get_breaker_status("zoho_api_breaker")
    dependencies["dependencies"]["zoho_api"] = {
        "available": zoho_breaker["state"] != "open",
        "circuit_breaker": zoho_breaker
    }

    # Apollo API
    apollo_breaker = get_breaker_status("apollo_api_breaker")
    dependencies["dependencies"]["apollo_api"] = {
        "available": apollo_breaker["state"] != "open",
        "circuit_breaker": apollo_breaker
    }

    # Firecrawl API
    firecrawl_breaker = get_breaker_status("firecrawl_api_breaker")
    dependencies["dependencies"]["firecrawl_api"] = {
        "available": firecrawl_breaker["state"] != "open",
        "circuit_breaker": firecrawl_breaker
    }

    # Calculate overall availability
    total_deps = len(dependencies["dependencies"])
    available_deps = sum(1 for dep in dependencies["dependencies"].values() if dep.get("available"))
    dependencies["availability_percentage"] = (available_deps / total_deps * 100) if total_deps > 0 else 0

    return dependencies


@router.post("/circuit-breakers/reset")
async def reset_circuit_breakers(breaker_name: str = None) -> Dict[str, str]:
    """
    Reset circuit breakers (admin function)

    Args:
        breaker_name: Optional specific breaker to reset, or reset all if not provided
    """
    from teams_bot.app.services.circuit_breaker import reset_all_breakers, reset_breaker

    try:
        if breaker_name:
            success = reset_breaker(breaker_name)
            if success:
                return {"status": "success", "message": f"Circuit breaker '{breaker_name}' reset"}
            else:
                raise HTTPException(status_code=404, detail=f"Unknown breaker: {breaker_name}")
        else:
            reset_all_breakers()
            return {"status": "success", "message": "All circuit breakers reset"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting circuit breakers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset circuit breakers: {str(e)}")


def _generate_recommendations(components: Dict[str, Any]) -> list:
    """Generate health recommendations based on component status"""
    recommendations = []

    # Check circuit breakers
    if "circuit_breakers" in components:
        cb = components["circuit_breakers"]
        if cb.get("status") == "degraded":
            if "recommendations" in cb:
                recommendations.extend(cb["recommendations"])

    # Check Redis
    if "redis" in components:
        redis = components["redis"]
        if redis.get("status") != "healthy":
            if redis.get("fallback_mode"):
                recommendations.append("Redis in fallback mode - investigate connection issues")
            elif redis.get("circuit_breaker_open"):
                recommendations.append("Redis circuit breaker open - check Redis server health")

    # Check PostgreSQL
    if "postgresql" in components:
        pg = components["postgresql"]
        if pg.get("status") != "healthy":
            if "details" in pg and "status" in pg["details"]:
                if pg["details"]["status"].get("last_error"):
                    recommendations.append(f"PostgreSQL error: {pg['details']['status']['last_error']}")
            else:
                recommendations.append("PostgreSQL unhealthy - check database connectivity")

    # General recommendations
    if len(recommendations) == 0 and any(
        comp.get("status") not in ["healthy", "closed"]
        for comp in components.values()
        if isinstance(comp, dict)
    ):
        recommendations.append("Some services are degraded - monitor closely")

    return recommendations


# Export router
__all__ = ['router']