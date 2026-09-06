from __future__ import annotations

import argparse
import errno
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import shutil
import zipfile

import pytest

from apparatus_core import managed_state_recovery as recovery
from apparatus_core.cache import library_cache_root
from apparatus_core.check import check_workspace
from apparatus_core.commands import init, library
from apparatus_core.fs_transactions import WorkspaceAnchor
from apparatus_core.library import cards, index, ingest, sources
from apparatus_core.receipts import ReceiptPublication
from apparatus_core.retention import operation, start_task

TEXT = "Four bench trials were recorded: three completed and one timed out. Results may not generalize.\n"
SUMMARY = "Of four bench trials, three completed and one timed out; results may not generalize."


def files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.fixture
def area(tmp_path, monkeypatch):
    monkeypatch.setenv('APPARATUS_HOME', str(tmp_path / 'home'))
    root = tmp_path / 'area'
    assert init.run(argparse.Namespace(workspace=str(root), payload=None, privacy_mode=None,
                                      work_types=None), available=lambda: False) == 0
    return root, start_task(root).task_id


def prepare(area, source='project/report.txt', text=TEXT):
    root, task = area
    path = root / source
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    sources.register_source(root, source, task_id=task)
    ingest.ingest_source(root, source, task_id=task)
    return source


def candidate(root, source, summary=SUMMARY):
    result = cards.read_card(root, source)
    assert result['evidence_status'] == 'extracted', result
    data = {key: result[key] for key in ('source_sha256', 'text_sha256', 'extractor_version')}
    return {**data, 'summary': summary, 'topics': ['bench trials', 'uncertain results']}


def save(area, source, data=None, **options):
    root, task = area
    data = candidate(root, source) if data is None else data
    return cards.write_card(root, source, StringIO(json.dumps(data)), task_id=task, **options)


@pytest.mark.parametrize('source', ['project/report.txt', 'Library/report.txt', 'Library/cafe\u0301.txt'])
def test_card_is_one_grounded_record_with_selected_evidence_only(area, monkeypatch, source):
    root, task = area
    prepare(area, source)
    if source.startswith('Library/'):
        assert not (root / 'System/library').exists()
    else:
        prepare(area, 'project/other.txt', 'Unrelated selected source.')
    original = sources.SourceRead.__init__
    opened = []
    def selected(reader, catalog, descriptor, rules=None):
        opened.append(descriptor.source_path)
        assert descriptor.source_path == source
        return original(reader, catalog, descriptor, rules)
    monkeypatch.setattr(sources.SourceRead, '__init__', selected)
    monkeypatch.setattr(ingest, '_library_entries', lambda *a, **k: pytest.fail('card walked Library'))
    monkeypatch.setattr(index, '_record_paths', lambda *a, **k: pytest.fail('card scanned extractions'))
    before = files(root)
    assert save(area, source)['status'] == 'written'
    path = cards.card_path(cards.source_for(source))
    stored = cards.parse_card((root / path).read_bytes(), path)
    assert stored['summary'] == SUMMARY and stored['source_sha256'] == hashlib.sha256(TEXT.encode()).hexdigest()
    assert files(root) == {**before, path: (root / path).read_bytes()}
    snapshot = files(root)
    assert save(area, source)['status'] == 'unchanged'
    assert files(root) == snapshot
    result = cards.read_card(root, source)
    assert result['card_status'] == 'current' and result['text'] == TEXT and result['summary'] == SUMMARY
    assert opened and set(opened) == {source}


def test_no_save_guard_precedes_input_and_sources_even_with_library_exception(area, monkeypatch):
    root, _ = area
    task = start_task(root, save_memory=False).task_id
    before = files(root)
    class Unreadable:
        def read(self):
            pytest.fail('no-save read card candidate')
    monkeypatch.setattr(sources.SourceRead, '__init__', lambda *a, **k: pytest.fail('no-save read source'))
    with operation(root, task_id=task, requested=('library', 'snapshot')):
        with pytest.raises(ValueError, match='does not save'):
            cards.write_card(root, 'project/report.txt', Unreadable(), task_id=task)
    assert files(root) == before


