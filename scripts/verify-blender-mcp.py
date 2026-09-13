#!/usr/bin/env python3
"""Verify the project-local Blender Lab MCP connection without changing a scene."""

from __future__ import annotations

import json
import os
import selectors
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "blender" / "mcp"
TIMEOUT_SECONDS = 30


class McpProcess:
    def __init__(self) -> None:
        env = os.environ.copy()
        env["BLENDER_HOST"] = "127.0.0.1"
        env["BLENDER_PORT"] = "9876"
        self.process = subprocess.Popen(
            ["uv", "run", "--project", str(PROJECT), "blender-mcp"],
            cwd=ROOT,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.request_id = 0

    def request(self, method: str, params: dict[str, object] | None = None) -> dict[str, object]:
        self.request_id += 1
        message: dict[str, object] = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
        }
        if params is not None:
            message["params"] = params
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

        selector = selectors.DefaultSelector()
        selector.register(self.process.stdout, selectors.EVENT_READ)
        try:
            while True:
                events = selector.select(TIMEOUT_SECONDS)
                if not events:
                    raise TimeoutError(f"Timed out waiting for MCP method {method!r}")
                line = self.process.stdout.readline()
                if not line:
                    raise RuntimeError(self._failure_message())
                try:
                    response = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if response.get("id") != self.request_id:
                    continue
                if "error" in response:
                    raise RuntimeError(json.dumps(response["error"], indent=2))
                return response.get("result", {})
        finally:
            selector.close()

    def notify(self, method: str) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")
        self.process.stdin.flush()

    def _failure_message(self) -> str:
        stderr = ""
        if self.process.stderr is not None:
            stderr = self.process.stderr.read()
        return f"Blender MCP exited with code {self.process.returncode}: {stderr.strip()}"

    def close(self) -> None:
        if self.process.stdin is not None:
            self.process.stdin.close()
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()


def main() -> int:
    client = McpProcess()
    try:
        initialize = client.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "residential-verifier", "version": "0.1.0"},
            },
        )
        client.notify("notifications/initialized")
        tools_result = client.request("tools/list")
        tool_names = sorted(tool["name"] for tool in tools_result.get("tools", []))
        if "execute_blender_code" not in tool_names:
            raise RuntimeError("The Blender MCP server is reachable but execute_blender_code is unavailable")

        probe = client.request(
            "tools/call",
            {
                "name": "execute_blender_code",
                "arguments": {
                    "code": (
                        "import bpy\n"
                        "result = {\n"
                        "    'blender_version': bpy.app.version_string,\n"
                        "    'scene': bpy.context.scene.name if bpy.context.scene else None,\n"
                        "    'filepath': bpy.data.filepath,\n"
                        "}\n"
                    )
                },
            },
        )
        print(json.dumps({"initialize": initialize, "tool_count": len(tool_names), "probe": probe}, indent=2))
        return 0
    except (OSError, RuntimeError, TimeoutError) as error:
        print(f"Blender MCP verification failed: {error}", file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
