"""
MCP Client Wrapper - Isolates all async MCP SDK calls behind sync functions.

Educational Note: MCP (Model Context Protocol) is a standard protocol for AI
apps to connect to external data sources via JSON-RPC. This wrapper supports
two transports:

- SSE (Server-Sent Events): HTTP-based, natural for web apps
- Stdio: Subprocess-based, launches MCP server as a child process
  (e.g., `uvx freshdesk-mcp`). Common for CLI-based MCP servers.

We wrap async calls with asyncio.run() for Flask compatibility. Each function
creates a fresh connection to avoid stale session issues.

Timeouts: 10s connect, 30s per resource/tool call.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import re
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Optional

logger = logging.getLogger(__name__)


def _run_async(coro):
    """
    Run an async coroutine from sync code, safely handling the case
    where an event loop is already running (e.g. background threads).
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No event loop running — safe to use asyncio.run()
        return asyncio.run(coro)
    # Already inside a loop — run in a separate thread to avoid
    # "This event loop is already running" errors
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


# Connection timeout in seconds
CONNECT_TIMEOUT = 10
# Per-resource/tool read timeout in seconds
READ_TIMEOUT = 30

# Allowed commands for stdio transport (security: prevent arbitrary execution)
ALLOWED_STDIO_COMMANDS = {"uvx", "npx", "node", "python3", "python", "docker"}

# Pattern to detect shell metacharacters (prevent injection)
SHELL_METACHAR_PATTERN = re.compile(r"[|;&`$(){}\n]")

# Env vars that could subvert the command allowlist (e.g. redirect PATH to a malicious binary)
BLOCKED_ENV_KEYS = {
    "PATH", "LD_PRELOAD", "LD_LIBRARY_PATH",
    "DYLD_INSERT_LIBRARIES", "DYLD_LIBRARY_PATH",
    "HOME", "SHELL", "USER", "PYTHONPATH",
}


