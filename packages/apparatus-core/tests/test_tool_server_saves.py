"""Tests for opt-in Memory save tools on the local MCP tool server (PR-78)."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import UUID

import pytest
import yaml

from apparatus_core import mcp_protocol
from apparatus_core.commands import mcp as mcp_command
from apparatus_core.commands import memory as memory_command
from apparatus_core.commands import task as task_command
from apparatus_core.fs_transactions import WorkspaceAnchor


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


def _make_env(tmp_path: Path) -> dict[str, str]:
    home = tmp_path / "apparatus_home"
    home.mkdir(exist_ok=True)
    env = dict(os.environ)
    env["APPARATUS_HOME"] = str(home)
    env["PYTHONUTF8"] = "1"
    return env


def _tree_snapshot(root: Path) -> dict[str, tuple[int, str]]:
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


def _init_workspace(tmp_path: Path, name: str, env: dict[str, str]) -> Path:
    workspace = tmp_path / name
    proc = _run_cli(["init", str(workspace)], env=env)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")
    return workspace


def _normalized_receipts(root: Path, *, exclude: set[str] | None = None) -> list[tuple[str, bytes]]:
    receipts_dir = root / "System" / "receipts"
    if not receipts_dir.is_dir():
        return []
    skip = exclude or set()
    items: list[tuple[str, bytes]] = []
    for path in sorted(receipts_dir.glob("*.md")):
        if path.name in skip:
            continue
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        # Normalize the per-run UTC timestamp line so two equal saves can be compared byte-for-byte.
        normalized = "\n".join(
            "timestamp: <normalized>" if line.startswith("timestamp: ") else line
            for line in text.splitlines()
        )
        suffix = path.name.split("-", 4)[-1]
        items.append((suffix, normalized.encode("utf-8")))
    return items


def test_without_flag_save_tools_are_omitted_and_rejected(tmp_path: Path) -> None:
    env = _make_env(tmp_path)
    workspace = _init_workspace(tmp_path, "ws", env)
    home = Path(env["APPARATUS_HOME"])
    ws_before = _tree_snapshot(workspace)
    home_before = _tree_snapshot(home)

    stream = b"".join(
        [
            _rpc("initialize", 1, _init_params()),
            _rpc("notifications/initialized"),
            _rpc("tools/list", 2),
            _rpc("tools/call", 3, {"name": "task_start", "arguments": {}}),
            _rpc("tools/call", 4, {"name": "task_no_memory", "arguments": {"task_id": "x"}}),
            _rpc("tools/call", 5, {"name": "memory_save_fact", "arguments": {"task_id": "x", "title": "t", "body": "b"}}),
            _rpc("tools/call", 6, {"name": "memory_save_person", "arguments": {"task_id": "x", "name": "n", "body": "b"}}),
            _rpc("tools/call", 7, {"name": "memory_save_decision", "arguments": {"task_id": "x", "title": "t", "date": "2026-11-13", "body": "b"}}),
        ]
    )
    proc = _run_cli(["mcp", "serve", str(workspace)], env=env, stdin_bytes=stream)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")
    assert _tree_snapshot(workspace) == ws_before
    assert _tree_snapshot(home) == home_before

    responses = _decode_lines(proc.stdout)
    assert [t["name"] for t in responses[1]["result"]["tools"]] == [
        "library_recall",
        "memory_recall",
        "resume_brief",
    ]
    for resp in responses[2:]:
        assert resp["error"]["code"] == -32602


def test_with_flag_tool_listing_and_descriptions(tmp_path: Path) -> None:
    env = _make_env(tmp_path)
    workspace = _init_workspace(tmp_path, "ws", env)

    stream = b"".join(
        [
            _rpc("initialize", 1, _init_params()),
            _rpc("notifications/initialized"),
            _rpc("tools/list", 2),
        ]
    )
    proc = _run_cli(["mcp", "serve", str(workspace), "--memory-saves"], env=env, stdin_bytes=stream)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")
    tools = _decode_lines(proc.stdout)[1]["result"]["tools"]
    assert [t["name"] for t in tools] == [
        "library_recall",
        "memory_recall",
        "resume_brief",
        "task_start",
        "task_no_memory",
        "memory_save_fact",
        "memory_save_person",
        "memory_save_decision",
    ]

    by_name = {tool["name"]: tool for tool in tools}
    for tool in tools:
        desc_lower = tool["description"].lower()
        assert "harness" not in desc_lower
        assert "agent" not in desc_lower
    for save_name in ("memory_save_fact", "memory_save_person", "memory_save_decision"):
        desc = by_name[save_name]["description"].lower()
        assert "explicitly asks" in desc
        assert "do not invent" in desc
        assert "unrelated conversation content" in desc
        assert by_name[save_name]["annotations"]["readOnlyHint"] is False


def test_save_tools_match_cli_verbs_byte_for_byte(tmp_path: Path) -> None:
    env = _make_env(tmp_path)
    ws_mcp = _init_workspace(tmp_path, "ws-mcp", env)
    ws_cli = _init_workspace(tmp_path, "ws-cli", env)
    mcp_init_receipts = {p.name for p in (ws_mcp / "System" / "receipts").glob("*.md")}
    cli_init_receipts = {p.name for p in (ws_cli / "System" / "receipts").glob("*.md")}

    # 1. Start a saving task via MCP and save all three record kinds.
    start_proc = _run_cli(
        ["mcp", "serve", str(ws_mcp), "--memory-saves"],
        env=env,
        stdin_bytes=(
            _rpc("initialize", 1, _init_params())
            + _rpc("tools/call", 2, {"name": "task_start", "arguments": {}})
        ),
    )
    assert start_proc.returncode == 0
    start_res = _decode_lines(start_proc.stdout)[1]["result"]
    assert start_res["isError"] is False
    mcp_task = start_res["structuredContent"]
    assert mcp_task["memory"] == "save"
    assert UUID(mcp_task["task_id"]).version == 4
    assert json.loads(start_res["content"][0]["text"]) == mcp_task

    fact_args = {
        "task_id": mcp_task["task_id"],
        "title": "Build Window",
        "body": "Freeze starts Tuesday at 18:00 UTC.\nSource: release checklist.",
    }
    person_args = {
        "task_id": mcp_task["task_id"],
        "name": "Morgan Rivera",
        "role": "Release coordinator",
        "body": "Coordinates checksum checks.",
    }
    decision_args = {
        "task_id": mcp_task["task_id"],
        "title": "Use SHA-256 manifests",
        "date": "2026-11-13",
        "body": "Use SHA-256 for every artifact because SHA-1 is retired.",
    }

    save_proc = _run_cli(
        ["mcp", "serve", str(ws_mcp), "--memory-saves"],
        env=env,
        stdin_bytes=(
            _rpc("initialize", 1, _init_params())
            + _rpc("tools/call", 2, {"name": "memory_save_fact", "arguments": fact_args})
            + _rpc("tools/call", 3, {"name": "memory_save_person", "arguments": person_args})
            + _rpc("tools/call", 4, {"name": "memory_save_decision", "arguments": decision_args})
        ),
    )
    assert save_proc.returncode == 0
    save_responses = _decode_lines(save_proc.stdout)[1:]

    # 2. Run equivalent CLI verbs on ws_cli.
    cli_task_proc = _run_cli(["task", "start", str(ws_cli)], env=env)
    assert cli_task_proc.returncode == 0
    cli_task = json.loads(cli_task_proc.stdout.decode("utf-8"))
    assert cli_task["memory"] == "save"

    cli_fact = _run_cli(
        [
            "--task",
            cli_task["task_id"],
            "memory",
            "add-fact",
            str(ws_cli),
            "--title",
            fact_args["title"],
            "--body",
            fact_args["body"],
        ],
        env=env,
    )
    cli_person = _run_cli(
        [
            "--task",
            cli_task["task_id"],
            "memory",
            "add-person",
            str(ws_cli),
            "--name",
            person_args["name"],
            "--role",
            person_args["role"],
            "--body",
            person_args["body"],
        ],
        env=env,
    )
    cli_decision = _run_cli(
        [
            "--task",
            cli_task["task_id"],
            "memory",
            "add-decision",
            str(ws_cli),
            "--title",
            decision_args["title"],
            "--date",
            decision_args["date"],
            "--body",
            decision_args["body"],
        ],
        env=env,
    )
    for cli_res, mcp_res in zip((cli_fact, cli_person, cli_decision), save_responses):
        assert cli_res.returncode == 0
        payload = mcp_res["result"]["structuredContent"]
        assert mcp_res["result"]["isError"] is False
        assert payload["status"] == "saved"
        assert payload["redactions"] == {"total": 0, "classes": [], "counts": {}}
        assert json.loads(mcp_res["result"]["content"][0]["text"]) == payload

        rel = payload["record_path"]
        cli_lines = cli_res.stdout.decode("utf-8").replace("\r\n", "\n").splitlines()
        assert cli_lines[:2] == ["Memory record saved.", f"Record: {rel}"]
        assert (ws_mcp / rel).read_bytes() == (ws_cli / rel).read_bytes()

    assert _normalized_receipts(ws_mcp, exclude=mcp_init_receipts) == _normalized_receipts(
        ws_cli, exclude=cli_init_receipts
    )


def test_no_save_and_task_no_memory_suppress_writes_cleanly(tmp_path: Path) -> None:
    env = _make_env(tmp_path)
    workspace = _init_workspace(tmp_path, "ws", env)

    # Start saving task, save one fact, opt out via task_no_memory, then attempt all 3 saves.
    init_proc = _run_cli(
        ["mcp", "serve", str(workspace), "--memory-saves"],
        env=env,
        stdin_bytes=(
            _rpc("initialize", 1, _init_params())
            + _rpc("tools/call", 2, {"name": "task_start", "arguments": {"memory": "save"}})
            + _rpc("tools/call", 3, {"name": "task_start", "arguments": {"memory": "no-save"}})
        ),
    )
    assert init_proc.returncode == 0
    init_lines = _decode_lines(init_proc.stdout)
    saving_id = init_lines[1]["result"]["structuredContent"]["task_id"]
    nosave_id = init_lines[2]["result"]["structuredContent"]["task_id"]
    assert init_lines[1]["result"]["structuredContent"]["memory"] == "save"
    assert init_lines[2]["result"]["structuredContent"]["memory"] == "no-save"

    # Save one fact under saving_id, then flip saving_id to no-save.
    flip_proc = _run_cli(
        ["mcp", "serve", str(workspace), "--memory-saves"],
        env=env,
        stdin_bytes=(
            _rpc("initialize", 1, _init_params())
            + _rpc(
                "tools/call",
                2,
                {
                    "name": "memory_save_fact",
                    "arguments": {
                        "task_id": saving_id,
                        "title": "Before Opt Out",
                        "body": "Saved before opting out.",
                    },
                },
            )
            + _rpc("tools/call", 3, {"name": "task_no_memory", "arguments": {"task_id": saving_id}})
        ),
    )
    assert flip_proc.returncode == 0
    flip_lines = _decode_lines(flip_proc.stdout)
    assert flip_lines[1]["result"]["structuredContent"]["status"] == "saved"
    assert flip_lines[2]["result"]["structuredContent"] == {
        "task_id": saving_id,
        "memory": "no-save",
    }

    before = _tree_snapshot(workspace)

    # Attempt all three saves under both nosave_id and the opted-out saving_id.
    calls = []
    req_id = 2
    for tid in (nosave_id, saving_id):
        calls.extend(
            [
                _rpc("tools/call", req_id, {"name": "memory_save_fact", "arguments": {"task_id": tid, "title": "Blocked Fact", "body": "Do not write."}}),
                _rpc("tools/call", req_id + 1, {"name": "memory_save_person", "arguments": {"task_id": tid, "name": "Blocked Person", "body": "Do not write."}}),
                _rpc("tools/call", req_id + 2, {"name": "memory_save_decision", "arguments": {"task_id": tid, "title": "Blocked Decision", "date": "2026-11-13", "body": "Do not write."}}),
            ]
        )
        req_id += 3

    suppressed_proc = _run_cli(
        ["mcp", "serve", str(workspace), "--memory-saves"],
        env=env,
        stdin_bytes=_rpc("initialize", 1, _init_params()) + b"".join(calls),
    )
    assert suppressed_proc.returncode == 0
    assert _tree_snapshot(workspace) == before

    for resp in _decode_lines(suppressed_proc.stdout)[1:]:
        assert resp["result"]["isError"] is False
        assert resp["result"]["structuredContent"] == {
            "status": "not_saved",
            "reason": "This task does not save new Memory or setup answers.",
        }

    # Verify previously saved record stayed in place.
    assert (workspace / "Memory" / "Facts" / "before-opt-out.md").is_file()


def test_credential_redaction_matches_verb_and_reports_counts_only(tmp_path: Path) -> None:
    env = _make_env(tmp_path)
    ws_mcp = _init_workspace(tmp_path, "ws-mcp", env)
    ws_cli = _init_workspace(tmp_path, "ws-cli", env)
    mcp_init_receipts = {p.name for p in (ws_mcp / "System" / "receipts").glob("*.md")}
    cli_init_receipts = {p.name for p in (ws_cli / "System" / "receipts").glob("*.md")}

    secret_pw = "synthetic-password-secret-xyz"
    secret_key = "synthetic-apikey-secret-abc"
    body = f"Rotate password={secret_pw} and api_key={secret_key} before deploy."

    mcp_proc = _run_cli(
        ["mcp", "serve", str(ws_mcp), "--memory-saves"],
        env=env,
        stdin_bytes=(
            _rpc("initialize", 1, _init_params())
            + _rpc("tools/call", 2, {"name": "task_start", "arguments": {}})
        ),
    )
    tid = _decode_lines(mcp_proc.stdout)[1]["result"]["structuredContent"]["task_id"]

    save_proc = _run_cli(
        ["mcp", "serve", str(ws_mcp), "--memory-saves"],
        env=env,
        stdin_bytes=(
            _rpc("initialize", 1, _init_params())
            + _rpc(
                "tools/call",
                2,
                {
                    "name": "memory_save_fact",
                    "arguments": {
                        "task_id": tid,
                        "title": "Credential Rotation",
                        "body": body,
                    },
                },
            )
        ),
    )
    assert save_proc.returncode == 0
    raw_out = save_proc.stdout.decode("utf-8")
    raw_err = save_proc.stderr.decode("utf-8")
    assert secret_pw not in raw_out and secret_key not in raw_out
    assert secret_pw not in raw_err and secret_key not in raw_err

    res = _decode_lines(save_proc.stdout)[1]["result"]
    assert res["isError"] is False
    payload = res["structuredContent"]
    assert payload["status"] == "saved"
    assert payload["redactions"] == {
        "total": 2,
        "classes": ["api-key", "password"],
        "counts": {"api-key": 1, "password": 1},
    }

    cli_tid = json.loads(_run_cli(["task", "start", str(ws_cli)], env=env).stdout)["task_id"]
    cli_proc = _run_cli(
        [
            "--task",
            cli_tid,
            "memory",
            "add-fact",
            str(ws_cli),
            "--title",
            "Credential Rotation",
            "--body",
            body,
        ],
        env=env,
    )
    assert cli_proc.returncode == 0
    rel = payload["record_path"]
    assert (ws_mcp / rel).read_bytes() == (ws_cli / rel).read_bytes()
    assert _normalized_receipts(ws_mcp, exclude=mcp_init_receipts) == _normalized_receipts(
        ws_cli, exclude=cli_init_receipts
    )


def test_invalid_inputs_and_missing_or_unknown_task_id_return_tool_error(tmp_path: Path) -> None:
    env = _make_env(tmp_path)
    workspace = _init_workspace(tmp_path, "ws", env)

    # Start one saving task in a first request, but do NOT reuse it automatically.
    task_proc = _run_cli(
        ["mcp", "serve", str(workspace), "--memory-saves"],
        env=env,
        stdin_bytes=(
            _rpc("initialize", 1, _init_params())
            + _rpc("tools/call", 2, {"name": "task_start", "arguments": {}})
        ),
    )
    valid_tid = _decode_lines(task_proc.stdout)[1]["result"]["structuredContent"]["task_id"]
    before = _tree_snapshot(workspace)

    unknown_uuid = "00000000-0000-4000-8000-000000000000"
    bad_calls = [
        ("task_start", {"memory": "maybe"}),
        ("task_start", {"extra": "nope"}),
        ("task_no_memory", {}),
        ("task_no_memory", {"task_id": "not-a-uuid"}),
        ("task_no_memory", {"task_id": unknown_uuid}),
        # Missing task_id even though valid_tid exists in workspace.
        ("memory_save_fact", {"title": "Missing task", "body": "Body"}),
        ("memory_save_fact", {"task_id": "", "title": "Empty task", "body": "Body"}),
        ("memory_save_fact", {"task_id": "not-a-uuid", "title": "Bad task", "body": "Body"}),
        ("memory_save_fact", {"task_id": unknown_uuid, "title": "Unknown task", "body": "Body"}),
        ("memory_save_fact", {"task_id": valid_tid, "title": "   ", "body": "Body"}),
        ("memory_save_person", {"task_id": valid_tid, "name": "", "body": "Body"}),
        ("memory_save_person", {"task_id": valid_tid, "name": "Person", "body": "Body", "role": 42}),
        ("memory_save_decision", {"task_id": valid_tid, "title": "Bad leap date", "date": "2026-02-29", "body": "Reason"}),
        ("memory_save_decision", {"task_id": valid_tid, "title": "Bad format", "date": "2026-2-03", "body": "Reason"}),
        ("memory_save_decision", {"task_id": valid_tid, "title": "Empty body", "date": "2026-11-13", "body": "  \n"}),
        ("memory_save_fact", {"task_id": valid_tid, "title": "Extra field", "body": "Body", "source": "x"}),
    ]
    frames = [_rpc("initialize", 1, _init_params())]
    for idx, (name, args) in enumerate(bad_calls, start=2):
        frames.append(_rpc("tools/call", idx, {"name": name, "arguments": args}))

    proc = _run_cli(
        ["mcp", "serve", str(workspace), "--memory-saves"],
        env=env,
        stdin_bytes=b"".join(frames),
    )
    assert proc.returncode == 0
    assert _tree_snapshot(workspace) == before

    for resp in _decode_lines(proc.stdout)[1:]:
        assert resp["result"]["isError"] is True


def test_legacy_private_profile_defaults_to_no_save_and_allows_explicit_save(tmp_path: Path) -> None:
    env = _make_env(tmp_path)
    workspace = _init_workspace(tmp_path, "ws", env)
    profile_path = workspace / "System" / "profile.yaml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["privacy_mode"] = "private"
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")

    # 1. Omitted memory uses legacy private default -> no-save.
    proc1 = _run_cli(
        ["mcp", "serve", str(workspace), "--memory-saves"],
        env=env,
        stdin_bytes=(
            _rpc("initialize", 1, _init_params())
            + _rpc("tools/call", 2, {"name": "task_start", "arguments": {}})
        ),
    )
    default_task = _decode_lines(proc1.stdout)[1]["result"]["structuredContent"]
    assert default_task["memory"] == "no-save"
    before = _tree_snapshot(workspace)

    proc2 = _run_cli(
        ["mcp", "serve", str(workspace), "--memory-saves"],
        env=env,
        stdin_bytes=(
            _rpc("initialize", 1, _init_params())
            + _rpc(
                "tools/call",
                2,
                {
                    "name": "memory_save_person",
                    "arguments": {
                        "task_id": default_task["task_id"],
                        "name": "Private Default Person",
                        "body": "Should not save.",
                    },
                },
            )
        ),
    )
    assert _tree_snapshot(workspace) == before
    assert _decode_lines(proc2.stdout)[1]["result"]["structuredContent"]["status"] == "not_saved"

    # 2. Explicit memory: "save" overrides private default, matching CLI --task behavior.
    proc3 = _run_cli(
        ["mcp", "serve", str(workspace), "--memory-saves"],
        env=env,
        stdin_bytes=(
            _rpc("initialize", 1, _init_params())
            + _rpc("tools/call", 2, {"name": "task_start", "arguments": {"memory": "save"}})
        ),
    )
    save_task = _decode_lines(proc3.stdout)[1]["result"]["structuredContent"]
    assert save_task["memory"] == "save"

    proc4 = _run_cli(
        ["mcp", "serve", str(workspace), "--memory-saves"],
        env=env,
        stdin_bytes=(
            _rpc("initialize", 1, _init_params())
            + _rpc(
                "tools/call",
                2,
                {
                    "name": "memory_save_person",
                    "arguments": {
                        "task_id": save_task["task_id"],
                        "name": "Explicit Save Person",
                        "body": "Contact explicit@example.invalid.",
                    },
                },
            )
        ),
    )
    res4 = _decode_lines(proc4.stdout)[1]["result"]
    assert res4["isError"] is False
    assert res4["structuredContent"]["status"] == "saved"
    assert (workspace / res4["structuredContent"]["record_path"]).is_file()


def test_concurrent_servers_preserve_all_records(tmp_path: Path) -> None:
    env = _make_env(tmp_path)
    workspace = _init_workspace(tmp_path, "ws", env)

    proc = _run_cli(
        ["mcp", "serve", str(workspace), "--memory-saves"],
        env=env,
        stdin_bytes=(
            _rpc("initialize", 1, _init_params())
            + _rpc("tools/call", 2, {"name": "task_start", "arguments": {"memory": "save"}})
            + _rpc("tools/call", 3, {"name": "task_start", "arguments": {"memory": "save"}})
        ),
    )
    lines = _decode_lines(proc.stdout)
    tid1 = lines[1]["result"]["structuredContent"]["task_id"]
    tid2 = lines[2]["result"]["structuredContent"]["task_id"]

    def run_save(tid: str, body: str) -> dict:
        child = _run_cli(
            ["mcp", "serve", str(workspace), "--memory-saves"],
            env=env,
            stdin_bytes=(
                _rpc("initialize", 1, _init_params())
                + _rpc(
                    "tools/call",
                    2,
                    {
                        "name": "memory_save_fact",
                        "arguments": {
                            "task_id": tid,
                            "title": "Concurrent Topic",
                            "body": body,
                        },
                    },
                )
            ),
        )
        assert child.returncode == 0
        return _decode_lines(child.stdout)[1]["result"]["structuredContent"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut1 = pool.submit(run_save, tid1, "Writer one payload.")
        fut2 = pool.submit(run_save, tid2, "Writer two payload.")
        res1 = fut1.result()
        res2 = fut2.result()

    assert res1["status"] == "saved" and res2["status"] == "saved"
    assert res1["record_path"] != res2["record_path"]
    assert {res1["record_path"], res2["record_path"]} == {
        "Memory/Facts/concurrent-topic.md",
        "Memory/Facts/concurrent-topic-2.md",
    }
    bodies = {
        (workspace / res1["record_path"]).read_text(encoding="utf-8"),
        (workspace / res2["record_path"]).read_text(encoding="utf-8"),
    }
    assert any("Writer one payload." in text for text in bodies)
    assert any("Writer two payload." in text for text in bodies)


def test_bound_project_saves_into_linked_work_area(tmp_path: Path) -> None:
    env = _make_env(tmp_path)
    workspace = _init_workspace(tmp_path, "ws", env)
    project = workspace / "Projects" / "demo"
    project.mkdir(parents=True)
    assert _run_cli(["project", "bind", str(project), "--workspace", str(workspace)], env=env).returncode == 0
    project_before = _tree_snapshot(project)

    proc = _run_cli(
        ["mcp", "serve", str(project), "--memory-saves"],
        env=env,
        stdin_bytes=(
            _rpc("initialize", 1, _init_params())
            + _rpc("tools/call", 2, {"name": "task_start", "arguments": {"memory": "save"}})
        ),
    )
    tid = _decode_lines(proc.stdout)[1]["result"]["structuredContent"]["task_id"]

    save_proc = _run_cli(
        ["mcp", "serve", str(project), "--memory-saves"],
        env=env,
        stdin_bytes=(
            _rpc("initialize", 1, _init_params())
            + _rpc(
                "tools/call",
                2,
                {
                    "name": "memory_save_fact",
                    "arguments": {
                        "task_id": tid,
                        "title": "Bound Project Fact",
                        "body": "Saved through bound project link.",
                    },
                },
            )
        ),
    )
    assert save_proc.returncode == 0
    payload = _decode_lines(save_proc.stdout)[1]["result"]["structuredContent"]
    assert payload["status"] == "saved"
    assert payload["record_path"] == "Memory/Facts/bound-project-fact.md"
    assert (workspace / payload["record_path"]).is_file()
    assert _tree_snapshot(project) == project_before


def test_read_tools_remain_read_only_when_saving_task_exists(tmp_path: Path) -> None:
    env = _make_env(tmp_path)
    workspace = _init_workspace(tmp_path, "ws", env)
    home = Path(env["APPARATUS_HOME"])

    (workspace / "Library" / "source.md").write_text(
        "# Release Guide\n\nChecksums must match before deploy.\n",
        encoding="utf-8",
    )
    start_proc = _run_cli(["task", "start", str(workspace), "--save-memory"], env=env)
    tid = json.loads(start_proc.stdout)["task_id"]
    assert _run_cli(["--task", tid, "library", "ingest", str(workspace)], env=env).returncode == 0

    ws_before = _tree_snapshot(workspace)
    home_before = _tree_snapshot(home)

    proc = _run_cli(
        ["mcp", "serve", str(workspace), "--memory-saves"],
        env=env,
        stdin_bytes=(
            _rpc("initialize", 1, _init_params())
            + _rpc("tools/call", 2, {"name": "library_recall", "arguments": {"question": "checksums"}})
            + _rpc("tools/call", 3, {"name": "memory_recall", "arguments": {"query": "anything"}})
            + _rpc("tools/call", 4, {"name": "resume_brief", "arguments": {}})
        ),
    )
    assert proc.returncode == 0
    assert _tree_snapshot(workspace) == ws_before
    assert _tree_snapshot(home) == home_before
    for resp in _decode_lines(proc.stdout)[1:]:
        assert resp["result"]["isError"] is False


def test_print_free_helpers_and_sanitized_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    env = _make_env(tmp_path)
    workspace = _init_workspace(tmp_path, "ws", env)
    monkeypatch.setenv("APPARATUS_HOME", env["APPARATUS_HOME"])

    # 1. Print-free helpers emit zero stdout/stderr bytes.
    started = task_command.start_task_outcome(workspace)
    assert capsys.readouterr() == ("", "")
    with WorkspaceAnchor(workspace) as anchor:
        outcome = memory_command.save_memory_record(
            anchor,
            action="add-fact",
            task_id=started["task_id"],
            title="Quiet Helper",
            body="Written without printing.",
        )
    assert capsys.readouterr() == ("", "")
    assert outcome.status == "saved"
    opted_out = task_command.no_memory_outcome(workspace, started["task_id"])
    assert capsys.readouterr() == ("", "")
    assert opted_out["memory"] == "no-save"
    with WorkspaceAnchor(workspace) as anchor:
        suppressed = memory_command.save_memory_record(
            anchor,
            action="add-fact",
            task_id=started["task_id"],
            title="Quiet Suppressed",
            body="Not written.",
        )
    assert capsys.readouterr() == ("", "")
    assert suppressed.status == "not_saved"

    # 2. Raw OSError/ValueError strings never leak through MCP save/task tool errors.
    secret_token = "SECRET_SQLITE_YAML_ERRNO_TEXT"
    secret_path = "/private/secret/host/path/tasks.db"

    monkeypatch.setattr(
        mcp_command,
        "start_task_outcome",
        lambda *_a, **_kw: (_ for _ in ()).throw(OSError(13, secret_token, secret_path)),
    )
    monkeypatch.setattr(
        mcp_command,
        "no_memory_outcome",
        lambda *_a, **_kw: (_ for _ in ()).throw(ValueError(f"{secret_token}:{secret_path}")),
    )
    monkeypatch.setattr(
        mcp_command,
        "save_memory_record",
        lambda *_a, **_kw: (_ for _ in ()).throw(OSError(5, secret_token, secret_path)),
    )

    stdin = io.BytesIO(
        _rpc("initialize", 1, _init_params())
        + _rpc("tools/call", 2, {"name": "task_start", "arguments": {}})
        + _rpc("tools/call", 3, {"name": "task_no_memory", "arguments": {"task_id": started["task_id"]}})
        + _rpc(
            "tools/call",
            4,
            {
                "name": "memory_save_fact",
                "arguments": {"task_id": started["task_id"], "title": "Fail", "body": "Fail"},
            },
        )
    )
    stdout = io.BytesIO()
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=stdin))
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(buffer=stdout))
    assert (
        mcp_command.run(
            argparse.Namespace(workspace=str(workspace), task=None, memory_saves=True)
        )
        == 0
    )
    captured = capsys.readouterr()
    raw_out = stdout.getvalue().decode("utf-8")
    assert secret_token not in raw_out and secret_path not in raw_out
    assert secret_token not in captured.err and secret_path not in captured.err
    for resp in _decode_lines(stdout.getvalue())[1:]:
        assert resp["result"]["isError"] is True
