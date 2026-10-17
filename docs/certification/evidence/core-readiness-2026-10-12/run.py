#!/usr/bin/env python3
"""Bounded PR-71 installed-core probe; does not finalize the evidence manifest."""
from __future__ import annotations

import argparse
import email
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys
import time
import traceback
import zipfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inventory(root):
    """No-follow inventory including directories, file bytes and exact metadata."""
    result = {}
    if not root.exists():
        return result
    for path in [root, *sorted(root.rglob('*'))]:
        info = path.lstat()
        kind = 'link' if stat.S_ISLNK(info.st_mode) else 'dir' if path.is_dir() else 'file'
        row = {'kind': kind, 'size': info.st_size, 'mode': stat.S_IMODE(info.st_mode),
               'mtime_ns': info.st_mtime_ns}
        if kind == 'file':
            row['sha256'] = digest(path.read_bytes())
        elif kind == 'link':
            row['target'] = os.readlink(path)
        result['.' if path == root else path.relative_to(root).as_posix()] = row
    return result


def delta(before, after):
    return {'added': sorted(after.keys() - before.keys()),
            'removed': sorted(before.keys() - after.keys()),
            'changed': sorted(key for key in before.keys() & after.keys()
                              if before[key] != after[key])}


def pdf_bytes(text):
    """Single ASCII text page, generated without extra dependencies."""
    stream = f'BT /F1 12 Tf 72 720 Td ({text}) Tj ET'.encode('ascii')
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
               b'<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'\nendstream']
    output = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f'{number} 0 obj\n'.encode() + obj + b'\nendobj\n')
    xref = len(output)
    output.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]:
        output.extend(f'{offset:010d} 00000 n \n'.encode())
    output.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    return bytes(output)


