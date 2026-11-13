"""Tests for the optional read-only local MCP tool server (PR-76)."""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from apparatus_core import cli, mcp_protocol
from apparatus_core.cache import library_cache_root
from apparatus_core.commands import mcp as mcp_command
from apparatus_core.library import index
from apparatus_core.retention import set_no_memory, start_task


def _run_cli(
    args: list[str],
    *,
    env: dict[str, str],
    cwd: Path | None = None,
    stdin_bytes: bytes = b"",
) -> subprocess.CompletedProcess[bytes]:
    command = [
        sys.executable,
        "-c",
        "import sys; from apparatus_core.cli import main; raise SystemExit(main())",
        *args,
    ]
    return subprocess.run(
        command,
        input=stdin_bytes,
        capture_output=True,
        cwd=cwd,
        env=env,
        timeout=120,
    )


def _rpc(method: str, req_id: int | str | None = None, params: dict | None = None) -> bytes:
    msg: dict[str, object] = {"jsonrpc": "2.0", "method": method}
    if req_id is not None:
        msg["id"] = req_id
    if params is not None:
        msg["params"] = params
    return (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")


def _init_params() -> dict[str, object]:
    return {
        "protocolVersion": mcp_protocol.PROTOCOL_VERSION,
        "capabilities": {},
        "clientInfo": {"name": "test-client", "version": "1.0"},
    }


def _decode_lines(raw: bytes) -> list[dict]:
    lines = [line for line in raw.splitlines() if line]
    return [json.loads(line.decode("utf-8")) for line in lines]


def _tree_snapshot(root: Path) -> dict[str, tuple[int, str]]:
    """Capture normalized file paths, sizes, and SHA-256 digests under ``root``."""
    snapshot: dict[str, tuple[int, str]] = {}
    if not root.exists():
        return snapshot
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            snapshot[f"{rel}/"] = (0, "<dir>")
        else:
            data = path.read_bytes()
            snapshot[rel] = (len(data), hashlib.sha256(data).hexdigest())
    return snapshot


def _make_env(tmp_path: Path) -> dict[str, str]:
    home = tmp_path / "apparatus_home"
    home.mkdir(exist_ok=True)
    env = dict(os.environ)
    env["APPARATUS_HOME"] = str(home)
    env["PYTHONUTF8"] = "1"
    return env


def _seed_workspace(tmp_path: Path, env: dict[str, str]) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    workspace = tmp_path / "workspace"
    result = _run_cli(["init", str(workspace)], env=env)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")

    (workspace / "Library" / "guide.md").write_text(
        "# Deployment Protocol\n\n"
        "Apparatus stores durable Memory records as plain Markdown files with YAML frontmatter.\n"
        "Deployments always verify checksums before switching the active release pointer.\n",
        encoding="utf-8",
    )
    (workspace / "Goals" / "ship-mcp.md").write_text(
        "---\n"
        "schema: apparatus/goal@v0\n"
        "title: Ship local tool server\n"
        "owner: maintainer\n"
        "status: active\n"
        "done-when: Read-only MCP tests pass\n"
        "next-action: Run pytest\n"
        "---\n"
        "Goal details.\n",
        encoding="utf-8",
    )

    task = start_task(workspace, save_memory=True)
    try:
        res = _run_cli(
            [
                "--task",
                task.task_id,
                "memory",
                "add-fact",
                str(workspace),
                "--title",
                "Release Rule",
                "--body",
                "Checksums must match before promoting a build.",
            ],
            env=env,
        )
        assert res.returncode == 0, res.stderr.decode("utf-8", errors="replace")

        res = _run_cli(
            [
                "--task",
                task.task_id,
                "library",
                "ingest",
                str(workspace),
            ],
            env=env,
        )
        assert res.returncode == 0, res.stderr.decode("utf-8", errors="replace")

        res = _run_cli(
            [
                "--task",
                task.task_id,
                "snapshot",
                str(workspace),
                "--label",
                "seeded",
            ],
            env=env,
        )
        assert res.returncode == 0, res.stderr.decode("utf-8", errors="replace")
    finally:
        set_no_memory(workspace, task.task_id)
    return workspace


def test_no_networking_imports() -> None:
    forbidden = {
        "socket",
        "http",
        "urllib",
        "ssl",
        "asyncio",
        "websockets",
        "requests",
        "httpx",
        "aiohttp",
        "mcp",
        "ftplib",
        "smtplib",
        "poplib",
        "imaplib",
        "telnetlib",
        "xmlrpc",
    }
    for module in (mcp_protocol, mcp_command):
        source = Path(module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        found: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module.split(".")[0])
        assert not (found & forbidden), f"{module.__name__} imported networking modules: {found & forbidden}"


def test_stdio_lifecycle_and_tools_list(tmp_path: Path) -> None:
    env = _make_env(tmp_path)
    workspace = tmp_path / "workspace"
    assert _run_cli(["init", str(workspace)], env=env).returncode == 0

    stream = b"".join(
        [
            _rpc("ping", 1),
            _rpc("initialize", 2, _init_params()),
            _rpc("notifications/initialized"),
            _rpc("tools/list", 3),
            _rpc("ping", 4),
        ]
    )
    proc = _run_cli(["mcp", "serve", str(workspace)], env=env, stdin_bytes=stream)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")

    responses = _decode_lines(proc.stdout)
    assert [r["id"] for r in responses] == [1, 2, 3, 4]
    assert responses[0]["result"] == {}

    init_res = responses[1]["result"]
    assert init_res["protocolVersion"] == "2025-11-25"
    assert init_res["capabilities"] == {"tools": {}}
    assert init_res["serverInfo"]["name"] == "apparatus"

    tools = responses[2]["result"]["tools"]
    assert [t["name"] for t in tools] == ["library_recall", "memory_recall", "resume_brief"]
    for tool in tools:
        assert tool["annotations"] == {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
        assert "harness" not in tool["description"].lower()

    assert responses[3]["result"] == {}


def test_console_script_entry_point_wiring(tmp_path: Path) -> None:
    exe = shutil.which("apparatus")
    if exe is None:
        candidate = Path(sys.executable).parent / ("apparatus.exe" if sys.platform == "win32" else "apparatus")
        if not candidate.exists():
            pytest.skip("apparatus console script not on PATH")
        exe = str(candidate)
    env = _make_env(tmp_path)
    workspace = tmp_path / "workspace"
    assert _run_cli(["init", str(workspace)], env=env).returncode == 0

    proc = subprocess.run(
        [exe, "mcp", "serve", str(workspace)],
        input=_rpc("initialize", 1, _init_params()),
        capture_output=True,
        env=env,
        timeout=120,
    )
    assert proc.returncode == 0
    responses = _decode_lines(proc.stdout)
    assert responses[0]["result"]["protocolVersion"] == "2025-11-25"


def test_malformed_uninitialized_unknown_and_recovery(tmp_path: Path) -> None:
    env = _make_env(tmp_path)
    workspace = tmp_path / "workspace"
    assert _run_cli(["init", str(workspace)], env=env).returncode == 0

    stream = b"".join(
        [
            _rpc("tools/list", 1),
            b"{broken json\n",
            b"\xff\xfe\n",
            b'[{"jsonrpc":"2.0","id":9,"method":"ping"}]\n',
            _rpc("initialize", 2, _init_params()),
            _rpc("initialize", 3, _init_params()),
            _rpc("unknown/method", 4),
            _rpc("tools/call", 5, {"name": "nonexistent_tool", "arguments": {}}),
            _rpc("ping", 6),
        ]
    )
    proc = _run_cli(["mcp", "serve", str(workspace)], env=env, stdin_bytes=stream)
    assert proc.returncode == 0
    responses = _decode_lines(proc.stdout)
    codes = [(r.get("id"), r.get("error", {}).get("code")) for r in responses]
    assert codes == [
        (1, -32600),
        (None, -32700),
        (None, -32700),
        (None, -32600),
        (2, None),
        (3, -32600),
        (4, -32601),
        (5, -32602),
        (6, None),
    ]
    assert responses[-1]["result"] == {}


def test_request_and_result_byte_caps() -> None:
    oversized_req = b'{"jsonrpc":"2.0","id":1,"method":"ping","params":{"pad":"' + (b"x" * 70_000) + b'"}}\n'
    stdin = io.BytesIO(oversized_req + _rpc("ping", 2))
    stdout = io.BytesIO()
    server = mcp_protocol.McpServer(
        server_name="apparatus",
        server_version="0.0.3",
        tools=[
            mcp_protocol.ToolDefinition(
                name="huge",
                description="Produces an oversized payload.",
                input_schema={"type": "object", "properties": {}},
                handler=lambda _args: {"blob": "a" * (mcp_protocol.MAX_RESULT_BYTES + 1024)},
                annotations={"readOnlyHint": True},
            )
        ],
    )
    assert server.serve_stdio(stdin=stdin, stdout=stdout) == 0
    first, second = _decode_lines(stdout.getvalue())
    assert first["error"]["code"] == -32600
    assert second["id"] == 2
    assert second["result"] == {}

    # Now test oversized result cap on tools/call.
    stdin2 = io.BytesIO(
        _rpc("initialize", 1, _init_params())
        + _rpc("tools/call", 2, {"name": "huge", "arguments": {}})
        + _rpc("ping", 3)
    )
    stdout2 = io.BytesIO()
    server2 = mcp_protocol.McpServer(
        server_name="apparatus",
        server_version="0.0.3",
        tools=server._tools.values() if False else list(server._tools.values()),
    )
    assert server2.serve_stdio(stdin=stdin2, stdout=stdout2) == 0
    raw_lines = [line for line in stdout2.getvalue().splitlines() if line]
    assert all(len(line) <= mcp_protocol.MAX_RESULT_BYTES for line in raw_lines)
    res_huge = json.loads(raw_lines[1].decode("utf-8"))
    assert res_huge["result"]["isError"] is True
    assert "result_too_large" in res_huge["result"]["content"][0]["text"]
    assert json.loads(raw_lines[2].decode("utf-8"))["result"] == {}


def test_task_flag_missing_subcommand_and_legacy_workspace_rejected(tmp_path: Path) -> None:
    env = _make_env(tmp_path)
    workspace = tmp_path / "workspace"
    assert _run_cli(["init", str(workspace)], env=env).returncode == 0

    # --task rejected before retention opens, with zero stdout bytes.
    task_flag = _run_cli(
        ["--task", "00000000-0000-4000-8000-000000000000", "mcp", "serve", str(workspace)],
        env=env,
    )
    assert task_flag.returncode == 2
    assert task_flag.stdout == b""
    assert b"--task" in task_flag.stderr

    # Missing subcommand exits 2 with zero stdout.
    no_sub = _run_cli(["mcp"], env=env)
    assert no_sub.returncode == 2
    assert no_sub.stdout == b""

    # Direct mcp_command.run call with --task also exits 2 without writing stdout.
    assert mcp_command.run(
        argparse.Namespace(workspace=str(workspace), task="abc")
    ) == 2

    # Legacy workspace lacking System/workspace.yaml and System/recovery exits 2 with init guidance.
    shutil.rmtree(workspace / "System" / "recovery", ignore_errors=True)
    (workspace / "System" / "workspace.yaml").unlink()
    legacy = _run_cli(["mcp", "serve", str(workspace)], env=env)
    assert legacy.returncode == 2
    assert legacy.stdout == b""
    assert b"apparatus init" in legacy.stderr


def test_read_only_immutability_and_grounded_recall(tmp_path: Path) -> None:
    env = _make_env(tmp_path)
    workspace = _seed_workspace(tmp_path, env)
    home = Path(env["APPARATUS_HOME"])

    ws_before = _tree_snapshot(workspace)
    home_before = _tree_snapshot(home)

    stream = b"".join(
        [
            _rpc("initialize", 1, _init_params()),
            _rpc("notifications/initialized"),
            _rpc("tools/call", 2, {"name": "library_recall", "arguments": {"question": "checksums deployment"}}),
            _rpc("tools/call", 3, {"name": "library_recall", "arguments": {"question": "quantum marsupials"}}),
            _rpc("tools/call", 4, {"name": "memory_recall", "arguments": {"query": "Checksums"}}),
            _rpc("tools/call", 5, {"name": "memory_recall", "arguments": {"query": "zebra_missing"}}),
            _rpc("tools/call", 6, {"name": "resume_brief", "arguments": {}}),
        ]
    )
    proc = _run_cli(["mcp", "serve", str(workspace)], env=env, stdin_bytes=stream)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")

    assert _tree_snapshot(workspace) == ws_before
    assert _tree_snapshot(home) == home_before

    responses = _decode_lines(proc.stdout)
    lib_hit = responses[1]["result"]
    assert lib_hit["isError"] is False
    assert lib_hit["structuredContent"]["status"] == "grounded"
    assert lib_hit["structuredContent"]["evidence"]
    assert lib_hit["structuredContent"]["coverage"]["status"] == "complete"
    assert json.loads(lib_hit["content"][0]["text"]) == lib_hit["structuredContent"]

    lib_miss = responses[2]["result"]
    assert lib_miss["isError"] is False
    assert lib_miss["structuredContent"]["status"] == "abstained"
    assert lib_miss["structuredContent"]["evidence"] == []
    assert lib_miss["structuredContent"]["coverage"]["status"] == "complete"

    mem_hit = responses[3]["result"]
    assert mem_hit["isError"] is False
    assert mem_hit["structuredContent"]["status"] == "matched"
    assert len(mem_hit["structuredContent"]["results"]) >= 1

    mem_miss = responses[4]["result"]
    assert mem_miss["isError"] is False
    assert mem_miss["structuredContent"]["status"] == "no-match"
    assert mem_miss["structuredContent"]["results"] == []

    brief = responses[5]["result"]
    assert brief["isError"] is False
    assert brief["structuredContent"]["status"] == "complete"
    assert brief["structuredContent"]["partial"] is False
    assert brief["structuredContent"]["selection"] == "direct work area"

    cli_resume = _run_cli(["resume", str(workspace)], env=env)
    assert cli_resume.returncode == 0
    assert (
        brief["structuredContent"]["text"]
        == cli_resume.stdout.decode("utf-8").replace("\r\n", "\n").rstrip("\n")
    )


def test_distinct_domain_states_and_invalid_args(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _make_env(tmp_path)
    workspace = tmp_path / "workspace"
    assert _run_cli(["init", str(workspace)], env=env).returncode == 0

    # 1. no_extractions on freshly initialized workspace.
    stream_no_ext = b"".join(
        [
            _rpc("initialize", 1, _init_params()),
            _rpc("tools/call", 2, {"name": "library_recall", "arguments": {"question": "anything"}}),
            _rpc("tools/call", 3, {"name": "library_recall", "arguments": {"question": "   "}}),
            _rpc("tools/call", 4, {"name": "library_recall", "arguments": {"question": "ok", "limit": True}}),
            _rpc("tools/call", 5, {"name": "memory_recall", "arguments": {"query": "ok", "limit": 99}}),
            _rpc("tools/call", 6, {"name": "resume_brief", "arguments": {"unexpected": 1}}),
        ]
    )
    proc1 = _run_cli(["mcp", "serve", str(workspace)], env=env, stdin_bytes=stream_no_ext)
    assert proc1.returncode == 0
    res1 = _decode_lines(proc1.stdout)
    assert res1[1]["result"]["isError"] is False
    assert res1[1]["result"]["structuredContent"]["status"] == "no_extractions"
    for idx in (2, 3, 4, 5):
        assert res1[idx]["result"]["isError"] is True

    # 2. feature_disabled when library_indexing is off.
    import yaml

    profile_path = workspace / "System" / "profile.yaml"
    profile_text = profile_path.read_text(encoding="utf-8")
    profile_data = yaml.safe_load(profile_text)
    profile_data["features"] = {
        "library_indexing": False,
        "snapshots": True,
        "ignore_rules": True,
    }
    profile_path.write_text(yaml.safe_dump(profile_data, sort_keys=False), encoding="utf-8")
    proc2 = _run_cli(
        ["mcp", "serve", str(workspace)],
        env=env,
        stdin_bytes=_rpc("initialize", 1, _init_params())
        + _rpc("tools/call", 2, {"name": "library_recall", "arguments": {"question": "anything"}}),
    )
    assert _decode_lines(proc2.stdout)[1]["result"]["structuredContent"]["status"] == "feature_disabled"
    profile_path.write_text(profile_text, encoding="utf-8")

    # 3. invalid_extractions when an existing extraction JSON in cache is corrupt.
    seeded = _seed_workspace(tmp_path / "seeded_sub", env)
    monkeypatch.setenv("APPARATUS_HOME", env["APPARATUS_HOME"])
    ext_file = library_cache_root(seeded) / "extractions" / "guide.md.json"
    assert ext_file.is_file()
    saved_ext = ext_file.read_bytes()
    ext_file.write_bytes(b"{corrupt")
    proc3 = _run_cli(
        ["mcp", "serve", str(seeded)],
        env=env,
        stdin_bytes=_rpc("initialize", 1, _init_params())
        + _rpc("tools/call", 2, {"name": "library_recall", "arguments": {"question": "anything"}}),
    )
    res3 = _decode_lines(proc3.stdout)[1]["result"]
    assert res3["isError"] is False
    assert res3["structuredContent"]["status"] == "invalid_extractions"
    ext_file.write_bytes(saved_ext)

    # 4. fts_unavailable simulated in-process cleanly.
    monkeypatch.setattr(index, "retrieve", lambda *_a, **_kw: (_ for _ in ()).throw(index.FtsUnavailable("no fts5")))
    stdin = io.BytesIO(
        _rpc("initialize", 1, _init_params())
        + _rpc("tools/call", 2, {"name": "library_recall", "arguments": {"question": "checksums"}})
    )
    stdout = io.BytesIO()
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=stdin))
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(buffer=stdout))
    assert mcp_command.run(argparse.Namespace(workspace=str(seeded), task=None)) == 0
    fts_res = _decode_lines(stdout.getvalue())[1]["result"]
    assert fts_res["isError"] is False
    assert fts_res["structuredContent"]["status"] == "fts_unavailable"

    # 5. partial Library coverage vs complete no-match.
    monkeypatch.undo()
    (seeded / "Library" / "extra_uningested.md").write_text(
        "# Extra\nAdded after ingest so coverage is partial.\n",
        encoding="utf-8",
    )
    proc_partial = _run_cli(
        ["mcp", "serve", str(seeded)],
        env=env,
        stdin_bytes=_rpc("initialize", 1, _init_params())
        + _rpc("tools/call", 2, {"name": "library_recall", "arguments": {"question": "zebra"}}),
    )
    partial_res = _decode_lines(proc_partial.stdout)[1]["result"]
    assert partial_res["isError"] is False
    assert partial_res["structuredContent"]["status"] == "abstained"
    assert partial_res["structuredContent"]["coverage"]["status"] == "partial"

    # 6. memory_recall unavailable & 7. resume_brief partial on corrupt records.
    (seeded / "Memory" / "Facts" / "corrupt.md").write_text("---\n[broken yaml\n", encoding="utf-8")
    (seeded / "Goals" / "corrupt.md").write_text("---\n[broken yaml\n", encoding="utf-8")
    proc_corrupt = _run_cli(
        ["mcp", "serve", str(seeded)],
        env=env,
        stdin_bytes=(
            _rpc("initialize", 1, _init_params())
            + _rpc("tools/call", 2, {"name": "memory_recall", "arguments": {"query": "anything"}})
            + _rpc("tools/call", 3, {"name": "resume_brief", "arguments": {}})
        ),
    )
    corrupt_res = _decode_lines(proc_corrupt.stdout)
    assert corrupt_res[1]["result"]["isError"] is False
    assert corrupt_res[1]["result"]["structuredContent"]["status"] == "unavailable"
    assert corrupt_res[2]["result"]["isError"] is False
    assert corrupt_res[2]["result"]["structuredContent"]["status"] == "partial"
    assert corrupt_res[2]["result"]["structuredContent"]["partial"] is True


