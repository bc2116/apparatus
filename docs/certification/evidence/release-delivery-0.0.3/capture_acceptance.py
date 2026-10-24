"""Capture bounded native receipts and verify their exact published source."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent
REPO = 'bc2116/apparatus'
SOURCE_RUN = 40057337396
CANDIDATE = '5890838696157a9139d91903f029b7114f1412b5'


def api(path, binary=False):
    data = subprocess.check_output(['gh', 'api', f'repos/{REPO}/{path}'])
    return data if binary else json.loads(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--windows-run', type=int, required=True)
    parser.add_argument('--macos-run', type=int, required=True)
    args = parser.parse_args()
    source_artifact = json.loads((ROOT/'artifacts.json').read_text())['apparatus-release-0.0.3']
    hashes = json.loads((ROOT/'verification.json').read_text())['distributables']
    records, runs, failed = {}, {}, []
    for os_name, platform, architecture in [('macos-15', 'Darwin', 'arm64'),
                                            ('windows-2025', 'Windows', 'AMD64')]:
        run_id = args.macos_run if platform == 'Darwin' else args.windows_run
        run = api(f'actions/runs/{run_id}')
        assert run['event'] == 'workflow_dispatch' and run['status'] == 'completed'
        assert run['head_sha'] == CANDIDATE and run['head_branch'] == 'v0.0.3'
        jobs = api(f'actions/runs/{run_id}/jobs?per_page=100')['jobs']
        by_name = {job['name']: job for job in jobs}
        for name in ['Validate published acceptance source', f'Native install and repair ({os_name})']:
            assert by_name[name]['conclusion'] == 'success', name
        for name in ['Build release files', 'Publish apparatus-core to PyPI', 'Create GitHub Release']:
            assert by_name[name]['conclusion'] == 'skipped', name
        if platform == 'Darwin':
            assert run['conclusion'] == 'success'
        record = {key: run[key] for key in ['id', 'run_attempt', 'event', 'head_sha', 'head_branch',
                                           'status', 'conclusion', 'created_at', 'updated_at', 'html_url']}
        record['jobs'] = [{key: job[key] for key in ['id', 'name', 'status', 'conclusion',
                                                  'started_at', 'completed_at', 'html_url', 'steps']}
                          for job in jobs]
        runs[str(run_id)] = record
        artifacts = api(f'actions/runs/{run_id}/artifacts?per_page=100')['artifacts']
        name = f'apparatus-native-acceptance-{os_name}-{run_id}-{run["run_attempt"]}'
        matches = [artifact for artifact in artifacts if artifact['name'] == name]
        assert len(matches) == 1 and not matches[0]['expired']
        artifact = matches[0]
        data = api(f'actions/artifacts/{artifact["id"]}/zip', binary=True)
        assert artifact['digest'] == 'sha256:' + hashlib.sha256(data).hexdigest()
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            assert archive.namelist() == ['acceptance-receipt.json']
            raw = archive.read('acceptance-receipt.json')
        receipt = json.loads(raw)
        assert receipt['result'] == 'passed' and receipt['installed_version'] == '0.0.3'
        assert receipt['platform'] == platform and receipt['architecture'] == architecture
        source = receipt['source']
        assert source['run_id'] == str(SOURCE_RUN) and source['run_attempt'] == 1
        assert source['head_sha'] == CANDIDATE and source['tag'] == 'v0.0.3'
        assert source['repository'] == REPO and source['version'] == '0.0.3'
        assert source['artifact_id'] == source_artifact['id']
        assert source['artifact_digest'] == source_artifact['digest']
        assert receipt['hashes'] == hashes
        assert all(command.get('exit_code') == 0 for command in receipt['commands'])
        stages = {command['stage'] for command in receipt['commands']}
        assert {'native install', 'installed version', 'installed workspace check',
                'native repair', 'repaired version', 'repaired workspace check'} <= stages
        assert receipt['repaired_file'] == '.agents/skills/apparatus-welcome/SKILL.md'
        shipped = ROOT.parents[3]/'starter/payload'/receipt['repaired_file']
        assert receipt['repaired_sha256'] == hashlib.sha256(shipped.read_bytes()).hexdigest()
        assert receipt['sentinel_sha256'] == hashlib.sha256(
            b'Apparatus native installer acceptance: preserve this project file.\n').hexdigest()
        if platform == 'Windows':
            signature = receipt['windows_signature']
            assert signature['status'] == 'Valid' and signature['failure_category'] == 'none'
            assert signature['signer_present'] and signature['timestamp_present']
        else:
            assert {'package signature', 'Gatekeeper assessment', 'notarization ticket',
                    'real console session'} <= stages
        filename = f'{os_name}-receipt.json'
        (ROOT/filename).write_bytes(raw)
        records[os_name] = {key: artifact[key] for key in
                            ['id', 'name', 'digest', 'size_in_bytes', 'created_at', 'expires_at']}
        records[os_name].update(run_id=run_id, download_digest_verified=True, receipt=filename,
                               receipt_sha256=hashlib.sha256(raw).hexdigest())
    # Preserve the failed first Mac receipt and its original successful Windows sibling.
    artifacts = api(f'actions/runs/{args.windows_run}/artifacts?per_page=100')['artifacts']
    for artifact in artifacts:
        if 'macos-15' not in artifact['name'] or args.windows_run == args.macos_run:
            continue
        data = api(f'actions/artifacts/{artifact["id"]}/zip', binary=True)
        assert artifact['digest'] == 'sha256:' + hashlib.sha256(data).hexdigest()
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            assert archive.namelist() == ['acceptance-receipt.json']
            raw = archive.read('acceptance-receipt.json')
        receipt = json.loads(raw)
        assert receipt['result'] == 'failed' and receipt['reason'] == 'notarization ticket failed'
        assert receipt['source']['head_sha'] == CANDIDATE
        assert receipt['source']['run_id'] == str(SOURCE_RUN)
        assert receipt['source']['artifact_id'] == source_artifact['id']
        assert receipt['source']['artifact_digest'] == source_artifact['digest']
        assert receipt['hashes'] == hashes
        assert receipt['commands'][-1] == {'stage': 'notarization ticket', 'exit_code': 68}
        filename = 'macos-first-failed-receipt.json'
        (ROOT/filename).write_bytes(raw)
        failed.append({'run_id': args.windows_run, 'artifact_id': artifact['id'],
                       'artifact_digest': artifact['digest'], 'download_digest_verified': True,
                       'receipt': filename, 'receipt_sha256': hashlib.sha256(raw).hexdigest()})
    assert len(failed) == (0 if args.windows_run == args.macos_run else 1)
    result = {'result': 'pass', 'head_sha': CANDIDATE, 'head_branch': 'v0.0.3',
              'updated_at': max(record['updated_at'] for record in runs.values()),
              'runs': runs, 'artifacts': records, 'failed_observations': failed}
    (ROOT/'native-acceptance.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print('PASS: both native receipts, signatures, source/artifact hashes, version, repair and preservation')


if __name__ == '__main__':
    main()
