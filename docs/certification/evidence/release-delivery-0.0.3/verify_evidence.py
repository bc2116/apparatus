"""Check captured delivery evidence offline; does not re-execute installation."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parents[3]
CANDIDATE = '5890838696157a9139d91903f029b7114f1412b5'
RUN = 40057337396


def load(name):
    return json.loads((ROOT/name).read_text())


run = load('run.json')
assert run['id'] == RUN and run['run_attempt'] == 1
assert run['head_sha'] == CANDIDATE and run['head_branch'] == 'v0.0.3'
assert run['event'] == 'push' and run['conclusion'] == 'success'
assert run['workflow_sha256'] == hashlib.sha256((SOURCE/'.github/workflows/release.yml').read_bytes()).hexdigest()
assert load('tag.json')['object']['sha'] == CANDIDATE
assert load('preflight.json')['candidate'] == CANDIDATE
parity = load('source-parity.json')
assert parity['candidate'] == CANDIDATE and parity['source_input_count'] == 263
assert parity['frozen_candidate_matches_accepted_inputs'] and parity['delivery_checkout_matches_accepted_inputs']
jobs = {job['name']: job for job in run['jobs']}
for name in ['Build release files', 'Build Windows installer wrapper', 'Build macOS installer wrapper',
             'Sign and notarize macOS installer', 'Sign Windows installer with Azure Artifact Signing',
             'Assemble release files and checksums', 'Publish apparatus-core to PyPI', 'Create GitHub Release']:
    assert jobs[name]['conclusion'] == 'success', name
assert jobs['Sign Windows installer']['conclusion'] == 'skipped'
sums = {line.split(maxsplit=1)[1].lstrip('*'): line.split(maxsplit=1)[0]
        for line in (ROOT/'SHA256SUMS').read_text().splitlines()}
verification = load('verification.json')
assert verification['result'] == 'pass' and len(sums) == 7
assert sums == verification['distributables']
artifacts = load('artifacts.json')
assert len(artifacts) == 4 and all(a['download_digest_verified'] for a in artifacts.values())
final = artifacts['apparatus-release-0.0.3']
assert set(final['members']) == set(sums) | {'SHA256SUMS', 'release-notes.md'}
assert all(final['members'][name] == digest for name, digest in sums.items())
for name, artifact in [('apparatus-installer.exe', 'apparatus-azure-signed-windows-installer-0.0.3'),
                       ('apparatus-installer.pkg', 'apparatus-signed-macos-installer-0.0.3')]:
    assert artifacts[artifact]['members'] == {name: sums[name]}
candidate = json.loads((ROOT.parent/'release-candidate-0.0.3/source-changes.json').read_text())
assert all(sums[name] == digest for name, digest in candidate['artifacts'].items())
for name, path in [('bootstrap-apparatus.ps1', 'installer/windows/bootstrap-apparatus.ps1'),
                   ('bootstrap-apparatus.sh', 'installer/macos/bootstrap-apparatus.sh')]:
    assert sums[name] == hashlib.sha256((SOURCE/path).read_bytes()).hexdigest()
assert load('signatures-and-tools.json')['result'] == 'pass'
assert load('signatures-and-tools.json')['run_id'] == RUN
native = load('native-acceptance.json')
assert native['result'] == 'pass'
assert native['head_sha'] == CANDIDATE and native['head_branch'] == 'v0.0.3'
for os_name, platform in [('macos-15', 'Darwin'), ('windows-2025', 'Windows')]:
    artifact = native['artifacts'][os_name]
    assert artifact['download_digest_verified']
    native_run = native['runs'][str(artifact['run_id'])]
    assert native_run['head_sha'] == CANDIDATE
    native_jobs = {j['name']: j for j in native_run['jobs']}
    assert native_jobs[f'Native install and repair ({os_name})']['conclusion'] == 'success'
    raw = (ROOT/artifact['receipt']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == artifact['receipt_sha256']
    receipt = json.loads(raw)
    assert receipt['result'] == 'passed' and receipt['platform'] == platform
    assert receipt['installed_version'] == '0.0.3' and receipt['hashes'] == sums
    source = receipt['source']
    assert source['run_id'] == str(RUN) and source['head_sha'] == CANDIDATE
    assert source['artifact_id'] == final['id'] and source['artifact_digest'] == final['digest']
    assert all(command.get('exit_code') == 0 for command in receipt['commands'])
    assert receipt['repaired_sha256'] == hashlib.sha256(
        (SOURCE/'starter/payload'/receipt['repaired_file']).read_bytes()).hexdigest()
    assert receipt['sentinel_sha256'] == hashlib.sha256(
        b'Apparatus native installer acceptance: preserve this project file.\n').hexdigest()
    if platform == 'Windows':
        signature = receipt['windows_signature']
        assert signature['status'] == 'Valid' and signature['failure_category'] == 'none'
        assert signature['signer_present'] and signature['timestamp_present']
for failed in native['failed_observations']:
    raw = (ROOT/failed['receipt']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == failed['receipt_sha256']
    assert failed['download_digest_verified'] and json.loads(raw)['result'] == 'failed'
public = load('public-delivery.json')
assert public['result'] == 'pass' and public['candidate'] == CANDIDATE
assert public['tag_name'] == 'v0.0.3' and not public['draft']
assert public['anonymous_downloads_verified'] == 10 and public['notes_equal']
assert {asset['name'] for asset in public['assets']} == set(sums) | {'SHA256SUMS'}
for asset in public['assets']:
    assert asset['digest'] == 'sha256:' + final['members'][asset['name']]
assert len(public['pypi']) == 2
for package in public['pypi']:
    assert package['digests']['sha256'] == sums[package['filename']] and not package['yanked']
approvals = load('approvals.json')
release_approval = [a for a in approvals if a['environment'] == 'release']
assert len(release_approval) == 1
assert all(a['normal_required_reviewer_path'] and a['state'] == 'approved' for a in approvals)
from datetime import datetime
assert datetime.fromisoformat(release_approval[0]['timestamp_utc']) > datetime.fromisoformat(native['updated_at'])
cleanup = load('cleanup.json')
assert cleanup['publish_mode'] == 'unset' and cleanup['required_reviewer_rules_preserved']
assert cleanup['tag_sha'] == CANDIDATE
manifest = load('manifest.json')['files']
assert set(manifest) == {p.name for p in ROOT.iterdir() if p.is_file() and p.name != 'manifest.json'}
for name, digest in manifest.items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest, name
print('PASS: release source, signatures, native acceptance, public bytes, approval ordering and cleanup')