def _build_headers(auth_type: str, auth_config: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """
    Build HTTP headers for MCP server authentication.

    Supported auth types:
    - none: No auth headers
    - bearer: Authorization: Bearer <token>
    - api_key: X-API-Key: <key>
    - header: Custom header name + value from auth_config
    """
    if not auth_type or auth_type == "none" or not auth_config:
        return {}

    if auth_type == "bearer":
        token = auth_config.get("token", "")
        return {"Authorization": f"Bearer {token}"} if token else {}

    if auth_type == "api_key":
        key = auth_config.get("key", "")
        return {"X-API-Key": key} if key else {}

    if auth_type == "header":
        header_name = auth_config.get("header_name", "")
        header_value = auth_config.get("header_value", "")
        return {header_name: header_value} if header_name and header_value else {}

    return {}


def _validate_stdio_command(command: str, args: List[str], env: Optional[Dict[str, str]] = None) -> None:
    """
    Validate stdio command against allowlist and check for injection.

    Educational Note: stdio spawns real processes — we must prevent
    arbitrary command execution. Only known-safe commands are allowed,
    shell metacharacters are rejected in args, and dangerous env vars
    (like PATH, LD_PRELOAD) are blocked to prevent allowlist bypass.
    """
    if command not in ALLOWED_STDIO_COMMANDS:
        raise ValueError(
            f"Command '{command}' not allowed. "
            f"Allowed commands: {', '.join(sorted(ALLOWED_STDIO_COMMANDS))}"
        )

    for arg in args:
        if SHELL_METACHAR_PATTERN.search(arg):
            raise ValueError(f"Argument contains shell metacharacters: '{arg}'")

    if env:
        for key in env:
            if key.upper() in BLOCKED_ENV_KEYS:
                raise ValueError(f"Environment variable '{key}' is blocked for security reasons")


@asynccontextmanager
async def _connect(connection_config: Dict[str, Any]) -> AsyncIterator:
    """
    Create an MCP session for either SSE or stdio transport.

    Educational Note: This is the central abstraction that all functions use.
    It yields an initialized ClientSession regardless of transport type.
    For stdio, a subprocess is spawned and cleaned up on exit.
    For SSE, an HTTP connection is established.

    Args:
        connection_config: Dict with transport, server_url, auth_type,
                          auth_config, stdio_config fields.

    Yields:
        Initialized ClientSession ready for API calls.
    """
    from mcp import ClientSession

    transport = connection_config.get("transport", "sse")

    if transport == "stdio":
        from mcp.client.stdio import StdioServerParameters, stdio_client

        stdio_cfg = connection_config.get("stdio_config") or {}
        command = stdio_cfg.get("command", "")
        args = stdio_cfg.get("args", [])
        env = stdio_cfg.get("env")

        _validate_stdio_command(command, args, env)

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env,
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
    else:
        from mcp.client.sse import sse_client

        auth_headers = _build_headers(
            connection_config.get("auth_type", "none"),
            connection_config.get("auth_config"),
        )
        server_url = connection_config.get("server_url", "")
        async with sse_client(server_url, headers=auth_headers, timeout=CONNECT_TIMEOUT) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session


# ---------------------------------------------------------------------------
# Async implementations
# ---------------------------------------------------------------------------

async def _validate_connection_async(connection_config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate by connecting and initializing a session."""
    async with _connect(connection_config) as session:
        # Session is already initialized by _connect
        # We need server info from the initialization result
        # Re-initialize to get the result object
        # Actually, _connect already initialized. Let's use list_tools/list_resources
        # to verify the connection is working. The fact that _connect succeeded
        # means the connection is valid.
        #
        # For server info, we can try listing tools (lightweight call)
        warnings: List[str] = []

        try:
            tools_resp = await session.list_tools()
            tool_count = len(tools_resp.tools) if hasattr(tools_resp, "tools") else 0
        except Exception as e:
            logger.warning("MCP validation: tool listing failed: %s", e)
            tool_count = 0
            warnings.append(f"Tool listing failed: {e}")

        try:
            resources_resp = await session.list_resources()
            resource_count = len(resources_resp.resources) if hasattr(resources_resp, "resources") else 0
        except Exception as e:
            logger.warning("MCP validation: resource listing failed: %s", e)
            resource_count = 0
            warnings.append(f"Resource listing failed: {e}")

        return {
            "valid": True,
            "server_name": "MCP Server",
            "server_version": "Unknown",
            "tool_count": tool_count,
            "resource_count": resource_count,
            "error": None,
            "warnings": warnings if warnings else None,
        }


async def _list_resources_async(connection_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """List available resources from an MCP server."""
    async with _connect(connection_config) as session:
        response = await session.list_resources()
        resources = response.resources if hasattr(response, "resources") else []
        return [
            {
                "uri": str(r.uri),
                "name": r.name if hasattr(r, "name") else str(r.uri),
                "description": r.description if hasattr(r, "description") else "",
                "mime_type": r.mimeType if hasattr(r, "mimeType") else None,
            }
            for r in resources
        ]


async def _read_resources_async(
    connection_config: Dict[str, Any],
    resource_uris: List[str],
) -> List[Dict[str, Any]]:
    """Read content from specific MCP resources."""
    results: List[Dict[str, Any]] = []

    async with _connect(connection_config) as session:
        for uri in resource_uris:
            try:
                response = await asyncio.wait_for(
                    session.read_resource(uri),
                    timeout=READ_TIMEOUT,
                )
                content_parts = response.contents if hasattr(response, "contents") else []
                text_content = ""
                for part in content_parts:
                    if hasattr(part, "text"):
                        text_content += part.text
                    elif hasattr(part, "blob"):
                        text_content += f"[Binary content: {len(part.blob)} bytes]"

                results.append({
                    "uri": uri,
                    "name": uri.split("/")[-1] if "/" in uri else uri,
                    "content": text_content,
                })
            except asyncio.TimeoutError:
                logger.warning("Timeout reading MCP resource: %s", uri)
                results.append({
                    "uri": uri,
                    "name": uri.split("/")[-1] if "/" in uri else uri,
                    "content": f"[Error: Read timeout after {READ_TIMEOUT}s]",
                })
            except Exception as e:
                logger.warning("Error reading MCP resource %s: %s", uri, e)
                results.append({
                    "uri": uri,
                    "name": uri.split("/")[-1] if "/" in uri else uri,
                    "content": f"[Error: {str(e)}]",
                })

    return results


async def _list_tools_async(connection_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    List available tools from an MCP server.

    Educational Note: MCP tools use JSON Schema for their input schemas,
    which maps directly to Claude's tool input_schema format — no conversion needed.
    """
    async with _connect(connection_config) as session:
        response = await session.list_tools()
        tools = response.tools if hasattr(response, "tools") else []
        return [
            {
                "name": t.name,
                "description": t.description or "",
                "input_schema": t.inputSchema if hasattr(t, "inputSchema") else {"type": "object", "properties": {}},
            }
            for t in tools
        ]


async def _call_tool_async(
    connection_config: Dict[str, Any],
    tool_name: str,
    arguments: Dict[str, Any],
) -> str:
    """
    Call a tool on an MCP server and return the result as text.

    Educational Note: MCP tool results contain content blocks (TextContent,
    ImageContent, EmbeddedResource). We extract text from each block and
    concatenate them. If the result indicates an error, we prefix with "Error:".
    """
    async with _connect(connection_config) as session:
        result = await asyncio.wait_for(
            session.call_tool(tool_name, arguments),
            timeout=READ_TIMEOUT,
        )

        # Extract text from content blocks
        parts: List[str] = []
        for block in (result.content if hasattr(result, "content") else []):
            if hasattr(block, "text"):
                parts.append(block.text)
            elif hasattr(block, "blob"):
                parts.append(f"[Binary content: {len(block.blob)} bytes]")
            else:
                parts.append(str(block))

        text = "\n".join(parts) if parts else "(No output)"

        # Check if the MCP server reported an error
        if hasattr(result, "isError") and result.isError:
            text = f"Error: {text}"

        return text


# ---------------------------------------------------------------------------
# Public sync API (called from Flask routes and services)
# ---------------------------------------------------------------------------

def _extract_root_cause(e: Exception) -> str:
    """
    Extract a human-readable error message from potentially nested exceptions.

    Educational Note: The MCP SDK uses asyncio TaskGroups internally, which wrap
    errors in ExceptionGroup/BaseExceptionGroup. The actual root cause (e.g.,
    "npm package not found" or "connection refused") is buried inside. We dig
    it out so users see something useful instead of "unhandled errors in a TaskGroup".
    """
    # Handle ExceptionGroup (Python 3.11+) / BaseExceptionGroup
    if hasattr(e, "exceptions"):
        for sub in e.exceptions:
            return _extract_root_cause(sub)

    # Handle chained exceptions
    if e.__cause__:
        return _extract_root_cause(e.__cause__)

    msg = str(e)

    # Clean up common unhelpful wrappers
    if "TaskGroup" in msg and hasattr(e, "__context__") and e.__context__:
        return _extract_root_cause(e.__context__)

    return msg or type(e).__name__


def validate_connection(
    server_url: str = "",
    auth_type: str = "none",
    auth_config: Optional[Dict[str, Any]] = None,
    transport: str = "sse",
    stdio_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Validate an MCP server connection by initializing a session.

    Returns:
        {"valid": True, "server_name": "...", "tool_count": N, ...}
        or {"valid": False, ..., "error": "..."}
    """
    connection_config = {
        "transport": transport,
        "server_url": server_url,
        "auth_type": auth_type,
        "auth_config": auth_config,
        "stdio_config": stdio_config,
    }
    try:
        return _run_async(_validate_connection_async(connection_config))
    except Exception as e:
        identifier = server_url if transport == "sse" else (stdio_config or {}).get("command", "unknown")
        root_cause = _extract_root_cause(e)
        logger.warning("MCP connection validation failed for %s: %s", identifier, root_cause)
        return {
            "valid": False,
            "server_name": None,
            "server_version": None,
            "tool_count": 0,
            "resource_count": 0,
            "error": root_cause,
        }


def list_resources(
    server_url: str = "",
    auth_type: str = "none",
    auth_config: Optional[Dict[str, Any]] = None,
    transport: str = "sse",
    stdio_config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """List available resources from an MCP server."""
    connection_config = {
        "transport": transport,
        "server_url": server_url,
        "auth_type": auth_type,
        "auth_config": auth_config,
        "stdio_config": stdio_config,
    }
    return _run_async(_list_resources_async(connection_config))


def read_resources(
    server_url: str = "",
    auth_type: str = "none",
    auth_config: Optional[Dict[str, Any]] = None,
    resource_uris: Optional[List[str]] = None,
    transport: str = "sse",
    stdio_config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Read content from specific MCP resources."""
    if not resource_uris:
        return []
    connection_config = {
        "transport": transport,
        "server_url": server_url,
        "auth_type": auth_type,
        "auth_config": auth_config,
        "stdio_config": stdio_config,
    }
    return _run_async(_read_resources_async(connection_config, resource_uris))


def list_tools(
    server_url: str = "",
    auth_type: str = "none",
    auth_config: Optional[Dict[str, Any]] = None,
    transport: str = "sse",
    stdio_config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    List available tools from an MCP server.

    Returns:
        List of {"name": "...", "description": "...", "input_schema": {...}}
    """
    connection_config = {
        "transport": transport,
        "server_url": server_url,
        "auth_type": auth_type,
        "auth_config": auth_config,
        "stdio_config": stdio_config,
    }
    return _run_async(_list_tools_async(connection_config))


def call_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    server_url: str = "",
    auth_type: str = "none",
    auth_config: Optional[Dict[str, Any]] = None,
    transport: str = "sse",
    stdio_config: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Call a tool on an MCP server and return the result as text.

    Returns:
        Result text from the tool execution.
    """
    connection_config = {
        "transport": transport,
        "server_url": server_url,
        "auth_type": auth_type,
        "auth_config": auth_config,
        "stdio_config": stdio_config,
    }
    return _run_async(_call_tool_async(connection_config, tool_name, arguments))
