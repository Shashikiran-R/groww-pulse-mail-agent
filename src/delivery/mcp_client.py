"""
MCP Client and Delivery Base Utilities for Google Workspace MCP Server.

Supports:
1. Remote Streamable HTTP/SSE mode (aiagentserver.onrender.com/sse)
2. Local stdio mode (subprocess JSON-RPC)
3. Server-verifiable human approval models and idempotency tracking.
"""

from __future__ import annotations

import os
import re
import json
import uuid
import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import httpx

logger = logging.getLogger(__name__)


class DeliveryError(Exception):
    """Raised when an MCP delivery tool fails or configuration is invalid."""
    pass


@dataclass
class DeliveryApprovalResult:
    """Represents the outcome of an MCP tool call (often requiring human approval)."""
    status: str                         # e.g. "pending_approval", "executed", "error"
    action_id: Optional[str] = None
    approval_url: Optional[str] = None  # e.g. https://aiagentserver.onrender.com/approve/<id>
    target_url: Optional[str] = None    # e.g. Google Doc URL
    preview: Optional[Dict[str, Any]] = None
    expires_at: Optional[str] = None
    error: Optional[str] = None

    @property
    def is_pending(self) -> bool:
        return self.status == "pending_approval" and bool(self.approval_url)

    @property
    def is_executed(self) -> bool:
        return self.status in ("executed", "succeeded")


def parse_tool_content(response_data: dict[str, Any]) -> dict[str, Any]:
    """Extract and parse JSON text payload from MCP tool response."""
    if not isinstance(response_data, dict):
        return {"raw": response_data}

    content_list = response_data.get("content", [])
    if isinstance(content_list, list) and content_list:
        text_block = content_list[0]
        if isinstance(text_block, dict) and "text" in text_block:
            raw_text = text_block["text"]
            try:
                parsed = json.loads(raw_text)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return {"text": raw_text}

    return response_data


