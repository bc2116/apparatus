"""Minimal, zero-network MCP stdio JSON-RPC 2.0 protocol implementation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import io
import json
import os
import sys
from typing import Any, BinaryIO

PROTOCOL_VERSION = "2025-11-25"
MAX_REQUEST_BYTES = 65_536
MAX_RESULT_BYTES = 524_288

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class ToolInputError(Exception):
    """Raised when tool arguments fail schema or value validation."""


class ToolExecutionError(Exception):
    """Raised when a read-only tool call fails operationally at runtime."""


@dataclass(frozen=True)
class ToolDefinition:
    """Registered MCP tool descriptor and call handler."""

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], dict[str, Any]]
    annotations: dict[str, Any]

    def to_wire(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "annotations": dict(self.annotations),
        }


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _error_response(
    request_id: Any,
    code: int,
    message: str,
    data: Any = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def _success_response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _tool_error_result(message: str, *, status: str = "error") -> dict[str, Any]:
    payload = {"status": status, "error": message}
    return {
        "content": [{"type": "text", "text": _json_dumps(payload)}],
        "isError": True,
    }


def _is_valid_request_id(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    return isinstance(value, (str, int)) or value is None


def _configure_windows_binary_stdio(stdin: BinaryIO, stdout: BinaryIO) -> None:
    if sys.platform != "win32":
        return
    import msvcrt

    for stream in (stdin, stdout):
        try:
            fd = stream.fileno()
        except (AttributeError, OSError, io.UnsupportedOperation):
            continue
        try:
            msvcrt.setmode(fd, os.O_BINARY)
        except OSError:
            continue


def _read_bounded_line(stream: BinaryIO, max_bytes: int) -> tuple[bytes | None, bool]:
    """Read one LF-delimited line up to ``max_bytes`` (excluding line ending).

    Returns ``(None, False)`` on EOF, ``(None, True)`` if the line exceeds
    ``max_bytes`` (after draining through the terminating LF or EOF), or
    ``(line_without_crlf, False)`` on a bounded line.
    """
    raw = stream.readline(max_bytes + 2)
    if not raw:
        return None, False
    if raw.endswith(b"\n"):
        stripped = raw[:-1]
        if stripped.endswith(b"\r"):
            stripped = stripped[:-1]
        if len(stripped) > max_bytes:
            return None, True
        return stripped, False
    # Line did not end with LF within max_bytes + 2 bytes: either EOF or oversized.
    if len(raw) <= max_bytes:
        stripped = raw[:-1] if raw.endswith(b"\r") else raw
        return stripped, False
    while True:
        chunk = stream.readline(max_bytes)
        if not chunk or chunk.endswith(b"\n"):
            break
    return None, True


def _write_message(stream: BinaryIO, message: dict[str, Any]) -> None:
    line = (_json_dumps(message) + "\n").encode("utf-8")
    stream.write(line)
    stream.flush()


class McpServer:
    """Stateful MCP 2025-11-25 stdio JSON-RPC 2.0 server."""

    def __init__(
        self,
        *,
        server_name: str,
        server_version: str,
        tools: list[ToolDefinition],
        protocol_version: str = PROTOCOL_VERSION,
        max_request_bytes: int = MAX_REQUEST_BYTES,
        max_result_bytes: int = MAX_RESULT_BYTES,
    ) -> None:
        self._server_name = server_name
        self._server_version = server_version
        self._protocol_version = protocol_version
        self._max_request_bytes = max_request_bytes
        self._max_result_bytes = max_result_bytes
        self._tools = {tool.name: tool for tool in tools}
        self._initialized = False
        self._client_ready = False

    def handle_line(self, raw_line: bytes) -> dict[str, Any] | None:
        """Process one line-delimited JSON-RPC frame and return a response dict or None."""
        if not raw_line.strip():
            return None
        try:
            text = raw_line.decode("utf-8")
        except UnicodeDecodeError:
            return _error_response(None, PARSE_ERROR, "invalid UTF-8 payload")
        if "\n" in text or "\r" in text:
            return _error_response(None, INVALID_REQUEST, "embedded newlines are not allowed")
        try:
            message = json.loads(text)
        except ValueError:
            return _error_response(None, PARSE_ERROR, "malformed JSON-RPC payload")
        return self.handle_message(message)

    def handle_message(self, message: Any) -> dict[str, Any] | None:
        """Dispatch a parsed JSON-RPC 2.0 request or notification."""
        if not isinstance(message, dict):
            return _error_response(None, INVALID_REQUEST, "JSON-RPC message must be an object")

        has_id = "id" in message
        raw_id = message.get("id")
        if has_id and (not _is_valid_request_id(raw_id) or raw_id is None):
            return _error_response(None, INVALID_REQUEST, "invalid JSON-RPC request id")
        req_id = raw_id if has_id else None

        if message.get("jsonrpc") != "2.0":
            return _error_response(req_id, INVALID_REQUEST, "jsonrpc version must be '2.0'")

        method = message.get("method")
        if not isinstance(method, str) or not method:
            return _error_response(req_id, INVALID_REQUEST, "method must be a non-empty string")

        params = message.get("params")

        if not has_id:
            if method == "notifications/initialized" and self._initialized:
                self._client_ready = True
            return None

        if method == "ping":
            if params is not None and not isinstance(params, dict):
                return _error_response(req_id, INVALID_PARAMS, "ping params must be an object")
            return _success_response(req_id, {})

        if method == "initialize":
            return self._handle_initialize(req_id, params)

        if not self._initialized:
            return _error_response(
                req_id,
                INVALID_REQUEST,
                "server not initialized; call initialize first",
            )

        if method == "tools/list":
            if params is not None and not isinstance(params, dict):
                return _error_response(req_id, INVALID_PARAMS, "tools/list params must be an object")
            return _success_response(
                req_id,
                {"tools": [tool.to_wire() for tool in self._tools.values()]},
            )

        if method == "tools/call":
            return self._handle_tool_call(req_id, params)

        return _error_response(req_id, METHOD_NOT_FOUND, f"method not found: {method}")

    def _handle_initialize(self, req_id: Any, params: Any) -> dict[str, Any]:
        if self._initialized:
            return _error_response(req_id, INVALID_REQUEST, "server already initialized")
        if not isinstance(params, dict):
            return _error_response(req_id, INVALID_PARAMS, "initialize params must be an object")
        requested_version = params.get("protocolVersion")
        if not isinstance(requested_version, str) or not requested_version.strip():
            return _error_response(
                req_id,
                INVALID_PARAMS,
                "initialize requires a non-empty string protocolVersion",
            )
        self._initialized = True
        return _success_response(
            req_id,
            {
                "protocolVersion": self._protocol_version,
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": self._server_name,
                    "version": self._server_version,
                },
            },
        )

    def _handle_tool_call(self, req_id: Any, params: Any) -> dict[str, Any]:
        if not isinstance(params, dict):
            return _error_response(req_id, INVALID_PARAMS, "tools/call params must be an object")
        tool_name = params.get("name")
        if not isinstance(tool_name, str) or not tool_name:
            return _error_response(req_id, INVALID_PARAMS, "tools/call requires tool name")
        arguments = params.get("arguments")
        if arguments is None:
            arguments = {}
        elif not isinstance(arguments, dict):
            return _error_response(
                req_id,
                INVALID_PARAMS,
                "tools/call arguments must be an object",
            )

        tool = self._tools.get(tool_name)
        if tool is None:
            return _error_response(req_id, INVALID_PARAMS, f"unknown tool: {tool_name}")

        try:
            payload = tool.handler(arguments)
        except ToolInputError as error:
            return _success_response(
                req_id,
                _tool_error_result(str(error), status="invalid_arguments"),
            )
        except ToolExecutionError as error:
            return _success_response(
                req_id,
                _tool_error_result(str(error), status="execution_error"),
            )
        except Exception:
            return _error_response(req_id, INTERNAL_ERROR, "internal tool execution error")

        result = {
            "content": [{"type": "text", "text": _json_dumps(payload)}],
            "structuredContent": payload,
            "isError": False,
        }
        response = _success_response(req_id, result)
        encoded = (_json_dumps(response) + "\n").encode("utf-8")
        if len(encoded) > self._max_result_bytes:
            return _success_response(
                req_id,
                _tool_error_result(
                    f"tool result exceeds {self._max_result_bytes}-byte limit",
                    status="result_too_large",
                ),
            )
        return response

    def serve_stdio(
        self,
        stdin: BinaryIO | None = None,
        stdout: BinaryIO | None = None,
    ) -> int:
        """Serve JSON-RPC 2.0 requests over newline-delimited binary stdio until EOF."""
        in_stream = stdin if stdin is not None else sys.stdin.buffer
        out_stream = stdout if stdout is not None else sys.stdout.buffer
        _configure_windows_binary_stdio(in_stream, out_stream)
        while True:
            raw_line, oversized = _read_bounded_line(in_stream, self._max_request_bytes)
            if oversized:
                _write_message(
                    out_stream,
                    _error_response(
                        None,
                        INVALID_REQUEST,
                        f"request exceeds {self._max_request_bytes}-byte limit",
                    ),
                )
                continue
            if raw_line is None:
                return 0
            response = self.handle_line(raw_line)
            if response is not None:
                _write_message(out_stream, response)