def test_bound_project_resolution_and_mid_session_drift_rejection(tmp_path: Path) -> None:
    env = _make_env(tmp_path)
    workspace = tmp_path / "workspace"
    assert _run_cli(["init", str(workspace)], env=env).returncode == 0
    project = workspace / "Projects" / "demo"
    project.mkdir(parents=True)
    assert _run_cli(["project", "bind", str(project), "--workspace", str(workspace)], env=env).returncode == 0

    # Verify linked work-area resolution via project path.
    proc = _run_cli(
        ["mcp", "serve", str(project)],
        env=env,
        stdin_bytes=(
            _rpc("initialize", 1, _init_params())
            + _rpc("tools/call", 2, {"name": "resume_brief", "arguments": {}})
        ),
    )
    assert proc.returncode == 0
    res = _decode_lines(proc.stdout)
    assert res[1]["result"]["structuredContent"]["selection"] == "linked work area"

    # Verify mid-session drift when binding file changes between calls inside one session.
    stdout = io.BytesIO()
    stdin = io.BytesIO(
        _rpc("initialize", 1, _init_params())
        + _rpc("tools/call", 2, {"name": "resume_brief", "arguments": {}})
        + _rpc("tools/call", 3, {"name": "resume_brief", "arguments": {}})
    )
    binding_dir = project / ".apparatus"
    original_stdin, original_stdout = sys.stdin, sys.stdout
    try:
        class _MutatingStream:
            def __init__(self) -> None:
                self._chunks = [
                    _rpc("initialize", 1, _init_params()),
                    _rpc("tools/call", 2, {"name": "resume_brief", "arguments": {}}),
                    _rpc("tools/call", 3, {"name": "resume_brief", "arguments": {}}),
                ]
                self._index = 0

            def readline(self, size: int = -1) -> bytes:
                if self._index == 2 and binding_dir.exists():
                    shutil.rmtree(binding_dir)
                if self._index >= len(self._chunks):
                    return b""
                chunk = self._chunks[self._index]
                self._index += 1
                return chunk

        sys.stdin = SimpleNamespace(buffer=_MutatingStream())
        sys.stdout = SimpleNamespace(buffer=stdout)
        old_home = os.environ.get("APPARATUS_HOME")
        os.environ["APPARATUS_HOME"] = env["APPARATUS_HOME"]
        try:
            rc = cli.main(["mcp", "serve", str(project)])
        finally:
            if old_home is None:
                os.environ.pop("APPARATUS_HOME", None)
            else:
                os.environ["APPARATUS_HOME"] = old_home
    finally:
        sys.stdin, sys.stdout = original_stdin, original_stdout

    assert rc == 0
    drift_res = _decode_lines(stdout.getvalue())
    assert drift_res[1]["result"]["isError"] is False
    assert drift_res[2]["result"]["isError"] is True
    assert "changed" in drift_res[2]["result"]["content"][0]["text"].lower()