@pytest.mark.parametrize('missing', ['task', 'enrollment'])
def test_missing_controls_stop_before_input(area, missing):
    root, task = area
    if missing == 'enrollment':
        (root / 'System/workspace.yaml').unlink()
    else:
        task = None
    before = files(root)
    class Unreadable:
        def read(self):
            pytest.fail('missing controls read candidate')
    with pytest.raises(ValueError, match='task|Enroll'):
        cards.write_card(root, 'project/report.txt', Unreadable(), task_id=task)
    assert files(root) == before


def test_no_save_read_is_write_free_and_registration_exception_creates_no_card(area, capsys):
    root, _ = area
    source = prepare(area)
    save(area, source)
    task = start_task(root, save_memory=False).task_id
    before, cache_before = files(root), files(library_cache_root(root, create=False))
    with operation(root, task_id=task):
        assert cards.read_card(root, source)['card_status'] == 'current'
    assert files(root) == before and files(library_cache_root(root, create=False)) == cache_before
    other = root / 'project/new.txt'; other.write_text(TEXT)
    assert library.run_registration(argparse.Namespace(workspace=str(root), source='project/new.txt',
                                                      task=task, requested=True, library_action='add')) == 0
    assert 'Card: absent' in capsys.readouterr().out
    assert not (root / cards.card_path(cards.source_for('project/new.txt'))).exists()


@pytest.mark.parametrize('change', ['source_sha256', 'text_sha256', 'extractor_version'])
def test_stale_candidate_does_not_publish_or_leave_provisional_parents(area, change):
    root, task = area
    source = prepare(area, 'Library/report.txt')
    data = candidate(root, source)
    data[change] = '0' * 64 if change.endswith('sha256') else 'old'
    before = files(root)
    with pytest.raises(cards.CardError, match='evidence changed'):
        save(area, source, data)
    assert files(root) == before and not (root / 'System/library').exists()


@pytest.mark.parametrize('change', ['same-size', 'missing', 'ignored', 'unselected', 'missing-cache', 'corrupt-cache'])
def test_changed_or_unavailable_evidence_never_returns_a_stale_summary(area, change):
    root, task = area
    source = prepare(area)
    save(area, source)
    original = root / source
    if change == 'same-size':
        old = original.stat(); original.write_bytes(original.read_bytes().replace(b'Four', b'Five'))
        os.utime(original, ns=(old.st_atime_ns, old.st_mtime_ns))
    elif change == 'missing':
        original.unlink()
    elif change == 'ignored':
        (root / 'System/ignore').write_text(source + '\n')
    elif change == 'unselected':
        sources.unregister_source(root, source, task_id=task)
    else:
        cache = library_cache_root(root, create=False)
        record = cache / (cards.source_for(source).cache_relative + '.json')
        if change == 'missing-cache':
            shutil.rmtree(cache)
        else:
            record.write_bytes(b'invalid json')
    before = files(root)
    result = cards.read_card(root, source)
    assert result['card_status'] in {'stale', 'unavailable', 'unselected'}, result
    assert 'summary' not in result and 'topics' not in result
    assert files(root) == before


@pytest.mark.parametrize('source,text,expected', [('Library/empty.txt', '', 'no_text'),
                                                ('Library/raw.bin', 'Binary fixture', 'unsupported'),
                                                ('Library/bad.pdf', 'Invalid PDF fixture', 'error')])
def test_terminal_extraction_does_not_fabricate_card(area, source, text, expected):
    root, task = area
    prepare(area, source, text)
    result = cards.read_card(root, source)
    assert result['evidence_status'] == expected
    assert result['card_status'] == 'unavailable' and 'summary' not in result
    assert not (root / cards.card_path(cards.source_for(source))).exists()


@pytest.mark.parametrize('update', [False, True])
def test_redaction_receipt_late_failure_compensates_only_owned_card(area, monkeypatch, update):
    root, task = area
    source = prepare(area, 'Library/report.txt')
    if update:
        save(area, source)
    data = candidate(root, source, 'Use password=synthetic-password only in this synthetic example.')
    before = files(root)
    close = ReceiptPublication.close
    reached = []
    def fail(publication):
        close(publication)
        if '-redaction' in publication.path.name and not reached:
            reached.append(True)
            raise OSError('synthetic receipt close failure')
    monkeypatch.setattr(ReceiptPublication, 'close', fail)
    with pytest.raises(Exception):
        save(area, source, data)
    assert reached == [True] and files(root) == before
    if not update:
        assert not (root / 'System/library').exists()
    monkeypatch.setattr(ReceiptPublication, 'close', close)
    assert save(area, source, data)['status'] == 'written'
    saved = (root / cards.card_path(cards.source_for(source))).read_bytes()
    assert b'synthetic-password' not in saved and b'[redacted-password]' in saved
    assert len(list((root / 'System/receipts').glob('*-redaction.md'))) == 1