class Probe:
    def __init__(self, args):
        self.source = args.source_root.resolve(strict=True)
        self.runroot = args.run_dir.resolve()
        self.evidence = args.evidence_dir.resolve()
        self.sha = args.source_sha
        self.uv = shutil.which('uv')
        assert self.uv, 'uv is required'
        for root in (self.runroot, self.evidence):
            assert root != self.source and self.source not in root.parents, 'external directories required'
            assert not root.exists(), 'use fresh run and evidence directories; failed evidence is preserved'
        assert self.runroot != self.evidence
        assert self.runroot not in self.evidence.parents and self.evidence not in self.runroot.parents
        self.runroot.mkdir(parents=True)
        self.evidence.mkdir(parents=True)
        self.runtime = self.runroot / 'runtime'
        self.cwd = self.runtime / 'external-cwd'
        self.home = self.runtime / 'apparatus-home'
        self.temp = self.runtime / 'tmp'
        for root in (self.cwd, self.home, self.temp):
            root.mkdir(parents=True)
        self.env = {key: os.environ[key] for key in ('PATH', 'SYSTEMROOT', 'WINDIR') if key in os.environ}
        self.env.update({'LC_ALL': 'C', 'PYTHONDONTWRITEBYTECODE': '1',
                         'APPARATUS_HOME': str(self.home), 'TMPDIR': str(self.temp),
                         'TMP': str(self.temp), 'TEMP': str(self.temp),
                         'UV_CACHE_DIR': str(self.runroot / 'build-cache'), 'UV_NO_CONFIG': '1',
                         'PIP_CONFIG_FILE': os.devnull, 'PIP_DISABLE_PIP_VERSION_CHECK': '1',
                         'PIP_NO_INPUT': '1', 'SOURCE_DATE_EPOCH': '315532800',
                         'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull})
        self.aliases = [(str(self.source), '$SOURCE'), (str(self.runroot), '$RUN'),
                        (str(self.evidence), '$EVIDENCE'), (str(Path.home()), '$HOME'),
                        (str(Path(sys.executable).resolve()), '$BOOTSTRAP_PYTHON'),
                        (str(Path(self.uv).resolve()), '$UV')]
        self.aliases.extend([(sys.executable, '$BOOTSTRAP_PYTHON'), (self.uv, '$UV')])
        # Keep both lexical /tmp and canonical /private/tmp spellings portable.
        for old, new in list(self.aliases):
            if old.startswith('/private/tmp/'):
                self.aliases.append((old.replace('/private/tmp/', '/tmp/', 1), new))
        self.logs = []
        self.results = {'source_sha': self.sha, 'scope': 'Synthetic installed core CLI boundary probes; no native assistant, installer, signing, module or publication acceptance.',
                        'runner_sha256': digest(Path(__file__).read_bytes()),
                        'platform': {'system': platform.system(), 'machine': platform.machine(),
                                     'bootstrap_python': platform.python_version()}, 'cases': {}}

    def safe(self, text):
        for old, new in sorted(self.aliases, key=lambda item: len(item[0]), reverse=True):
            text = text.replace(old, new)
        return text

    def save(self, name, data):
        content = json.dumps(data, indent=2, sort_keys=True) + '\n'
        (self.evidence / name).write_text(self.safe(content), encoding='utf-8')

    def command(self, label, argv, expected=0, cwd=None, env=None):
        started = time.monotonic()
        completed = subprocess.run([str(arg) for arg in argv], cwd=cwd or self.cwd,
                                   env=env or self.env, capture_output=True, text=True, timeout=300)
        row = {'label': label, 'argv': [str(arg) for arg in argv],
               'cwd': str(cwd or self.cwd), 'return_code': completed.returncode,
               'stdout': completed.stdout, 'stderr': completed.stderr,
               'elapsed_seconds': round(time.monotonic() - started, 3)}
        self.logs.append(row)
        self.save('commands.json', self.logs)
        assert completed.returncode == expected, f'{label}: expected {expected}, observed {completed.returncode}; preserve commands.json'
        return completed.stdout

    def cli(self, label, *argv, alias='apparatus', expected=0):
        return self.command(label, [self.bin / (alias + ('.exe' if os.name == 'nt' else '')), *argv], expected)

    def run(self):
        self.results['uv_version'] = self.command('uv-version', [self.uv, '--version']).strip()
        observed = self.command('source-head', ['git', '-C', self.source, 'rev-parse', 'HEAD']).strip()
        assert observed == self.sha, 'source SHA must be full current HEAD'
        inputs = ['packages/apparatus-core', 'starter', 'tools/build_payload.py', 'uv.lock', 'pyproject.toml']
        assert not self.command('source-input-status', ['git', '-C', self.source, 'status', '--porcelain', '--untracked-files=no', '--', *inputs]).strip(), 'tracked build inputs must be clean; C documentation WIP may coexist'
        source_hashes = {}
        self.stage = self.runroot / 'build-source'
        tracked = self.command('source-input-files', ['git', '-C', self.source, 'ls-files', '--', *inputs]).splitlines()
        for name in tracked:
            path = self.source / name
            assert path.is_file() and not path.is_symlink(), 'source inputs must be ordinary tracked files'
            target = self.stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
            source_hashes[name] = digest(path.read_bytes())
        self.save('source-inputs.json', source_hashes)
        wheels = []
        for number in (1, 2):
            out = self.runroot / f'wheel-build-{number}'
            self.command(f'build-wheel-{number}', [self.uv, 'build', '--wheel', '--no-sources',
                                                  '--out-dir', out, self.stage / 'packages/apparatus-core'])
            found = list(out.glob('apparatus_core-*.whl'))
            assert len(found) == 1
            wheels.append(found[0])
        assert wheels[0].read_bytes() == wheels[1].read_bytes(), 'wheel builds differ'
        wheel = wheels[0]
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
            assert len(names) == len(set(names)), 'duplicate wheel entries'
            metadata_name, = [name for name in names if name.endswith('.dist-info/METADATA')]
            metadata = email.message_from_bytes(archive.read(metadata_name))
            requirements = metadata.get_all('Requires-Dist', [])
            floor = [value for value in requirements if re.match(r'^pypdf\s*>=\s*6\.19\.0\s*$', value, re.I)]
            assert len(floor) == 1, 'Requires-Dist must declare pypdf>=6.19.0'
            self.results['wheel'] = {'sha256': digest(wheel.read_bytes()), 'repeated_bytes_equal': True,
                                     'requires_dist': requirements, 'version': metadata['Version']}
            matched = {}
            for name in names:
                if not name.startswith('apparatus_core/') or name.endswith('/'):
                    continue
                source = self.source / 'packages/apparatus-core/src' / name
                assert source.is_file() and source.read_bytes() == archive.read(name), f'wheel/source mismatch: {name}'
                matched[name] = digest(archive.read(name))
            for root in ('payload', 'profiles'):
                canonical = self.source / 'starter' / root
                expected = {f'apparatus_core/starter/{root}/{path.relative_to(canonical).as_posix()}'
                            for path in canonical.rglob('*') if path.is_file()}
                actual = {name for name in names if name.startswith(f'apparatus_core/starter/{root}/') and not name.endswith('/')}
                assert actual == expected, f'{root} resource set mismatch'
                for name in expected:
                    original = canonical / name.split(f'/starter/{root}/', 1)[1]
                    assert original.read_bytes() == archive.read(name), f'canonical starter mismatch: {name}'
            self.save('wheel-source-verification.json', matched)
        self.venv = self.runroot / 'venv'
        self.command('isolated-venv', [self.uv, 'venv', '--seed', '--python', sys.executable, self.venv])
        self.bin = self.venv / ('Scripts' if os.name == 'nt' else 'bin')
        self.python = self.bin / ('python.exe' if os.name == 'nt' else 'python')
        wheelhouse = self.runroot / 'dependency-wheels'
        self.command('download-core-and-dependencies', [self.python, '-m', 'pip', 'download', '--only-binary=:all:',
                                                      '--dest', wheelhouse, wheel])
        dependency_hashes = {path.name: digest(path.read_bytes()) for path in sorted(wheelhouse.glob('*.whl'))}
        assert dependency_hashes
        self.save('dependency-wheel-hashes.json', dependency_hashes)
        self.command('install-only-core-with-dependencies', [self.python, '-m', 'pip', 'install', '--no-index',
                                                            '--find-links', wheelhouse, wheel])
        inspect_code = '''import importlib.metadata as m, json, pathlib, hashlib, apparatus_core, pypdf
data = {'module_file': str(pathlib.Path(apparatus_core.__file__).resolve()), 'pypdf_version': pypdf.__version__, 'distributions': {}}
for dist in m.distributions():
 files = {}
 for f in dist.files or []:
  p = dist.locate_file(f)
  if p.is_file() and not str(f).endswith('.pyc'):
   files[str(f)] = hashlib.sha256(p.read_bytes()).hexdigest()
 data['distributions'][dist.metadata['Name']] = {'version': dist.version, 'file_hashes': files}
print(json.dumps(data))'''
        installed = json.loads(self.command('installed-identity', [self.python, '-I', '-c', inspect_code]))
        module = Path(installed['module_file'])
        assert self.venv in module.parents and self.source not in module.parents
        assert 'apparatus-mailbox-survey' not in {key.lower() for key in installed['distributions']}
        version = tuple(int(part) for part in installed['pypdf_version'].split('.')[:3])
        assert version >= (6, 19, 0)
        self.save('installed-distributions.json', installed)
        payloads = []
        for number in (1, 2):
            out = self.runroot / f'payload-build-{number}'
            self.command(f'build-payload-{number}', [self.python, self.stage / 'tools/build_payload.py', '--out', out])
            found = list(out.glob('apparatus-payload-*.zip'))
            assert len(found) == 1
            payloads.append(found[0])
        assert payloads[0].read_bytes() == payloads[1].read_bytes(), 'payload builds differ'
        with zipfile.ZipFile(payloads[0]) as archive:
            expected = {}
            for root in ('payload', 'profiles'):
                base = self.source / 'starter' / root
                for path in base.rglob('*'):
                    if path.is_file():
                        name = f'{root}/{path.relative_to(base).as_posix()}'
                        expected[name] = digest(path.read_bytes())
                        assert archive.read(name) == path.read_bytes(), f'payload render differs: {name}'
            assert set(archive.namelist()) == set(expected) | {'manifest.txt'}
            self.results['payload'] = {'sha256': digest(payloads[0].read_bytes()), 'repeated_bytes_equal': True,
                                       'files': expected, 'manifest_sha256': digest(archive.read('manifest.txt'))}
        self.init_cases()
        self.continuity_library()
        self.backup_cases()
        # The read-only source identity is rechecked after every build/probe.
        assert all(digest((self.source / path).read_bytes()) == sha for path, sha in source_hashes.items())
        assert self.command('source-head-after', ['git', '-C', self.source, 'rev-parse', 'HEAD']).strip() == self.sha
        assert not self.command('source-input-status-after', ['git', '-C', self.source, 'status', '--porcelain', '--untracked-files=no', '--', *inputs]).strip()
        self.results['result'] = 'pass'
        self.results['manifest_state'] = 'Not finalized; root owns final archive inventory after evidence reconciliation.'
        self.save('results.json', self.results)

    def init_cases(self):
        for alias in ('apparatus', 'ap'):
            area = self.runtime / ('init-' + alias)
            self.cli(f'{alias}-init', 'init', area, alias=alias)
            (area / 'project').mkdir()
            sentinel = area / 'project/sentinel.txt'
            sentinel.write_text('Synthetic project sentinel.\n')
            before = inventory(area)
            output = self.cli(f'{alias}-repeat-init', 'init', area, alias=alias)
            after = inventory(area)
            self.save(f'{alias}-repeat-before.json', before)
            self.save(f'{alias}-repeat-after.json', after)
            assert before == after, 'repeat init changed exact file/directory inventory'
            assert 'already up to date' in output
            shim = area / 'CLAUDE.md'
            shim_bytes = shim.read_bytes()
            shim.unlink()
            before_repair = inventory(area)
            output = self.cli(f'{alias}-repair-init', 'init', area, alias=alias)
            after_repair = inventory(area)
            self.save(f'{alias}-repair-before.json', before_repair)
            self.save(f'{alias}-repair-after.json', after_repair)
            differences = delta(before_repair, after_repair)
            assert shim.read_bytes() == shim_bytes and 'repaired' in output.lower()
            assert before_repair['project/sentinel.txt'] == after_repair['project/sentinel.txt']
            assert not differences['removed']
            # Explicit repair is allowed only its shim, receipt and recovery writes.
            for name in differences['added'] + differences['changed']:
                assert name == 'CLAUDE.md' or name in {'.', 'System', 'System/receipts', 'System/recovery'} or name.startswith(('System/receipts/', 'System/recovery/')), f'unexpected repair write: {name}'
            self.results['cases']['init-' + alias] = {'repeat_exact_inventory_equal': True,
                                                    'shim_bytes_restored': True, 'repair_delta': differences}

    def continuity_library(self):
        area = self.runtime / 'continuation-area'
        self.cli('continuation-init', 'init', area)
        project = area / 'project'
        project.mkdir()
        (project / 'brief.md').write_text('# Synthetic Harbor brief\nTen participants; a forty-minute practice session.\n')
        self.cli('bind-project', 'project', 'bind', project, '--workspace', area)
        (area / 'Goals/prepare-harbor-note.md').write_text('---\nschema: apparatus/goal@v0\ntitle: Prepare Harbor note\nowner: Workshop team\nstatus: active\ndone-when: A grounded project note exists.\nnext-action: Read the project brief and list unresolved equipment choices.\n---\n\nSynthetic acceptance goal.\n')
        task = json.loads(self.cli('start-saving-task', 'task', 'start', project, '--save-memory'))['task_id']
        output = self.cli('save-synthetic-fact', '--task', task, 'memory', 'add-fact', project,
                          '--title', 'Harbor session format', '--body', 'The synthetic session has ten participants and lasts forty minutes. Source: project/brief.md.')
        assert 'Memory record saved.' in output and 'Record: Memory/Facts/' in output
        before = inventory(self.runtime)
        resumed = self.cli('resume-bound-project', 'resume', project)
        assert 'Goals/prepare-harbor-note.md' in resumed and 'Read the project brief' in resumed
        assert before == inventory(self.runtime), 'resume wrote state'
        self.results['cases']['saving-task-resume'] = {'fact_saved': True, 'bound_project_goal_returned': True, 'resume_exact_inventory_equal': True}
        (project / 'library-note.md').write_text('# Harbor reference\nThe violet lighthouse marker identifies this synthetic Markdown source.\n')
        (project / 'library-page.pdf').write_bytes(pdf_bytes('Amber harbor beacon synthetic PDF source'))
        bad_marker = b'SYNTHETIC_MALFORMED_PDF_CONTENT_MUST_NOT_LEAK'
        (project / 'malformed.pdf').write_bytes(b'%PDF-1.4\n' + bad_marker + b'\ninvalid body\n')
        for name, token in [('library-note.md', 'violet'), ('library-page.pdf', 'Amber')]:
            output = self.cli('library-add-' + name, '--task', task, 'library', 'add', project, 'project/' + name)
            assert 'extracted=1' in output, output
            search = json.loads(self.cli('library-search-' + name, 'library', 'search', project, token, '--json'))
            assert any(hit['source_path'] == 'project/' + name and token.lower() in hit['snippet'].lower() for hit in search['hits'])
        malformed = self.cli('library-malformed-pdf', '--task', task, 'library', 'add', project, 'project/malformed.pdf', expected=1)
        assert 'source could not be extracted' in malformed
        assert bad_marker.decode() not in malformed
        assert bad_marker.decode() not in self.logs[-1]['stderr']
        extraction = json.loads(self.command('malformed-extractor-boundary', [self.python, '-I', '-c',
            "import json; from pathlib import Path; from dataclasses import asdict; from apparatus_core.library.extractors import extract_bytes; print(json.dumps(asdict(extract_bytes(Path('synthetic.pdf'), b'not a PDF SYNTHETIC_MALFORMED_PDF_CONTENT_MUST_NOT_LEAK'))))"]))
        assert extraction == {'status': 'error', 'extractor': 'pypdf', 'text': '', 'error': 'source could not be extracted'}
        checked = self.cli('check-bound-project', 'check', project)
        assert 'check passed:' in checked
        self.results['cases']['library'] = {'markdown_extraction_search': True, 'pdf_extraction_search': True,
                                           'malformed_pdf_exit': 1, 'malformed_extractor_error_content_free': True}
        no_save = json.loads(self.cli('start-no-save-task', 'task', 'start', project, '--no-memory'))['task_id']
        before = inventory(self.runtime)
        self.save('no-save-before.json', before)
        refused = self.cli('no-save-managed-write-refused', '--task', no_save, 'memory', 'add-fact', project,
                           '--title', 'Must not be retained', '--body', 'Synthetic no-save content.', expected=1)
        assert 'does not save to Memory' in refused
        after_refusal = inventory(self.runtime)
        self.save('no-save-after-refusal.json', after_refusal)
        assert before == after_refusal, 'refused Memory operation wrote state'
        shown = json.loads(self.cli('no-save-task-show', 'task', 'show', project, no_save))
        assert shown['memory'] == 'no-save'
        self.cli('no-save-resume', '--task', no_save, 'resume', project)
        self.cli('no-save-check', '--task', no_save, 'check', project)
        assert before == inventory(self.runtime), 'no-save read operations wrote state'
        # This explicit requested file is a direct synthetic fixture write, not
        # evidence of autonomous assistant behavior or provider retention.
        requested = project / 'requested-note.md'
        requested.write_text('# Requested Harbor note\nTen participants; forty minutes. Equipment remains unresolved.\n\nSource: brief.md.\n')
        (self.evidence / 'requested-note.md').write_bytes(requested.read_bytes())
        after = inventory(self.runtime)
        self.save('no-save-after-requested-note.json', after)
        differences = delta(before, after)
        note_key = requested.relative_to(self.runtime).as_posix()
        parent_key = project.relative_to(self.runtime).as_posix()
        assert differences['added'] == [note_key] and not differences['removed']
        assert differences['changed'] == [parent_key], 'only parent directory metadata may change for the requested note'
        parent_before, parent_after = dict(before[parent_key]), dict(after[parent_key])
        for key in ('size', 'mtime_ns'):
            parent_before.pop(key); parent_after.pop(key)
        assert parent_before == parent_after
        self.save('no-save-delta.json', differences)
        self.results['cases']['no-save'] = {'baseline': 'After task start; all runtime files/directories, including controls/cache/recovery, inventoried with SHA-256/size/mode/mtime_ns.',
                                          'managed_write_refused_without_delta': True,
                                          'read_commands_without_delta': True, 'requested_note_only': True,
                                          'allowed_directory_change': 'Only requested-note parent size/mtime; no controls, receipts, cache or recovery exemptions.',
                                          'direct_cli_and_fixture_only': True}

    def backup_cases(self):
        cases = ['canonical', 'system-alias', 'leaf-link', 'alias-inside']
        for name in cases:
            case = self.runtime / ('backup-' + name)
            area = case / 'area'
            destination = case / 'exports'
            destination.mkdir(parents=True)
            self.cli('backup-init-' + name, 'init', area)
            (area / 'project').mkdir()
            self.command('backup-project-git-init-' + name, ['git', 'init', '--quiet', area / 'project'])
            (area / 'project/sentinel.txt').write_text('Synthetic protected project sentinel.\n')
            (area / 'Library/original.txt').write_text('Synthetic protected Library original.\n')
            (destination / 'sentinel.txt').write_text('Synthetic external sentinel.\n')
            selected = destination
            if name == 'system-alias':
                # General ancestor-symlink fixture follows PR-61's POSIX tests.
                alias = case / 'destination-ancestor-alias'
                alias.symlink_to(case, target_is_directory=True)
                selected = alias / 'exports'
            elif name == 'leaf-link':
                selected = case / 'destination-leaf-link'
                selected.symlink_to(destination, target_is_directory=True)
            elif name == 'alias-inside':
                destination = area / 'inside-exports'
                destination.mkdir()
                alias = case / 'inside-ancestor-alias'
                alias.symlink_to(area, target_is_directory=True)
                selected = alias / 'inside-exports'
            before = inventory(case)
            protected = {key: before[key] for key in ('area/project/sentinel.txt', 'area/Library/original.txt', 'exports/sentinel.txt')}
            output = self.cli('backup-export-' + name, 'backup', 'export', area, selected,
                              expected=0 if name in ('canonical', 'system-alias') else 2)
            after = inventory(case)
            self.save('backup-' + name + '-before.json', before)
            self.save('backup-' + name + '-after.json', after)
            assert all(after[key] == row for key, row in protected.items()), 'backup changed protected originals'
            project_before = {key: row for key, row in before.items() if key == 'area/project' or key.startswith('area/project/')}
            project_after = {key: row for key, row in after.items() if key == 'area/project' or key.startswith('area/project/')}
            assert project_before == project_after, 'backup changed the independent project Git tree'
            archives = list(case.rglob('apparatus-backup-*.zip'))
            if name in ('canonical', 'system-alias'):
                assert len(archives) == 1 and archives[0].parent == destination.resolve()
                assert f'Destination: {destination.resolve()}' in output
                with zipfile.ZipFile(archives[0]) as archive:
                    assert all(not entry.startswith(('project/', 'Library/')) for entry in archive.namelist())
                    entries = {entry: digest(archive.read(entry)) for entry in archive.namelist() if not entry.endswith('/')}
                receipts = list((area / 'System/receipts').glob('*-backup-export.md'))
                assert len(receipts) == 1
                assert str(destination.resolve()) in receipts[0].read_text(), 'receipt destination must be canonical'
                self.results['cases']['backup-' + name] = {'archive_count': 1, 'protected_exact_inventory_equal': True,
                                                          'canonical_output_and_receipt': True, 'project_and_originals_excluded': True,
                                                          'archive_sha256': digest(archives[0].read_bytes()), 'archive_entries': entries}
            else:
                assert not archives and before == after, 'rejected backup changed state or published archive'
                self.results['cases']['backup-' + name] = {'exit_code': 2, 'archive_count': 0, 'exact_inventory_equal': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    parser.add_argument('--source-sha', required=True)
    args = parser.parse_args()
    assert re.fullmatch(r'[0-9a-f]{40}', args.source_sha), 'full source SHA required'
    probe = Probe(args)
    try:
        probe.run()
    except Exception as error:
        probe.results['result'] = 'failed'
        probe.results['failure'] = probe.safe(str(error))
        probe.results['traceback'] = probe.safe(traceback.format_exc())
        probe.save('results.json', probe.results)
        print(probe.safe(f'Probe failed; preserved evidence: {probe.evidence}'), file=sys.stderr)
        return 1
    print(probe.safe(f'CLI probes passed; provisional evidence: {probe.evidence}'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