class RemoteSSEMCPClient:
    """
    Remote MCP client using official HTTP with Server-Sent Events (SSE) transport.
    Connects to an SSE endpoint (e.g., https://aiagentserver.onrender.com/sse)
    and sends JSON-RPC requests via HTTP POST to the returned message endpoint.
    """

    def __init__(
        self,
        server_url: str = "https://aiagentserver.onrender.com",
        auth_token: Optional[str] = None,
        timeout: float = 30.0,
    ):
        base = server_url.rstrip("/")
        if base.endswith("/sse"):
            self.sse_url = base
            self.base_url = base[:-4]
        else:
            self.base_url = base
            self.sse_url = f"{base}/sse"

        self.auth_token = auth_token or os.getenv("MCP_AUTH_TOKEN", "")
        self.timeout = timeout
        self.messages_url: Optional[str] = None
        self._http_client: Optional[httpx.AsyncClient] = None
        self._sse_task: Optional[asyncio.Task] = None
        self._pending_requests: dict[int, asyncio.Future] = {}
        self._request_id = 0
        self._started = False

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "text/event-stream",
            "User-Agent": "GrowwPulseAgent/1.0",
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    async def start(self) -> None:
        """Establish the SSE connection and receive the messages POST endpoint."""
        if self._started:
            return

        self._http_client = httpx.AsyncClient(timeout=self.timeout)
        endpoint_future: asyncio.Future[str] = asyncio.get_event_loop().create_future()

        async def _sse_listener():
            try:
                headers = self._headers()
                async with self._http_client.stream("GET", self.sse_url, headers=headers, timeout=None) as response:
                    if response.status_code == 401:
                        if not endpoint_future.done():
                            endpoint_future.set_exception(DeliveryError("401 Unauthorized: Valid MCP_AUTH_TOKEN required"))
                        return
                    if response.status_code != 200:
                        if not endpoint_future.done():
                            endpoint_future.set_exception(DeliveryError(f"SSE connection failed with HTTP {response.status_code}"))
                        return

                    current_event = None
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            current_event = None
                            continue

                        if line.startswith("event:"):
                            current_event = line[6:].strip()
                        elif line.startswith("data:"):
                            data_str = line[5:].strip()
                            if current_event == "endpoint" or "/messages" in data_str:
                                endpoint = data_str
                                if not endpoint.startswith("http"):
                                    endpoint = f"{self.base_url}{endpoint if endpoint.startswith('/') else '/' + endpoint}"
                                if not endpoint_future.done():
                                    endpoint_future.set_result(endpoint)
                            elif current_event == "message" or data_str.startswith("{"):
                                try:
                                    msg = json.loads(data_str)
                                    req_id = msg.get("id")
                                    if req_id in self._pending_requests:
                                        fut = self._pending_requests.pop(req_id)
                                        if not fut.done():
                                            fut.set_result(msg)
                                except Exception as err:
                                    logger.debug(f"Error parsing SSE message: {err}")

            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.warning(f"SSE background connection closed: {e}")
                if not endpoint_future.done():
                    endpoint_future.set_exception(DeliveryError(f"SSE connection failed: {e}"))

        self._sse_task = asyncio.create_task(_sse_listener())

        try:
            self.messages_url = await asyncio.wait_for(endpoint_future, timeout=12.0)
            self._started = True
            logger.info(f"Connected to remote MCP server via SSE. Post messages endpoint: {self.messages_url}")
        except asyncio.TimeoutError:
            await self.stop()
            raise DeliveryError(f"Timed out connecting to remote MCP SSE endpoint at {self.sse_url}")
        except Exception as e:
            await self.stop()
            raise DeliveryError(f"Failed to connect to remote MCP server: {e}")

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call an MCP tool on the remote server via JSON-RPC 2.0."""
        if not self._started or not self.messages_url or not self._http_client:
            await self.start()

        self._request_id += 1
        req_id = self._request_id

        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }

        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        fut: asyncio.Future[dict[str, Any]] = asyncio.get_event_loop().create_future()
        self._pending_requests[req_id] = fut

        try:
            post_resp = await self._http_client.post(
                self.messages_url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )

            # Some servers return JSON-RPC directly in the POST response
            if post_resp.status_code == 200:
                try:
                    direct_data = post_resp.json()
                    if isinstance(direct_data, dict) and direct_data.get("id") == req_id:
                        self._pending_requests.pop(req_id, None)
                        if "error" in direct_data:
                            raise DeliveryError(f"MCP tool error: {direct_data['error']}")
                        return direct_data.get("result", {})
                except Exception:
                    pass

            # Otherwise, wait for the response to arrive via the SSE event stream
            result_msg = await asyncio.wait_for(fut, timeout=self.timeout)
            if "error" in result_msg:
                raise DeliveryError(f"MCP tool error: {result_msg['error']}")
            return result_msg.get("result", {})

        except asyncio.TimeoutError:
            self._pending_requests.pop(req_id, None)
            raise DeliveryError(f"Timed out waiting for tool '{tool_name}' response after {self.timeout}s")
        except Exception as e:
            self._pending_requests.pop(req_id, None)
            if isinstance(e, DeliveryError):
                raise
            raise DeliveryError(f"Failed to execute tool '{tool_name}': {e}")

    async def list_tools(self) -> list[dict[str, Any]]:
        """List tools exposed by the MCP server."""
        if not self._started or not self.messages_url or not self._http_client:
            await self.start()

        self._request_id += 1
        req_id = self._request_id
        payload = {"jsonrpc": "2.0", "id": req_id, "method": "tools/list", "params": {}}

        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        fut = asyncio.get_event_loop().create_future()
        self._pending_requests[req_id] = fut

        try:
            post_resp = await self._http_client.post(self.messages_url, json=payload, headers=headers)
            if post_resp.status_code == 200:
                try:
                    direct = post_resp.json()
                    if direct.get("id") == req_id:
                        self._pending_requests.pop(req_id, None)
                        return direct.get("result", {}).get("tools", [])
                except Exception:
                    pass

            result_msg = await asyncio.wait_for(fut, timeout=self.timeout)
            return result_msg.get("result", {}).get("tools", [])
        except Exception as e:
            self._pending_requests.pop(req_id, None)
            logger.warning(f"Error listing MCP tools: {e}")
            return []

    async def check_connection_status(self) -> dict[str, Any]:
        """Check Google OAuth connection status via google_connection_status tool."""
        res = await self.call_tool("google_connection_status", {})
        return parse_tool_content(res)

    async def close(self) -> None:
        """Alias for stop()."""
        await self.stop()

    async def stop(self) -> None:
        """Close HTTP and SSE connections."""
        if self._sse_task and not self._sse_task.done():
            self._sse_task.cancel()
            try:
                await self._sse_task
            except asyncio.CancelledError:
                pass
        if self._http_client:
            await self._http_client.aclose()
        self._started = False
        self._pending_requests.clear()


class StdioMCPClient:
    """
    Local JSON-RPC 2.0 stdio MCP client.
    Connects to an MCP server spawned via subprocess.
    """

    def __init__(self, command: str, args: list[str], env: dict[str, str] | None = None):
        self.command = command
        self.args = args
        self.env = env or {}
        self.process: Optional[asyncio.subprocess.Process] = None
        self._request_id = 0

    async def start(self) -> None:
        """Start the MCP server subprocess."""
        merged_env = os.environ.copy()
        merged_env.update(self.env)

        self.process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=merged_env,
        )

        init_res = await self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "aiagent", "version": "1.0.0"},
        })
        logger.debug(f"MCP stdio server initialized: {init_res}")
        await self.send_notification("notifications/initialized", {})

    async def send_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON-RPC request and wait for the response."""
        if not self.process or self.process.returncode is not None:
            raise DeliveryError("MCP server process is not running")

        self._request_id += 1
        req_id = self._request_id
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }

        req_bytes = (json.dumps(payload) + "\n").encode("utf-8")
        self.process.stdin.write(req_bytes)
        await self.process.stdin.drain()

        while True:
            line = await self.process.stdout.readline()
            if not line:
                stderr_output = await self.process.stderr.read()
                raise DeliveryError(f"MCP server closed stdout unexpectedly: {stderr_output.decode(errors='ignore')}")

            line_str = line.decode("utf-8").strip()
            if not line_str:
                continue

            try:
                res = json.loads(line_str)
            except json.JSONDecodeError:
                continue

            if res.get("id") == req_id:
                if "error" in res:
                    raise DeliveryError(f"MCP error: {res['error']}")
                return res.get("result", {})

    async def send_notification(self, method: str, params: dict[str, Any]) -> None:
        """Send a JSON-RPC notification."""
        if not self.process or self.process.returncode is not None:
            return

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        req_bytes = (json.dumps(payload) + "\n").encode("utf-8")
        self.process.stdin.write(req_bytes)
        await self.process.stdin.drain()

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call an MCP tool on the local server."""
        return await self.send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })

    async def list_tools(self) -> list[dict[str, Any]]:
        """List tools exposed by the MCP server."""
        res = await self.send_request("tools/list", {})
        return res.get("tools", [])

    async def check_connection_status(self) -> dict[str, Any]:
        """Check Google OAuth connection status via google_connection_status tool."""
        res = await self.call_tool("google_connection_status", {})
        return parse_tool_content(res)

    async def close(self) -> None:
        """Alias for stop()."""
        await self.stop()

    async def stop(self) -> None:
        """Terminate the server process gracefully."""
        if self.process and self.process.returncode is None:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=3.0)
            except (asyncio.TimeoutError, ProcessLookupError):
                try:
                    self.process.kill()
                except ProcessLookupError:
                    pass


# Alias MCPClient to StdioMCPClient for backwards compatibility
MCPClient = StdioMCPClient


def load_and_validate_mcp_config(config_path: str | Path, server_name: str = "google-workspace") -> dict[str, Any]:
    """
    Validate that mcp_config.json exists, is valid JSON, and defines the requested server.
    Accepts both 'mcpServers' and 'servers' root keys.
    """
    path = Path(config_path)
    if not path.exists():
        raise DeliveryError(f"MCP config file not found: {path.resolve()}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise DeliveryError(f"Invalid JSON in MCP config file {path}: {e}")

    servers = data.get("mcpServers") or data.get("servers") or {}
    if server_name not in servers:
        # Check fallback aliases
        fallbacks = ["google-workspace", "google-workspace-local", "google-workspace-remote", "google-docs", "google-gmail"]
        match = next((fb for fb in fallbacks if fb in servers), None)
        if match:
            server_name = match
        else:
            raise DeliveryError(f"Server '{server_name}' not defined in {path}. Available: {list(servers.keys())}")

    server_conf = servers[server_name]

    # Remote SSE config
    if "serverUrl" in server_conf:
        headers = {}
        for k, v in server_conf.get("headers", {}).items():
            if isinstance(v, str) and "${" in v:
                for match_var in re.findall(r"\$\{([^}]+)\}", v):
                    val = os.getenv(match_var, "")
                    v = v.replace(f"${{{match_var}}}", val)
            headers[k] = v
        return {
            "type": "sse",
            "serverUrl": server_conf["serverUrl"],
            "headers": headers,
        }

    # Stdio config
    if "command" not in server_conf:
        raise DeliveryError(f"Missing 'command' or 'serverUrl' for MCP server '{server_name}' in {path}")

    env = {}
    for k, v in server_conf.get("env", {}).items():
        if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            var_name = v[2:-1]
            env[k] = os.getenv(var_name, "")
        else:
            env[k] = str(v)

    return {
        "type": "stdio",
        "command": server_conf["command"],
        "args": server_conf.get("args", []),
        "env": env,
    }


def create_mcp_client(config_path: str | Path = "mcp_config.json", server_name: str = "google-workspace") -> Union[RemoteSSEMCPClient, StdioMCPClient]:
    """Factory creating appropriate MCP client (RemoteSSEMCPClient or StdioMCPClient) from config or env."""
    transport_pref = os.getenv("MCP_TRANSPORT", "").lower()
    if transport_pref in ("stdio", "local") and server_name == "google-workspace":
        server_name = "google-workspace-local"

    # Check if explicit remote URL in environment without config file
    mcp_env_url = os.getenv("MCP_SERVER_URL")
    if mcp_env_url and not Path(config_path).exists() and transport_pref not in ("stdio", "local"):
        return RemoteSSEMCPClient(server_url=mcp_env_url, auth_token=os.getenv("MCP_AUTH_TOKEN"))

    conf = load_and_validate_mcp_config(config_path, server_name)
    if conf.get("type") == "sse":
        auth_header = conf.get("headers", {}).get("Authorization", "")
        token = auth_header.replace("Bearer ", "").strip() if "Bearer " in auth_header else os.getenv("MCP_AUTH_TOKEN", "")
        return RemoteSSEMCPClient(server_url=conf["serverUrl"], auth_token=token)
    else:
        return StdioMCPClient(command=conf["command"], args=conf.get("args", []), env=conf.get("env", {}))