def test_stdout_print_redirected_to_stderr(tmp_path: Path) -> None:
    server = mcp_protocol.McpServer(
        server_name="apparatus",
        server_version="0.0.3",
        tools=[
            mcp_protocol.ToolDefinition(
                name="noisy",
                description="Prints accidentally.",
                input_schema={"type": "object", "properties": {}},
                handler=lambda _a: (print("accidental print"), {"ok": True})[1],
                annotations={"readOnlyHint": True},
            )
        ],
    )
    stdin = io.BytesIO(_rpc("initialize", 1, _init_params()) + _rpc("tools/call", 2, {"name": "noisy", "arguments": {}}))
    stdout = io.BytesIO()
    captured_err = io.StringIO()
    from contextlib import redirect_stdout

    old_err = sys.stderr
    sys.stderr = captured_err
    try:
        with redirect_stdout(sys.stderr):
            assert server.serve_stdio(stdin=stdin, stdout=stdout) == 0
    finally:
        sys.stderr = old_err

    lines = _decode_lines(stdout.getvalue())
    assert len(lines) == 2
    assert lines[1]["result"]["structuredContent"] == {"ok": True}
    assert "accidental print" in captured_err.getvalue()


def test_raw_exception_text_and_paths_do_not_leak(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    env = _make_env(tmp_path)
    workspace = tmp_path / "workspace"
    assert _run_cli(["init", str(workspace)], env=env).returncode == 0
    monkeypatch.setenv("APPARATUS_HOME", env["APPARATUS_HOME"])

    secret_token = "SECRET_ERRNO_SQLITE_YAML_TEXT"
    secret_path = "/private/secret/host/path/file.db"

    # 1. Startup OSError must not leak errno text or absolute paths to stderr.
    monkeypatch.setattr(
        mcp_command,
        "read_layout",
        lambda _ws: (_ for _ in ()).throw(OSError(13, secret_token, secret_path)),
    )
    assert mcp_command.run(argparse.Namespace(workspace=str(workspace), task=None)) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert secret_token not in captured.err
    assert secret_path not in captured.err
    monkeypatch.undo()

    # 2. Tool execution OSError/ValueError must not leak into JSON-RPC tool error payloads.
    monkeypatch.setenv("APPARATUS_HOME", env["APPARATUS_HOME"])
    monkeypatch.setattr(
        mcp_command.recall_engine,
        "recall",
        lambda *_a, **_kw: (_ for _ in ()).throw(OSError(2, secret_token, secret_path)),
    )
    monkeypatch.setattr(
        mcp_command,
        "recall_memory",
        lambda *_a, **_kw: (_ for _ in ()).throw(ValueError(f"{secret_token}:{secret_path}")),
    )
    monkeypatch.setattr(
        mcp_command,
        "assemble_brief",
        lambda *_a, **_kw: (_ for _ in ()).throw(OSError(5, secret_token, secret_path)),
    )
    stdin = io.BytesIO(
        _rpc("initialize", 1, _init_params())
        + _rpc("tools/call", 2, {"name": "library_recall", "arguments": {"question": "x"}})
        + _rpc("tools/call", 3, {"name": "memory_recall", "arguments": {"query": "x"}})
        + _rpc("tools/call", 4, {"name": "resume_brief", "arguments": {}})
    )
    stdout = io.BytesIO()
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=stdin))
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(buffer=stdout))
    assert mcp_command.run(argparse.Namespace(workspace=str(workspace), task=None)) == 0
    captured = capsys.readouterr()
    raw_out = stdout.getvalue().decode("utf-8")
    assert secret_token not in raw_out and secret_path not in raw_out
    assert secret_token not in captured.err and secret_path not in captured.err
    responses = _decode_lines(stdout.getvalue())
    for idx in (1, 2, 3):
        assert responses[idx]["result"]["isError"] is True
