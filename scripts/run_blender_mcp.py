#!/usr/bin/env python3
"""Send a local Python file to Blender through the official MCP server."""

from __future__ import annotations

import json
import os
import selectors
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "blender" / "mcp"
LOCAL_SERVER = PROJECT / ".venv" / "bin" / "blender-mcp"
TIMEOUT_SECONDS = 180


class McpClient:
    def __init__(self) -> None:
        env = os.environ.copy()
        env["BLENDER_MCP_HOST"] = "127.0.0.1"
        env["BLENDER_MCP_PORT"] = env.get("BLENDER_MCP_PORT", "9876")
        server_command = [str(LOCAL_SERVER)] if LOCAL_SERVER.exists() else ["uv", "run", "--project", str(PROJECT), "blender-mcp"]
        self.process = subprocess.Popen(
            server_command,
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
        request_id = self.request_id
        message: dict[str, object] = {"jsonrpc": "2.0", "id": request_id, "method": method}
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
                if not selector.select(TIMEOUT_SECONDS):
                    raise TimeoutError(f"Timed out waiting for {method!r}")
                line = self.process.stdout.readline()
                if not line:
                    raise RuntimeError(self.failure_message())
                try:
                    response = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if response.get("id") != request_id:
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

    def failure_message(self) -> str:
        stderr = self.process.stderr.read() if self.process.stderr is not None else ""
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
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} PATH_TO_BLENDER_PYTHON", file=sys.stderr)
        return 2
    code_path = Path(sys.argv[1]).resolve()
    # Keep the MCP payload small and let Blender read the project-owned script
    # from the shared checkout. Large inline source payloads can exceed the
    # bridge's JSON response buffer when a procedural scene grows.
    code = (
        "import runpy\n"
        f"result = runpy.run_path({str(code_path)!r}, run_name='__intermedia_mcp__').get('result')\n"
    )
    client = McpClient()
    try:
        client.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "residential-runner", "version": "0.1.0"},
            },
        )
        client.notify("notifications/initialized")
        result = client.request(
            "tools/call",
            {"name": "execute_blender_code", "arguments": {"code": code}},
        )
        payload = result.get("structuredContent")
        if payload is None:
            for block in result.get("content", []):
                if block.get("type") == "text":
                    try:
                        payload = json.loads(block["text"])
                    except json.JSONDecodeError:
                        payload = {"message": block["text"]}
                    break
        payload = dict(payload or {})
        for key in ("stdout", "stderr"):
            if isinstance(payload.get(key), str) and len(payload[key]) > 1600:
                payload[key] = "[earlier export log omitted]\n" + payload[key][-1600:]
        failed = result.get("isError", False) or payload.get("status") == "error"
        print(json.dumps({"isError": failed, "result": payload}, indent=2))
        return 1 if failed else 0
    except (OSError, RuntimeError, TimeoutError) as error:
        print(f"Blender MCP call failed: {error}", file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
