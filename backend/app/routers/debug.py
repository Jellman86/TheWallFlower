"""Debug and diagnostics API for container interaction."""

import asyncio
import os
import platform
import socket
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/debug", tags=["debug"])


class ServiceCheck(BaseModel):
    """Result of a service connectivity check."""
    name: str
    host: str
    port: int
    reachable: bool
    response_time_ms: Optional[float] = None
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class SystemInfo(BaseModel):
    """System and container information."""
    hostname: str
    platform: str
    python_version: str
    working_directory: str
    environment: Dict[str, str]
    timestamp: str


class NetworkInfo(BaseModel):
    """Network diagnostic information."""
    hostname: str
    fqdn: str
    ip_addresses: List[str]
    dns_servers: List[str]
    hosts_entries: Dict[str, str]


class HttpTestResult(BaseModel):
    """Result of an HTTP request test."""
    url: str
    method: str
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    headers: Optional[Dict[str, str]] = None
    body_preview: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# System Information
# =============================================================================

@router.get("/system", response_model=SystemInfo)
async def get_system_info():
    """Get system and container information."""
    # Filter sensitive env vars
    safe_env_keys = [
        "HOSTNAME", "PATH", "PYTHONPATH", "PYTHONUNBUFFERED",
        "DATABASE_URL", "WHISPER_HOST", "WHISPER_PORT",
        "LOG_LEVEL", "WORKERS", "HOME", "LANG", "TZ"
    ]

    env = {k: os.environ.get(k, "") for k in safe_env_keys if os.environ.get(k)}

    return SystemInfo(
        hostname=socket.gethostname(),
        platform=f"{platform.system()} {platform.release()}",
        python_version=sys.version,
        working_directory=os.getcwd(),
        environment=env,
        timestamp=datetime.utcnow().isoformat()
    )


@router.get("/network", response_model=NetworkInfo)
async def get_network_info():
    """Get network diagnostic information."""
    # Get IP addresses
    ip_addresses = []
    try:
        hostname = socket.gethostname()
        ip_addresses = socket.gethostbyname_ex(hostname)[2]
    except Exception:
        pass

    # Get DNS servers from resolv.conf
    dns_servers = []
    try:
        with open("/etc/resolv.conf", "r") as f:
            for line in f:
                if line.startswith("nameserver"):
                    dns_servers.append(line.split()[1])
    except Exception:
        pass

    # Get relevant hosts entries
    hosts_entries = {}
    try:
        with open("/etc/hosts", "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split()
                    if len(parts) >= 2:
                        ip = parts[0]
                        for host in parts[1:]:
                            hosts_entries[host] = ip
    except Exception:
        pass

    return NetworkInfo(
        hostname=socket.gethostname(),
        fqdn=socket.getfqdn(),
        ip_addresses=ip_addresses,
        dns_servers=dns_servers,
        hosts_entries=hosts_entries
    )


# =============================================================================
# Service Connectivity
# =============================================================================

async def check_tcp_port(host: str, port: int, timeout: float = 5.0) -> tuple[bool, float, Optional[str]]:
    """Check if a TCP port is reachable."""
    start = asyncio.get_event_loop().time()
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        elapsed = (asyncio.get_event_loop().time() - start) * 1000
        return True, elapsed, None
    except asyncio.TimeoutError:
        elapsed = (asyncio.get_event_loop().time() - start) * 1000
        return False, elapsed, "Connection timeout"
    except Exception as e:
        elapsed = (asyncio.get_event_loop().time() - start) * 1000
        return False, elapsed, str(e)


@router.get("/services", response_model=List[ServiceCheck])
async def check_services():
    """Check connectivity to all known services."""
    services = [
        ("whisper-live", os.environ.get("WHISPER_HOST", "whisper-live"),
         int(os.environ.get("WHISPER_PORT", "9090"))),
    ]

    # Common services to check
    common_services = [
        ("TheWallflower Backend", "localhost", 8953),
        ("WhisperLive", os.environ.get("WHISPER_HOST", "whisper-live"), int(os.environ.get("WHISPER_PORT", "9090"))),
    ]

    results = []
    for name, host, port in services + common_services:
        reachable, response_time, error = await check_tcp_port(host, port)
        results.append(ServiceCheck(
            name=name,
            host=host,
            port=port,
            reachable=reachable,
            response_time=response_time,
            error=error
        ))

    return results


@router.get("/check/{host}/{port}", response_model=ServiceCheck)
async def check_service(host: str, port: int):
    """Check connectivity to a specific host:port."""
    reachable, response_time, error = await check_tcp_port(host, port)
    return ServiceCheck(
        name=f"{host}:{port}",
        host=host,
        port=port,
        reachable=reachable,
        response_time_ms=round(response_time, 2),
        error=error
    )


@router.get("/resolve/{hostname}")
async def resolve_hostname(hostname: str):
    """Resolve a hostname to IP addresses."""
    try:
        results = socket.getaddrinfo(hostname, None)
        ips = list(set(r[4][0] for r in results))
        return {
            "hostname": hostname,
            "resolved": True,
            "ip_addresses": ips
        }
    except socket.gaierror as e:
        return {
            "hostname": hostname,
            "resolved": False,
            "error": str(e)
        }


# =============================================================================
# HTTP Testing
# =============================================================================

@router.get("/http", response_model=HttpTestResult)
async def test_http_endpoint(
    url: str = Query(..., description="URL to test"),
    method: str = Query("GET", description="HTTP method"),
    timeout: float = Query(10.0, description="Timeout in seconds")
):
    """Test an HTTP endpoint and return the response details."""
    start = asyncio.get_event_loop().time()

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(method, url)
            elapsed = (asyncio.get_event_loop().time() - start) * 1000

            # Get body preview (first 500 chars)
            body = response.text[:500] if response.text else None

            return HttpTestResult(
                url=url,
                method=method,
                status_code=response.status_code,
                response_time_ms=round(elapsed, 2),
                headers=dict(response.headers),
                body_preview=body
            )
    except Exception as e:
        elapsed = (asyncio.get_event_loop().time() - start) * 1000
        return HttpTestResult(
            url=url,
            method=method,
            response_time_ms=round(elapsed, 2),
            error=str(e)
        )


@router.post("/http", response_model=HttpTestResult)
async def test_http_post(
    url: str = Query(..., description="URL to test"),
    timeout: float = Query(10.0, description="Timeout in seconds"),
    body: Optional[Dict[str, Any]] = None
):
    """Test an HTTP POST endpoint."""
    start = asyncio.get_event_loop().time()

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=body)
            elapsed = (asyncio.get_event_loop().time() - start) * 1000

            return HttpTestResult(
                url=url,
                method="POST",
                status_code=response.status_code,
                response_time_ms=round(elapsed, 2),
                headers=dict(response.headers),
                body_preview=response.text[:500] if response.text else None
            )
    except Exception as e:
        elapsed = (asyncio.get_event_loop().time() - start) * 1000
        return HttpTestResult(
            url=url,
            method="POST",
            response_time_ms=round(elapsed, 2),
            error=str(e)
        )


