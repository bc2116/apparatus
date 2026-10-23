#!/usr/bin/env python3
"""Four bounded native conversations against an already installed candidate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import time


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inventory(root):
    result = {}
    for path in [root, *sorted(root.rglob('*'))]:
        info = path.lstat()
        kind = 'link' if stat.S_ISLNK(info.st_mode) else 'dir' if path.is_dir() else 'file'
        row = dict(kind=kind, size=info.st_size, mode=stat.S_IMODE(info.st_mode), mtime_ns=info.st_mtime_ns)
        if kind == 'file':
            row['sha256'] = digest(path.read_bytes())
        if kind == 'link':
            row['target'] = os.readlink(path)
        result['.' if path == root else path.relative_to(root).as_posix()] = row
    return result


def execute(argv, cwd, env, timeout=60):
    started = time.monotonic()
    process = subprocess.Popen(list(map(str, argv)), cwd=cwd, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
    return stdout, dict(argv=list(map(str, argv)), exit_code=process.returncode, timed_out=timed_out,
                        seconds=round(time.monotonic() - started, 3), stdout_sha256=digest(stdout.encode()),
                        stderr_sha256=digest(stderr.encode()), stderr_bytes=len(stderr.encode()))


def extract(stdout):
    finals, models, commands = [], set(), []
    def visit(value):
        if isinstance(value, list):
            for item in value:
                visit(item)
        if not isinstance(value, dict):
            return
        if isinstance(value.get('model'), str):
            models.add(value['model'])
        if isinstance(value.get('modelUsage'), dict):
            models.update(value['modelUsage'])
        if value.get('type') == 'agent_message':
            finals.append(value.get('text', ''))
        if value.get('type') == 'result' and isinstance(value.get('result'), str):
            finals.append(value['result'])
        if value.get('type') == 'command_execution' and value.get('command'):
            commands.append(dict(command=value['command'][:1200], exit_code=value.get('exit_code')))
        if value.get('type') == 'tool_use' and value.get('name') == 'Bash':
            commands.append(dict(command=str(value.get('input', {}).get('command', ''))[:1200]))
        for child in value.values():
            if isinstance(child, (dict, list)):
                visit(child)
    try:
        visit(json.loads(stdout))
    except json.JSONDecodeError:
        for line in stdout.splitlines():
            try:
                visit(json.loads(line))
            except json.JSONDecodeError:
                pass
    final = '\n'.join(dict.fromkeys(finals))
    return dict(final_response=final[:16000], final_truncated=len(final) > 16000,
                observed_models=sorted(models), command_evidence=commands[:32],
                command_evidence_truncated=len(commands) > 32)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('run-root', 'installed-bin', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    root, binpath, output = args.run_root.resolve(), args.installed_bin.resolve(strict=True), args.output.resolve()
    source = Path(__file__).resolve().parents[4]
    assert not root.exists() and not output.exists(), 'fresh paths required; never overwrite failed evidence'
    assert root != output and root not in output.parents and output not in root.parents
    assert all(path != source and source not in path.parents for path in (root, output)), 'external paths required'
    assert (binpath / 'apparatus').is_file(), 'installed candidate CLI required'
    aliases = [(str(root), '$RUN'), (str(binpath), '$INSTALLED_BIN'), (str(output), '$OUTPUT'), (str(Path.home()), '$HOME')]
    aliases += [(old.replace('/private/tmp/', '/tmp/', 1), new) for old, new in aliases if old.startswith('/private/tmp/')]
    results = dict(runner_sha256=digest(Path(__file__).read_bytes()), apps={},
                   limitations=['Synthetic CLI observations only; no desktop, installer or broad certification.',
                                'Native authentication retained; provider retention and outside-root app metadata are not audited.',
                                'Model identity is reported only when native structured output supplies it.',
                                'Semantic correctness requires review of retained deliverables; command evidence may be absent.',
                                'Cursor IDE unavailable according to launcher; Cursor agent is not a substitute.'])
    results['inventory_scope'] = 'Work area and APPARATUS_HOME, including projects, controls, cache and recovery; native app temporary files/provider metadata are outside Apparatus retention.'
    def save():
        content = json.dumps(results, indent=2, sort_keys=True)
        for old, new in sorted(aliases, key=lambda pair: len(pair[0]), reverse=True):
            content = content.replace(old, new)
        output.write_text(content + '\n', encoding='utf-8')
    root.mkdir(parents=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    for app, model in (('codex', 'gpt-6-luna'), ('claude', 'sonnet')):
        entry = results['apps'][app] = dict(requested_model=model, effort='medium', setup=[], cases=[])
        base, area = root / app, root / app / 'area'
        base.mkdir()
        env = os.environ.copy()
        env.update(PATH=str(binpath) + os.pathsep + env.get('PATH', ''), APPARATUS_HOME=str(base / 'apparatus-home'),
                   PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(base / 'tmp'))
        env.pop('PYTHONPATH', None)
        (base / 'tmp').mkdir()
        def managed_inventory():
            result = {}
            for folder in (area, base / 'apparatus-home'):
                if folder.exists():
                    prefix = folder.relative_to(root).as_posix()
                    result.update({prefix if key == '.' else prefix + '/' + key: value
                                   for key, value in inventory(folder).items()})
            return result
        def cli(*argv):
            text, row = execute([binpath / 'apparatus', *argv], base, env)
            entry['setup'].append(row)
            assert row['exit_code'] == 0 and not row['timed_out'], 'candidate setup command failed'
            return text
        try:
            executable = shutil.which(app)
            assert executable, 'native CLI unavailable'
            entry['version'], entry['version_command'] = execute([executable, '--version'], base, env)
            cli('init', area)
            project = area / 'project'
            project.mkdir()
            (project / 'brief.md').write_text('# Synthetic workshop\n10 participants; 40 minutes. Equipment and owners are unknown.\n')
            cli('project', 'bind', project, '--workspace', area)
            for saving in (True, False):
                task = json.loads(cli('task', 'start', project, '--save-memory' if saving else '--no-memory'))['task_id']
                case = dict(name='first-task' if saving else 'fresh-no-save-continuation', task_id=task, before=managed_inventory())
                entry['cases'].append(case)
                prompt = (f'Read {area}/AGENTS.md and its relevant installed instructions. Work only in this synthetic '
                          f'root: {root}. No network, connectors, other assistants, or files outside that root. Execute '
                          f'the supplied installed apparatus on PATH as needed; its executable may be outside the root. Existing task ID: {task}; inspect and reuse it, '
                          'do not start another task. Read brief.md in the current project. ')
                prompt += ('Save readiness.md in the project: a practical 40-minute plan for 10 participants. '
                           'Explicit Decision: use printed handouts because no projector is available; save that Decision '
                           'to Memory. Other equipment and owners remain unknown. Check and finish the work.' if saving else
                           "Continue this project using current saved evidence. Don't save this task to Memory. Save only "
                           'project/followup.md (followup.md in the current project), with next actions and source links. '
                           'Preserve unresolved equipment and unknown owners; do not invent confirmations. Finish the work.')
                command = ([executable, 'exec', '--ignore-user-config', '--ephemeral', '--skip-git-repo-check', '-s',
                            'workspace-write', '--add-dir', str(root), '-m', model, '-c', 'model_reasoning_effort="medium"',
                            '--json', '-C', str(project)] if app == 'codex' else
                           [executable, '-p', '--model', model, '--effort', 'medium', '--no-session-persistence',
                            '--setting-sources', 'project', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
                            '--permission-mode', 'acceptEdits', '--allowedTools', 'Read,Write,Edit,Bash', '--tools',
                            'Read,Write,Edit,Bash', '--no-chrome', '--add-dir', str(root), '--output-format', 'json'])
                raw, case['execution'] = execute(command + [prompt], project, env, timeout=240)
                case.update(extract(raw))
                case['after'] = managed_inventory()
                case['delta'] = {key: sorted(names) for key, names in dict(added=case['after'].keys() - case['before'].keys(),
                    removed=case['before'].keys() - case['after'].keys(), changed=[k for k in case['before'].keys() & case['after'].keys() if case['before'][k] != case['after'][k]]).items()}
                deliverable = project / ('readiness.md' if saving else 'followup.md')
                case['deliverable'] = deliverable.read_text() if deliverable.is_file() else None
                decisions = [p for p in (area / 'Memory/Decisions').glob('*.md') if str(p.relative_to(root)) not in case['before']]
                case['decisions'] = {str(p.relative_to(root)): p.read_text() for p in decisions}
                failures = []
                if case['execution']['exit_code'] != 0 or case['execution']['timed_out']:
                    failures.append('native process failed or timed out')
                if not case['deliverable']:
                    failures.append('requested deliverable missing or empty')
                if saving and not any('schema: apparatus/decision@v0' in text and 'handout' in text.lower() and 'projector' in text.lower() for text in case['decisions'].values()):
                    failures.append('new handout/projector Decision missing')
                if not saving:
                    key, parent = str(deliverable.relative_to(root)), str(project.relative_to(root))
                    if case['delta']['added'] != [key] or case['delta']['removed'] or set(case['delta']['changed']) - {parent}:
                        failures.append('no-save changed state beyond requested file and its parent')
                    if {k: v for k, v in case['before'][parent].items() if k not in ('size', 'mtime_ns')} != {k: v for k, v in case['after'].get(parent, {}).items() if k not in ('size', 'mtime_ns')}:
                        failures.append('no-save parent changed beyond size/mtime')
                case.update(result='failed' if failures else 'pass', failures=failures)
                save()
        except Exception as error:
            entry['failure'] = f'{type(error).__name__}: {error}'
        save()
    results['result'] = 'pass' if all(not app.get('failure') and len(app['cases']) == 2 and all(c.get('result') == 'pass' for c in app['cases']) for app in results['apps'].values()) else 'failed'
    save()
    return 0 if results['result'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
