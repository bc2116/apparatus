"""Check captured rehearsal evidence offline; does not execute signing."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parents[3]


def load(name):
    return json.loads((ROOT/name).read_text())


run = load('run.json')
assert run['head_sha'] == '5890838696157a9139d91903f029b7114f1412b5'
assert run['id'] == 39994962103 and run['run_attempt'] == 1
assert run['event'] == 'workflow_dispatch' and run['conclusion'] == 'success'
assert run['workflow_sha256'] == hashlib.sha256((SOURCE/'.github/workflows/release.yml').read_bytes()).hexdigest()
assert load('candidate-merge.json')['candidate_sha'] == run['head_sha']
assert load('candidate-merge.json')['source_input_count'] == 263
assert load('candidate-merge.json')['merged_source_parity'] == 'pass'
jobs = {j['name']: j for j in run['jobs']}
for name in ['Build release files', 'Build Windows installer wrapper', 'Build macOS installer wrapper',
             'Sign and notarize macOS installer', 'Sign Windows installer with Azure Artifact Signing',
             'Assemble release files and checksums']:
    assert jobs[name]['conclusion'] == 'success', name
for name in ['Sign Windows installer', 'Publish apparatus-core to PyPI', 'Create GitHub Release']:
    assert jobs[name]['conclusion'] == 'skipped', name
verification = load('verification.json')
assert verification['result'] == 'pass'
sums = {line.split(maxsplit=1)[1].lstrip('*'): line.split(maxsplit=1)[0]
        for line in (ROOT/'SHA256SUMS').read_text().splitlines()}
assert len(sums) == 7 and sums == verification['distributables']
artifacts = load('artifacts.json')
assert len(artifacts) == 4 and all(a['download_digest_verified'] for a in artifacts.values())
final = artifacts['apparatus-release-0.0.3']['members']
assert set(final) == set(sums) | {'SHA256SUMS', 'release-notes.md'}
assert all(final[p] == digest for p, digest in sums.items())
for file, artifact in [('apparatus-installer.exe', 'apparatus-azure-signed-windows-installer-0.0.3'),
                       ('apparatus-installer.pkg', 'apparatus-signed-macos-installer-0.0.3')]:
    assert artifacts[artifact]['members'] == {file: sums[file]}
candidate = json.loads((ROOT.parent/'release-candidate-0.0.3/source-changes.json').read_text())
assert all(sums[p] == h for p, h in candidate['artifacts'].items())
for file, path in [('bootstrap-apparatus.ps1', 'installer/windows/bootstrap-apparatus.ps1'),
                   ('bootstrap-apparatus.sh', 'installer/macos/bootstrap-apparatus.sh')]:
    assert sums[file] == hashlib.sha256((SOURCE/path).read_bytes()).hexdigest()
assert load('signatures-and-tools.json')['result'] == 'pass'
publication = load('publication-check.json')
assert publication['result'] == 'pass' and publication['publish_mode'] == 'unset'
assert publication['before'] == publication['after']
assert publication['after']['pypi_versions'] == ['0.0.2']
assert publication['after']['candidate_tag_absent']
manifest = load('manifest.json')['files']
actual = {p.name for p in ROOT.iterdir() if p.is_file() and p.name != 'manifest.json'}
assert set(manifest) == actual
for path, digest in manifest.items():
    assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest, path
print('PASS: candidate/run identity, signed provenance, seven hashes, publication hold and manifest')