@pytest.mark.parametrize('damage', ['extra', 'duplicate', 'alias', 'bad-source', 'filename'])
def test_closed_cards_reject_foreign_metadata(area, damage):
    root, _ = area
    source = prepare(area)
    save(area, source)
    relative = cards.card_path(cards.source_for(source))
    content = (root / relative).read_bytes()
    if damage == 'extra': content += b'extra: value\n'
    elif damage == 'duplicate': content += b'summary: duplicate\n'
    elif damage == 'alias': content = content.replace(b'summary:', b'summary: &body')
    elif damage == 'bad-source': content = content.replace(source.encode(), b'../../outside')
    else: relative = cards.ROOT + '/' + '0' * 64 + '.yaml'
    with pytest.raises(ValueError):
        cards.parse_card(content, relative)


def test_foreign_card_path_is_preserved(area):
    root, _ = area
    source = prepare(area)
    data = candidate(root, source)
    path = root / cards.card_path(cards.source_for(source))
    path.parent.mkdir(parents=True); path.write_bytes(b'User-owned foreign text\n')
    before = files(root)
    with pytest.raises(cards.CardError):
        save(area, source, data)
    assert files(root) == before


def test_source_known_ignore_precedes_card_and_original_reads(area, monkeypatch):
    root, _ = area
    source = prepare(area)
    save(area, source)
    (root / 'System/ignore').write_text(source + '\n')
    capture = WorkspaceAnchor.capture_file
    def guard(anchor, relative, **options):
        assert str(relative) not in {cards.card_path(cards.source_for(source)), source}
        return capture(anchor, relative, **options)
    monkeypatch.setattr(WorkspaceAnchor, 'capture_file', guard)
    assert cards.read_card(root, source)['reason'] == 'ignored'


def test_check_record_ignore_and_source_ignore_have_distinct_boundaries(area, monkeypatch):
    root, _ = area
    source = prepare(area)
    save(area, source)
    (root / 'System/ignore').write_text(source + '\n')
    monkeypatch.setattr(sources.SourceRead, '__init__', lambda *a, **k: pytest.fail('check read ignored original'))
    assert any(f.code == 'library-card-unavailable' for f in check_workspace(root).findings)
    relative = cards.card_path(cards.source_for(source))
    (root / 'System/ignore').write_text(relative + '\n')
    original = WorkspaceAnchor.capture_file
    def guard(anchor, path, **options):
        assert anchor.workspace / Path(path) != root / relative, 'check opened ignored card record'
        return original(anchor, path, **options)
    monkeypatch.setattr(WorkspaceAnchor, 'capture_file', guard)
    assert any(f.code == 'library-card-check-incomplete' for f in check_workspace(root).findings)


def test_late_source_change_or_actual_native_denial_never_accepts_card(area, monkeypatch):
    root, _ = area
    source = prepare(area)
    data = candidate(root, source)
    relative = cards.card_path(cards.source_for(source))
    original = sources.SourceRead.validate
    outcomes = []
    changed = TEXT.replace('Four', 'Five').encode()
    def race(reader):
        if (root / relative).exists() and not outcomes:
            try:
                count = (root / source).write_bytes(changed)
            except PermissionError as error:
                assert os.name == 'nt' and error.errno == errno.EACCES
                outcomes.append(('blocked', error.errno, getattr(error, 'winerror', None)))
            else:
                assert count == len(changed)
                outcomes.append(('written', count))
        original(reader)
        if outcomes and outcomes[0][0] == 'blocked':
            raise OSError('failure after observed native denial')
    monkeypatch.setattr(sources.SourceRead, 'validate', race)
    with pytest.raises((OSError, ValueError, index.IndexError)):
        save(area, source, data)
    assert len(outcomes) == 1
    assert not (root / relative).exists()
    assert (root / source).read_bytes() == (changed if outcomes[0][0] == 'written' else TEXT.encode()), outcomes


