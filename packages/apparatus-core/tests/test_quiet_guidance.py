"""Exact PR-44 quiet-guidance migration preserves custom and retained product state."""
from __future__ import annotations
import argparse
from io import StringIO
import json
from pathlib import Path

import pytest

from apparatus_core import learned_skills
from apparatus_core.commands import init
from apparatus_core.instruction_updates import QUIET_PREVIOUS_INSTRUCTIONS, _digest
from apparatus_core.library import cards, sources
from apparatus_core.library.ingest import ingest_source
from apparatus_core.payload import shipped_payload
from apparatus_core.retention import start_task
from apparatus_core.skills import BUILTIN_PATHS, SKILL_INDEX, is_shipped_skill_orientation
from apparatus_core.check import check_workspace

FIXTURES = Path(__file__).parent / 'fixtures/instruction_updates_pr44'


def files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('crlf', [False, True])
@pytest.mark.parametrize('custom', [False, True])
def test_exact_pr44_upgrade_preserves_cards_learned_preferences_and_no_save(tmp_path, monkeypatch, crlf, custom):
    root = tmp_path / 'area'
    monkeypatch.setenv('APPARATUS_HOME', str(tmp_path / 'cache'))
    args = argparse.Namespace(workspace=str(root), payload=None, privacy_mode=None, work_types=None)
    assert init.run(args, available=lambda: False) == 0
    task = start_task(root).task_id
    source = 'project/report.txt'
    path = root / source; path.parent.mkdir(); path.write_text('Three synthetic trials completed.\n')
    sources.register_source(root, source, task_id=task)
    ingest_source(root, source, task_id=task)
    evidence = cards.read_card(root, source)
    candidate = {key: evidence[key] for key in ('source_sha256', 'text_sha256', 'extractor_version')}
    candidate.update(summary='Three synthetic trials completed.', topics=['trials'])
    cards.write_card(root, source, StringIO(json.dumps(candidate)), task_id=task)
    name = 'learned-review-trials'
    body = root / learned_skills.body_path(name); body.parent.mkdir(parents=True)
    body.write_text(f'---\nname: {name}\ndescription: Review repeated synthetic trials.\n---\nCompare trial outcomes.\n')
    marker = root / learned_skills.marker_path(name); marker.parent.mkdir(parents=True)
    marker.write_bytes(learned_skills.marker_bytes(name))
    args.task = start_task(root, save_memory=False).task_id
    for relative, digest in QUIET_PREVIOUS_INSTRUCTIONS.items():
        content = (FIXTURES / relative).read_bytes().replace(b'\r\n', b'\n')
        assert _digest(content) == digest
        (root / relative).write_bytes(content.replace(b'\n', b'\r\n') if crlf else content)
    preserved = {relative: data for relative, data in files(root).items()
                 if relative.startswith(('System/library/', 'System/tasks/', 'System/skills/', 'project/'))
                 or relative in BUILTIN_PATHS or relative in {'System/profile.yaml', learned_skills.body_path(name)}}
    if custom:
        for relative in ('AGENTS.md', 'System/README.md'):
            path = root / relative; path.write_bytes(path.read_bytes() + b'\nCustom instructions remain user-owned.\n')
            preserved[relative] = path.read_bytes()
    def forbidden(*args, **kwargs):
        pytest.fail('no-save instruction repair attempted an automatic snapshot')
    assert init.run(args, available=lambda: True, take=forbidden) == 0
    assert all((root / relative).read_bytes() == content for relative, content in preserved.items())
    if not custom:
        assert all((root / relative).read_bytes() == (shipped_payload() / relative).read_bytes()
                   for relative in QUIET_PREVIOUS_INSTRUCTIONS)
    canon = (root / 'AGENTS.md').read_bytes().replace(b'\r\n', b'\n')
    assert SKILL_INDEX.encode() in canon and b'System/skills/adopted/' in canon
    assert 'library card' in canon.decode() and 'WORKSPACE PATH --stdin' in canon.decode()
    before = files(root)
    assert init.run(args, available=lambda: True, take=forbidden) == 0
    assert files(root) == before


def test_quiet_stock_keeps_credential_floor_and_no_routine_activity_instructions():
    canon = ' '.join((shipped_payload() / 'AGENTS.md').read_text().split())
    system = ' '.join((shipped_payload() / 'System/README.md').read_text().split())
    assert 'for anything the workspace machinery does' not in canon
    assert 'Routine checks, retrieval, Library ingest, disabled or unavailable operations and unchanged profile apply need no activity receipt.' in canon
    assert 'When a write redacts credentials, retain its required redaction receipt.' in canon
    assert 'Do not persist retrieval queries or evidence paths as activity logs.' in canon
    assert 'leave them inactive when that choice is intentional' in system
    assert is_shipped_skill_orientation('System/README.md', (FIXTURES / 'System/README.md').read_bytes())
    assert is_shipped_skill_orientation('System/README.md', (shipped_payload() / 'System/README.md').read_bytes())


def test_pr44_migration_does_not_replace_late_custom_instruction(tmp_path, monkeypatch):
    import os
    root = tmp_path / 'area'
    args = argparse.Namespace(workspace=str(root), payload=None, privacy_mode=None, work_types=None)
    assert init.run(args, available=lambda: False) == 0
    for relative in QUIET_PREVIOUS_INSTRUCTIONS:
        (root / relative).write_bytes((FIXTURES / relative).read_bytes())
    original = init.deploy_init_plan
    target = root / 'System/README.md'
    custom = target.read_bytes() + b'\nLate user-owned instruction.\n'
    before = files(root)
    observed = []
    def compete(*args, **kwargs):
        replacement = root / 'competitor.tmp'
        replacement.write_bytes(custom)
        try:
            os.replace(replacement, target)
            observed.append('replaced')
        except PermissionError as error:
            assert os.name == 'nt' and getattr(error, 'winerror', None) in {5, 32}
            replacement.unlink()
            observed.append('native-denial')
        return original(*args, **kwargs)
    monkeypatch.setattr(init, 'deploy_init_plan', compete)
    result = init.run(args, available=lambda: False)
    assert observed in (['replaced'], ['native-denial'])
    if observed == ['replaced']:
        assert result == 2
        assert files(root) == {**before, 'System/README.md': custom}
    else:
        assert result == 0
