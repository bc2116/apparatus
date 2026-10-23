"""Retain bounded signing/tool evidence, excluding setup secrets and identities."""
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent
RUN = 39994962103


def lines(archive, name):
    in_command = False
    for raw in archive.read(name).decode().splitlines():
        value = re.sub(r'^\d{4}-\d\d-\d\dT\S+\s*', '', raw)
        value = re.sub(r'\x1b\[[0-9;]*m', '', value)
        if '##[group]Run ' in value:
            in_command = True
            continue
        if in_command:
            if '##[endgroup]' in value:
                in_command = False
            continue
        yield value


data = subprocess.check_output(['gh', 'api', f'repos/bc2116/apparatus/actions/runs/{RUN}/logs'])
archive = zipfile.ZipFile(io.BytesIO(data))
paths = {
    'windows_build': 'Build Windows installer wrapper/3_Install pinned Inno Setup.txt',
    'macos_build': 'Build macOS installer wrapper/3_Build and verify macOS installer.txt',
    'windows_verify': 'Sign Windows installer with Azure Artifact Signing/7_Verify Azure-signed Windows installer.txt',
    'macos_sign': 'Sign and notarize macOS installer/4_Sign, notarize, and staple installer package.txt',
    'macos_payload': 'Sign and notarize macOS installer/5_Re-verify signed macOS package payload.txt',
}
pattern = re.compile(r'Inno Setup|Compiler engine|ProductName:|ProductVersion:|BuildVersion:|'
                     r'/usr/bin/(pkgbuild|productbuild)|Successfully verified|Number of (errors|warnings)|'
                     r'status: Accepted|Status: signed|staple and validate action worked|'
                     r'validate action worked|source=Notarized|^macOS package payload|^accepted$', re.I)
observations = {}
for key, name in paths.items():
    selected = [s for s in lines(archive, name) if pattern.search(s)]
    selected = [re.sub(r'[A-Za-z]:\\[^\n]*?apparatus-installer.exe', 'apparatus-installer.exe', s) for s in selected]
    observations[key] = {'log_member': name, 'selected_output': selected}
assert any('Successfully verified:' in s for s in observations['windows_verify']['selected_output'])
mac = '\n'.join(observations['macos_sign']['selected_output'])
for expected in ['status: Accepted', 'The staple and validate action worked!',
                 'Status: signed by a developer certificate issued by Apple for distribution',
                 'source=Notarized Developer ID', 'The validate action worked!']:
    assert expected in mac, expected
assert 'macOS package payload and launcher verified.' in observations['macos_payload']['selected_output']
images = {}
for job in ['Build release files', 'Build Windows installer wrapper', 'Build macOS installer wrapper',
            'Sign Windows installer with Azure Artifact Signing', 'Sign and notarize macOS installer']:
    name = job+'/1_Set up job.txt'
    selected, image_group = [], False
    for value in lines(archive, name):
        if '##[group]Runner Image' == value:
            image_group = True
        elif '##[endgroup]' == value:
            image_group = False
        elif value.startswith('Current runner version:') or (image_group and re.match(r'(Image|Version):', value)):
            selected.append(value)
    images[job] = selected
workflow = (ROOT.parents[3]/'.github/workflows/release.yml').read_text()
inno = re.search(r'INNO_SETUP_SHA256:\s*[\'"]?([0-9a-f]{64})', workflow)
assert inno
result = {'result': 'pass', 'run_id': RUN, 'selected_outputs': observations, 'runner_images': images,
          'inno_setup': {'pinned_version': '7.0.2', 'pinned_download_sha256': inno.group(1),
                         'assertion': 'Successful install step verifies pinned download digest, publisher signature and compiler major/architecture banner.'},
          'windows_assertions': ['signtool verify /pa /tw succeeded', 'Authenticode status Valid',
                                 'protected publisher subject matched', 'code-signing EKU accepted',
                                 'signer and timestamp certificate validity checked',
                                 'signed installer dry-run exercised embedded bootstrap'],
          'assertion_basis': 'Successful exact-source workflow steps plus bounded observed output; no credential-bearing command/setup text retained.',
          'tool_version_gaps': ['Exact signtool executable version not emitted',
                                'Exact productsign, notarytool and stapler versions not emitted'],
          'normalization': 'Hosted Windows executable path replaced with basename; certificate subject and account identity output omitted. Command echoes are excluded.'}
(ROOT/'signatures-and-tools.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
print('PASS: actual Windows verification, macOS notarization/stapling and signed payload evidence captured')
