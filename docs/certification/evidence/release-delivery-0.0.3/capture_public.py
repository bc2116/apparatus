"""Verify anonymous public download bytes against the tagged release bundle."""
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parent
REPO = 'bc2116/apparatus'
RUN = 40057337396
CANDIDATE = '5890838696157a9139d91903f029b7114f1412b5'


def api(path):
    return json.loads(subprocess.check_output(['gh', 'api', f'repos/{REPO}/{path}']))


def download(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        assert response.status == 200
        return response.read()


def main():
    run = api(f'actions/runs/{RUN}')
    assert run['head_sha'] == CANDIDATE and run['conclusion'] == 'success'
    jobs = api(f'actions/runs/{RUN}/jobs?per_page=100')['jobs']
    captured = json.loads((ROOT/'run.json').read_text())
    for key in captured:
        if key in run:
            captured[key] = run[key]
    captured['jobs'] = [{key: job[key] for key in ['id', 'name', 'status', 'conclusion',
                                                 'started_at', 'completed_at', 'html_url', 'steps']}
                        for job in jobs]
    assert next(job for job in jobs if job['name'] == 'Create GitHub Release')['conclusion'] == 'success'
    tag = api('git/ref/tags/v0.0.3')
    assert tag['object']['type'] == 'commit' and tag['object']['sha'] == CANDIDATE
    release = api('releases/tags/v0.0.3')
    assert not release['draft'] and release['tag_name'] == 'v0.0.3'
    assert release['body'].strip() == (ROOT/'release-notes.md').read_text().strip()
    final = json.loads((ROOT/'artifacts.json').read_text())['apparatus-release-0.0.3']['members']
    expected = set(final) - {'release-notes.md'}
    assert len(release['assets']) == 8 and {a['name'] for a in release['assets']} == expected
    assets = []
    for asset in release['assets']:
        raw = download(asset['browser_download_url'])
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == final[asset['name']]
        assert asset['digest'] == 'sha256:' + digest and len(raw) == asset['size']
        assets.append({key: asset[key] for key in ['id', 'name', 'size', 'digest', 'browser_download_url']})
    pypi = json.loads(download('https://pypi.org/pypi/apparatus-core/0.0.3/json'))
    assert pypi['info']['version'] == '0.0.3' and len(pypi['urls']) == 2
    packages = []
    for package in pypi['urls']:
        assert not package['yanked']
        digest = hashlib.sha256(download(package['url'])).hexdigest()
        assert digest == package['digests']['sha256'] == final[package['filename']]
        packages.append({key: package[key] for key in ['filename', 'url', 'size', 'upload_time_iso_8601', 'digests', 'yanked']})
    result = {key: release[key] for key in ['id', 'tag_name', 'html_url', 'name', 'draft', 'prerelease', 'published_at']}
    result.update(result='pass', candidate=CANDIDATE, assets=assets, pypi=packages,
                  anonymous_downloads_verified=10, notes_equal=True)
    (ROOT/'public-delivery.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    (ROOT/'run.json').write_text(json.dumps(captured, indent=2, sort_keys=True)+'\n')
    print('PASS: tag, final run, release notes, eight GitHub downloads and two PyPI downloads')


if __name__ == '__main__':
    main()
