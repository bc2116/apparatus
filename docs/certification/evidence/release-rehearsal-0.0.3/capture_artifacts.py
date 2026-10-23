"""Capture public rehearsal metadata and verify downloaded artifact bytes.

Requires authenticated gh access. Binary downloads stay outside this repository.
No publication, configuration changes, or raw workflow logs are performed.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

REPO = 'bc2116/apparatus'
CANDIDATE = '5890838696157a9139d91903f029b7114f1412b5'
RUN = 39994962103
VERSION = '0.0.3'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def api(path, binary=False):
    data = subprocess.check_output(['gh', 'api', f'repos/{REPO}/{path}'])
    return data if binary else json.loads(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--downloads', type=Path, required=True)
    args = parser.parse_args()
    evidence = Path(__file__).resolve().parent
    source = evidence.parents[3]
    target = args.downloads.resolve()
    assert target != source and source not in target.parents
    assert not target.exists(), 'fresh download directory required'
    run = api(f'actions/runs/{RUN}')
    assert run['event'] == 'workflow_dispatch' and run['head_sha'] == CANDIDATE
    assert run['head_branch'] == 'main' and run['conclusion'] == 'success'
    jobs = api(f'actions/runs/{RUN}/jobs?per_page=100')['jobs']
    required = ['Build release files', 'Build Windows installer wrapper',
                'Build macOS installer wrapper', 'Sign and notarize macOS installer',
                'Sign Windows installer with Azure Artifact Signing',
                'Assemble release files and checksums']
    by_name = {j['name']: j for j in jobs}
    assert all(by_name[n]['conclusion'] == 'success' for n in required)
    for name in ['Sign Windows installer', 'Publish apparatus-core to PyPI', 'Create GitHub Release']:
        assert by_name[name]['conclusion'] == 'skipped', name
    record = {k: run[k] for k in ['id', 'run_attempt', 'event', 'head_sha', 'head_branch',
                                  'status', 'conclusion', 'created_at', 'updated_at', 'html_url', 'path']}
    record['workflow_sha256'] = sha((source/'.github/workflows/release.yml').read_bytes())
    record['jobs'] = [{k: j[k] for k in ['id', 'name', 'status', 'conclusion', 'started_at',
                                        'completed_at', 'html_url', 'steps']} for j in jobs]
    artifacts = api(f'actions/runs/{RUN}/artifacts?per_page=100')['artifacts']
    selected = [f'apparatus-release-{VERSION}', f'apparatus-release-inputs-{VERSION}',
                f'apparatus-azure-signed-windows-installer-{VERSION}',
                f'apparatus-signed-macos-installer-{VERSION}']
    metadata, contents = {}, {}
    target.mkdir(parents=True)
    for name in selected:
        choices = [a for a in artifacts if a['name'] == name]
        assert len(choices) == 1 and not choices[0]['expired'], name
        a = choices[0]
        data = api(f"actions/artifacts/{a['id']}/zip", binary=True)
        assert a['digest'] == 'sha256:' + sha(data), name
        (target/(name+'.zip')).write_bytes(data)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
            assert len(names) == len(set(names))
            assert all(not p.startswith('/') and '..' not in Path(p).parts for p in names)
            files = {p: archive.read(p) for p in names if not p.endswith('/')}
        contents[name] = files
        metadata[name] = {k: a[k] for k in ['id', 'name', 'size_in_bytes', 'digest', 'created_at', 'expires_at']}
        metadata[name]['download_digest_verified'] = True
        metadata[name]['members'] = {p: sha(b) for p, b in files.items()}
    final = contents[selected[0]]
    expected = {f'apparatus-payload-{VERSION}.zip', f'apparatus_core-{VERSION}.tar.gz',
                f'apparatus_core-{VERSION}-py3-none-any.whl', 'bootstrap-apparatus.ps1',
                'bootstrap-apparatus.sh', 'apparatus-installer.exe', 'apparatus-installer.pkg'}
    assert set(final) == expected | {'SHA256SUMS', 'release-notes.md'}
    sums = dict((line.split(maxsplit=1)[1].lstrip('*'), line.split(maxsplit=1)[0])
                for line in final['SHA256SUMS'].decode().splitlines())
    assert set(sums) == expected
    assert all(sha(final[p]) == digest for p, digest in sums.items())
    assert final['release-notes.md'].decode().startswith('# Dry-run release')
    assert '## v0.0.3' in final['release-notes.md'].decode()
    for name, file in [(selected[2], 'apparatus-installer.exe'), (selected[3], 'apparatus-installer.pkg')]:
        assert set(contents[name]) == {file}
        assert contents[name][file] == final[file]
    for file in expected - {'apparatus-installer.exe', 'apparatus-installer.pkg'}:
        matches = [b for p, b in contents[selected[1]].items() if Path(p).name == file]
        assert len(matches) == 1 and matches[0] == final[file], file
    candidate_evidence = evidence.parent/'release-candidate-0.0.3'
    expected_members = json.loads((candidate_evidence/'package-equivalence.json').read_text())['member_hashes']
    with zipfile.ZipFile(io.BytesIO(final[f'apparatus_core-{VERSION}-py3-none-any.whl'])) as wheel:
        actual_members = {p: sha(wheel.read(p)) for p in wheel.namelist() if not p.endswith('/')}
    assert actual_members == expected_members, 'CI wheel members differ from the accepted candidate'
    source_artifacts = json.loads((candidate_evidence/'source-changes.json').read_text())['artifacts']
    assert sums[f'apparatus-payload-{VERSION}.zip'] == source_artifacts[f'apparatus-payload-{VERSION}.zip']
    (target/'final').mkdir()
    for name, data in final.items():
        (target/'final'/name).write_bytes(data)
    for name in ['SHA256SUMS', 'release-notes.md']:
        (evidence/name).write_bytes(final[name])
    (evidence/'run.json').write_text(json.dumps(record, indent=2, sort_keys=True)+'\n')
    (evidence/'artifacts.json').write_text(json.dumps(metadata, indent=2, sort_keys=True)+'\n')
    result = dict(result='pass', seven_checksums_verified=True, signed_upload_bytes_match_final=True,
                  inputs_match_final=True, candidate_wheel_members_equal=True,
                  candidate_payload_equal=True, distributables=sums)
    (evidence/'verification.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print('PASS: four artifact download digests, seven checksums, signed-file provenance and candidate parity')


if __name__ == '__main__':
    main()