@pytest.mark.skipif(shutil.which('git') is None, reason='real Git recovery/export proof')
def test_recovery_keeps_cards_not_originals_and_preserves_later_additions(area, tmp_path):
    from apparatus_core.managed_state_backup import export_backup
    root, task = area
    first_source = prepare(area)
    save(area, first_source)
    first = recovery.take_snapshot(root, task_id=task).snapshot
    second_source = prepare(area, 'project/later.txt')
    save(area, second_source)
    sources.unregister_source(root, first_source, task_id=task)
    with recovery.capture_state(root) as captured:
        assert cards.card_path(cards.source_for(first_source)) in captured.files
        assert first_source not in captured.files
    with operation(root, task_id=task):
        recovery.restore_snapshot(root, first.identifier)
        destination = tmp_path / 'exports'; destination.mkdir()
        archive = export_backup(root, destination).archive
    assert cards.read_card(root, second_source)['card_status'] == 'current'
    with zipfile.ZipFile(archive) as bundle:
        assert first_source not in bundle.namelist() and second_source not in bundle.namelist()
        assert cards.card_path(cards.source_for(first_source)) in bundle.namelist()
        extracted = tmp_path / 'restored'; bundle.extractall(extracted)
    with recovery.capture_state(extracted) as captured:
        assert cards.card_path(cards.source_for(second_source)) in captured.files
    assert cards.read_card(extracted, first_source)['card_status'] == 'unavailable'


def test_equal_redacted_candidate_keeps_required_receipt_and_late_failure_preserves_card(area, monkeypatch):
    root, _ = area
    source = prepare(area)
    data = candidate(root, source, 'Synthetic password=secret-value text.')
    save(area, source, data)
    relative = cards.card_path(cards.source_for(source))
    body = (root / relative).read_bytes()
    before = files(root)
    assert save(area, source, data)['status'] == 'unchanged'
    assert (root / relative).read_bytes() == body
    receipts = set(files(root)) - set(before)
    assert len(receipts) == 1 and '-redaction' in receipts.pop()
    before = files(root)
    original = ReceiptPublication.close
    reached = []
    def fail(receipt):
        original(receipt)
        if '-redaction' in receipt.path.name and not reached:
            reached.append(True)
            raise OSError('equal-card receipt failure')
    monkeypatch.setattr(ReceiptPublication, 'close', fail)
    with pytest.raises(OSError, match='equal-card receipt failure'):
        save(area, source, data)
    assert reached == [True] and files(root) == before


def test_disabled_feature_stops_before_candidate_and_provisional_writes(area, monkeypatch):
    root, task = area
    before = files(root)
    monkeypatch.setattr(cards, 'enabled', lambda *a: False)
    class Unreadable:
        def read(self): pytest.fail('feature-off read candidate')
    with pytest.raises(cards.CardError, match='off'):
        cards.write_card(root, 'Library/report.txt', Unreadable(), task_id=task)
    assert files(root) == before


def test_refresh_and_whole_area_move_require_current_extraction(area, tmp_path):
    root, task = area
    source = prepare(area)
    save(area, source)
    path = root / source
    path.write_text('Two trials completed; the sample is small.\n')
    assert cards.read_card(root, source)['card_status'] == 'stale'
    ingest.ingest_source(root, source, task_id=task)
    assert cards.read_card(root, source)['card_status'] == 'stale'
    save(area, source, candidate(root, source, 'Two trials completed; the sample is small.'))
    moved = tmp_path / 'moved'
    root.rename(moved)
    result = cards.read_card(moved, source)
    assert result['card_status'] in {'current', 'unavailable'}, result
    shutil.rmtree(library_cache_root(moved, create=False), ignore_errors=True)
    assert cards.read_card(moved, source)['card_status'] == 'unavailable'
    ingest.ingest_source(moved, source, task_id=task)
    assert cards.read_card(moved, source)['card_status'] == 'current'