# =============================================================================
# YA-WAMF Integration
# =============================================================================

@router.get("/yawamf/status")
async def get_yawamf_status():
    """Get YA-WAMF backend status if available."""
    system_status = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            health = await client.get("http://localhost:8953/api/health")
            system_status["health"] = health.json()
        except Exception as e:
            system_status["health"] = {"error": str(e)}

    return system_status


@router.get("/yawamf/events")
async def get_yawamf_events(limit: int = Query(5, ge=1, le=50)):
    """Get recent events from YA-WAMF."""
    try:
        # Connect to SSE endpoint
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream(
                "GET",
                f"http://localhost:8953/api/events",
                headers={"Accept": "text/event-stream"}
            ) as response:
                import json
                events = []
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            events.append(data)
                            if len(events) >= limit:
                                break
                        except:
                            pass
                return events
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to connect to YA-WAMF: {e}")


# =============================================================================
# Whisper-Live Integration
# =============================================================================

@router.get("/whisper/status")
async def get_whisper_status():
    """Check WhisperLive WebSocket server status."""
    host = os.environ.get("WHISPER_HOST", "whisper-live")
    port = int(os.environ.get("WHISPER_PORT", "9090"))

    reachable, response_time, error = await check_tcp_port(host, port)

    return {
        "host": host,
        "port": port,
        "reachable": reachable,
        "response_time_ms": round(response_time, 2),
        "error": error,
        "note": "WhisperLive uses WebSocket protocol - TCP check only confirms port is open"
    }


# =============================================================================
# Logs (if available)
# =============================================================================

@router.get("/logs")
async def get_recent_logs(lines: int = Query(50, ge=1, le=500)):
    """Get recent application logs if available."""
    # This would work if logs are written to a file
    log_paths = [
        "/var/log/thewallflower.log",
        "/data/logs/app.log",
        "/tmp/app.log"
    ]

    for path in log_paths:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    all_lines = f.readlines()
                    return {
                        "source": path,
                        "lines": all_lines[-lines:]
                    }
            except Exception as e:
                continue

    return {
        "source": None,
        "message": "No log file found. Logs are output to stdout/stderr.",
        "hint": "Use 'docker logs <container>' to view logs"
    }


# =============================================================================
# Ping/Healthcheck
# =============================================================================

@router.get("/ping")
async def ping():
    """Simple ping endpoint for connectivity testing."""
    return {
        "status": "pong",
        "timestamp": datetime.utcnow().isoformat(),
        "hostname": socket.gethostname()
    }
