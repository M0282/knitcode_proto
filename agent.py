"""Isolated, bounded repair loop. Adapter stdin/stdout JSON protocol."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys


def execute(argv, cwd, timeout, payload=None):
    try:
        p = subprocess.run(argv, cwd=cwd, input=payload, capture_output=True, text=True, timeout=timeout)
        return {'returncode': p.returncode, 'stdout': p.stdout[-20000:], 'stderr': p.stderr[-20000:]}
    except subprocess.TimeoutExpired:
        return {'returncode': 124, 'stdout': '', 'stderr': 'timeout'}


def apply_edits(work, edits):
    checked = []
    for edit in edits:
        rel = Path(edit['path'])
        target = (work / rel).resolve()
        if rel.is_absolute() or not target.is_relative_to(work) or any(x.startswith('.') for x in rel.parts):
            raise ValueError('Unsafe edit path: ' + str(rel))
        if not isinstance(edit['content'], str):
            raise ValueError('content must be text')
        checked.append((target, edit['content']))
    for cache in work.rglob('__pycache__'):
        if cache.is_dir() and not cache.is_symlink():
            shutil.rmtree(cache)
    for target, content in checked:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')


def run(args):
    repo, work = Path(args.repo).resolve(), Path(args.work).resolve()
    if work.exists() or work.is_relative_to(repo) or repo.is_relative_to(work):
        raise ValueError('Work directory must be new and outside source repository')
    shutil.copytree(repo, work, ignore=shutil.ignore_patterns('.git', '.venv', 'venv', '__pycache__', 'node_modules', '.env', '.env.*'))
    checks = json.loads(args.checks)
    adapter = json.loads(args.adapter)
    if not checks or not all(isinstance(c, list) and c and all(isinstance(v, str) for v in c) for c in checks):
        raise ValueError('checks must be nonempty argv arrays')
    log = []
    feedback = []
    status = 'attempt_limit'
    for attempt in range(1, args.attempts + 1):
        sources = {}
        for path in work.rglob('*.py'):
            if not any(x.startswith('.') or x in {'venv', '__pycache__'} for x in path.relative_to(work).parts):
                sources[path.relative_to(work).as_posix()] = path.read_text(encoding='utf-8', errors='replace')
        request = {'task': args.task, 'attempt': attempt, 'sources': sources, 'previous_checks': feedback,
                   'response_format': {'edits': [{'path': 'relative/path.py', 'content': 'complete replacement text'}]}}
        response = execute(adapter, work, args.timeout, json.dumps(request))
        entry = {'attempt': attempt, 'adapter': response}
        log.append(entry)
        if response['returncode']:
            status = 'adapter_failed'
            break
        try:
            edits = json.loads(response['stdout'])['edits']
            apply_edits(work, edits)
            entry['edited_paths'] = [e['path'] for e in edits]
        except (ValueError, KeyError, TypeError) as exc:
            status = 'invalid_edits'
            entry['error'] = str(exc)
            break
        feedback = [{'argv': cmd, **execute(cmd, work, args.timeout)} for cmd in checks]
        entry['checks'] = feedback
        if all(c['returncode'] == 0 for c in feedback):
            status = 'checks_passed'
            break
    result = {'status': status, 'work_directory': str(work), 'attempts': log,
              'note': 'Original repository untouched. Passing supplied checks does not prove task correctness.'}
    (work / 'agent_log.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': status, 'work_directory': str(work)}, ensure_ascii=False))
    return 0 if status == 'checks_passed' else 1


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--repo', required=True)
    p.add_argument('--work', required=True)
    p.add_argument('--task', required=True)
    p.add_argument('--adapter', required=True, help='JSON argv array; stdin request -> stdout edits JSON')
    p.add_argument('--checks', required=True, help='JSON array of argv arrays; no shell')
    p.add_argument('--attempts', type=int, default=3)
    p.add_argument('--timeout', type=int, default=120)
    a = p.parse_args()
    if not 1 <= a.attempts <= 10 or a.timeout < 1:
        p.error('attempts 1..10, timeout >=1')
    try:
        sys.exit(run(a))
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