@pytest.mark.parametrize('race', ['destination', 'catalog', 'cache'])
def test_late_race_preserves_competitor_and_never_accepts_card(area, monkeypatch, race):
    root, _ = area
    source = prepare(area, 'Library/report.txt')
    data = candidate(root, source)
    relative = cards.card_path(cards.source_for(source))
    original = cards._publish
    outcomes = []
    if race == 'destination':
        target = root / relative
        competing = b'User-owned concurrent record\n'
    elif race == 'catalog':
        target = root / sources.registration_path('project/other.txt')
        competing = b'schema: apparatus/library-source@v0\nsource: project/other.txt\n'
    else:
        target = library_cache_root(root, create=False) / (cards.source_for(source).cache_relative + '.txt')
        competing = TEXT.replace('Four', 'Five').encode()
    def mutate(*args, **kwargs):
        assert not outcomes
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            count = target.write_bytes(competing)
        except PermissionError as error:
            assert os.name == 'nt' and error.errno == errno.EACCES
            outcomes.append(('blocked', error.errno, getattr(error, 'winerror', None)))
            raise OSError('failure after observed native denial')
        else:
            outcomes.append(('written', count))
        return original(*args, **kwargs)
    monkeypatch.setattr(cards, '_publish', mutate)
    with pytest.raises((OSError, ValueError, index.IndexError)):
        save(area, source, data)
    assert len(outcomes) == 1, outcomes
    if outcomes[0][0] == 'written':
        assert target.read_bytes() == competing, outcomes
    if race != 'destination' or outcomes[0][0] != 'written':
        assert not (root / relative).exists(), outcomes


@pytest.mark.parametrize('crlf', [False, True])
@pytest.mark.parametrize('custom', [False, True])
def test_exact_pr43_migration_preserves_custom_learned_and_no_save_controls(area, crlf, custom):
    from apparatus_core.instruction_updates import CARDS_PREVIOUS_INSTRUCTIONS, _digest
    from apparatus_core.payload import shipped_payload
    from apparatus_core.skills import BUILTIN_PATHS, SKILL_INDEX
    from apparatus_core import learned_skills as learned
    root, _ = area
    task = start_task(root, save_memory=False).task_id
    fixtures = Path(__file__).parent / 'fixtures/instruction_updates_pr43'
    for relative, digest in CARDS_PREVIOUS_INSTRUCTIONS.items():
        content = (fixtures / relative).read_bytes().replace(b'\r\n', b'\n')
        assert _digest(content) == digest
        (root / relative).write_bytes(content.replace(b'\n', b'\r\n') if crlf else content)
    name = 'learned-bench-review'
    body_path, marker_path = root / learned.body_path(name), root / learned.marker_path(name)
    body_path.parent.mkdir(parents=True); marker_path.parent.mkdir(parents=True)
    body_path.write_bytes(f'---\nname: {name}\ndescription: Review repeated synthetic bench trials.\n---\n\nCompare outcomes and preserve uncertainty.\n'.encode())
    marker_path.write_bytes(learned.marker_bytes(name))
    preserved = {p.relative_to(root).as_posix(): p.read_bytes() for p in [body_path, marker_path]}
    if custom:
        for relative in (*BUILTIN_PATHS, 'AGENTS.md', 'Welcome.md', 'System/README.md', 'System/guidance/model-guidance.md'):
            path = root / relative; path.write_bytes(path.read_bytes() + b'\nUser-owned custom instructions.\n')
            preserved[relative] = path.read_bytes()
    preserved.update({p.relative_to(root).as_posix(): p.read_bytes() for p in (root / 'System/tasks').glob('*.yaml')})
    preserved['System/profile.yaml'] = (root / 'System/profile.yaml').read_bytes()
    options = argparse.Namespace(workspace=str(root), payload=None, privacy_mode=None, work_types=None, task=task)
    assert init.run(options, available=lambda: False) == 0
    assert all((root / relative).read_bytes() == content for relative, content in preserved.items())
    if not custom:
        assert all((root / relative).read_bytes() == (shipped_payload() / relative).read_bytes() for relative in CARDS_PREVIOUS_INSTRUCTIONS)
    assert SKILL_INDEX.encode() in (root / 'AGENTS.md').read_bytes().replace(b'\r\n', b'\n')
    assert b'System/skills/adopted/' in (root / 'AGENTS.md').read_bytes()
    before = files(root)
    assert init.run(options, available=lambda: False) == 0
    assert files(root) == before


