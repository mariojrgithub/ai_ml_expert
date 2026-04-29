import asyncio
import json
from typing import Any, Dict, List


class JsonRpcStdioMcpClient:
    def __init__(self, command: str, args: List[str] | None = None):
        self.command = command
        self.args = args or []
        self.process = None
        self._request_id = 0

    async def __aenter__(self):
        self.process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.process and self.process.returncode is None:
            self.process.terminate()
            await self.process.wait()

    async def initialize(self) -> Dict[str, Any]:
        result = await self.request(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {
                    "name": "engineering-copilot",
                    "version": "0.0.6",
                },
            },
        )
        # MCP spec requires sending this notification after the initialize response
        # so the server transitions from initializing → operational state.
        await self.notify("notifications/initialized", {})
        return result

    async def notify(self, method: str, params: Dict[str, Any]) -> None:
        """Send a JSON-RPC notification (no id, no response expected)."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        self.process.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
        await self.process.stdin.drain()

    async def list_tools(self) -> Dict[str, Any]:
        return await self.request("tools/list", {})

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return await self.request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments,
            },
        )

    async def request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        self._request_id += 1
        request_id = self._request_id
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        self.process.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
        await self.process.stdin.drain()

        while True:
            line = await self.process.stdout.readline()
            if not line:
                stderr_bytes = await self.process.stderr.read()
                stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()
                rc = self.process.returncode
                raise RuntimeError(
                    f"No response received from MCP server (returncode={rc}, stderr={stderr_text or '<empty>'})"
                )

            try:
                message = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                # Ignore non-JSON noise from subprocess stdout.
                continue

            # MCP servers can emit notifications/log events before the actual reply.
            if message.get("id") != request_id:
                continue

            if "error" in message:
                raise RuntimeError(f"MCP error: {message['error']}")

            return message.get("result", {})