@pytest.mark.parametrize('orientation', ['Welcome.md', 'System/README.md'])
def test_pr43_orientation_still_requires_complete_seven_skill_source(tmp_path, orientation):
    from apparatus_core.payload import shipped_payload
    from apparatus_core.skills import NEW_SKILL_PATHS, read_skill_payload
    root = tmp_path / 'payload'; shutil.copytree(shipped_payload(), root)
    for relative in ('AGENTS.md', 'Welcome.md', 'System/README.md'):
        (root / relative).write_bytes(b'Custom instructions.\n')
    (root / orientation).write_bytes((Path(__file__).parent / 'fixtures/instruction_updates_pr43' / orientation).read_bytes())
    for relative in NEW_SKILL_PATHS:
        shutil.rmtree((root / relative).parent)
    with WorkspaceAnchor(root) as anchor, pytest.raises(ValueError, match='complete portable Skill payload'):
        read_skill_payload(anchor)


def test_bound_project_cli_reads_and_publishes_exact_selected_card(area):
    import subprocess
    from apparatus_core.project_binding import bind_project
    root, task = area
    source = prepare(area)
    project = root / 'project'
    bind_project(project, root)
    command = [shutil.which('apparatus'), '--task', task, 'library', 'card', str(project), source]
    before = files(root)
    read = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert read.returncode == 0, read.stdout + read.stderr
    envelope = json.loads(read.stdout)
    data = {key: envelope[key] for key in ('source_sha256', 'text_sha256', 'extractor_version')}
    assert files(root) == before
    write = subprocess.run([*command, '--stdin'], input=json.dumps({**data, 'summary': SUMMARY, 'topics': []}),
                           capture_output=True, text=True, timeout=30)
    assert write.returncode == 0, write.stdout + write.stderr
    assert json.loads(write.stdout)['status'] == 'written'
    assert (root / cards.card_path(cards.source_for(source))).is_file()
    assert not (project / 'System').exists()


def test_cards_do_not_become_original_search_evidence(area):
    root, _ = area
    source = prepare(area)
    save(area, source, candidate(root, source, 'syntheticcardonlytoken'))
    result = index.retrieve(root, 'syntheticcardonlytoken')
    assert not result.hits


def test_unsafe_card_parent_is_not_followed(area, tmp_path):
    root, _ = area
    source = prepare(area)
    data = candidate(root, source)
    external = tmp_path / 'external'; external.mkdir()
    parent = root / cards.ROOT
    try:
        parent.symlink_to(external, target_is_directory=True)
    except OSError as error:
        if os.name == 'nt' and getattr(error, 'winerror', None) == 1314:
            pytest.skip('Windows runner does not permit synthetic symlink creation')
        raise
    with pytest.raises((OSError, ValueError, index.IndexError)):
        save(area, source, data)
    assert list(external.iterdir()) == [] and parent.is_symlink()


def test_invalid_card_is_actionable_in_check_and_blocks_recovery(area):
    root, _ = area
    source = prepare(area)
    save(area, source)
    (root / cards.card_path(cards.source_for(source))).write_text('foreign: content\n')
    assert any(item.code == 'library-card-check-incomplete' for item in check_workspace(root).findings)
    with pytest.raises(recovery.SnapshotError):
        with recovery.capture_state(root):
            pytest.fail('invalid card was omitted from recovery')


@pytest.mark.parametrize('change', ['unselected', 'ignored', 'missing', 'stale'])
def test_check_card_hints_distinguish_intentional_inactivity_from_repair(area, change):
    root, task = area
    source = prepare(area)
    save(area, source)
    if change == 'unselected':
        sources.unregister_source(root, source, task_id=task)
    elif change == 'ignored':
        (root / 'System/ignore').write_text(source + '\n')
    elif change == 'missing':
        (root / source).unlink()
    else:
        (root / source).write_text(TEXT.replace('Four', 'Five'))
    before = files(root)
    findings = [f for f in check_workspace(root).findings if f.code.startswith('library-card-')]
    assert len(findings) == 1
    hint = findings[0].hint
    if change in {'unselected', 'ignored'}:
        assert 'inactive' in hint and 'intentional' in hint
        assert 'refresh' not in hint and 'add WORKSPACE' not in hint
    else:
        assert 'original' in hint and ('repair' in hint.lower() or 'restore' in hint.lower())
    assert SUMMARY not in hint
    assert files(root) == before
