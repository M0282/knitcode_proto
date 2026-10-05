"""Conservative file-level impact candidates; never claims runtime reachability."""
from collections import Counter, defaultdict, deque
from itertools import combinations
from pathlib import Path
import subprocess

from analyzer.call_graph import build_call_graph


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True, check=True).stdout


def history(repo, limit=500, max_files=30):
    try:
        hashes = git(repo, 'log', '--no-merges', f'-{limit}', '--format=%H').splitlines()
        shallow = git(repo, 'rev-parse', '--is-shallow-repository').strip() == 'true'
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {'available': False, 'pairs': [], 'reason': 'Git repository/history unavailable'}
    counts, pairs = Counter(), Counter()
    skipped = 0
    for commit in hashes:
        names = git(repo, 'diff-tree', '--root', '--no-commit-id', '--name-only', '-r', '-z', commit).split('\0')
        names = sorted(set(n for n in names if n.endswith('.py')))
        if len(names) > max_files:
            skipped += 1
            continue
        counts.update(names)
        pairs.update(combinations(names, 2))
    return {'available': True, 'shallow': shallow, 'commits_scanned': len(hashes), 'large_commits_skipped': skipped,
            'pairs': [{'files': list(pair), 'count': n, 'jaccard': round(n / (counts[pair[0]] + counts[pair[1]] - n), 4)} for pair, n in pairs.most_common()]}


def module_name(path):
    parts = list(Path(path).with_suffix('').parts)
    if parts and parts[0] == 'src':
        parts.pop(0)
    if parts[-1] == '__init__':
        parts.pop()
    return '.'.join(parts)


def connections(report):
    modules = defaultdict(list)
    for f in report['files']:
        modules[module_name(f['path'])].append(f['path'])
    edges = []
    for f in report['files']:
        package = module_name(f['path']).split('.')
        if Path(f['path']).name != '__init__.py':
            package = package[:-1]
        for imp in f['imports']:
            raw = imp['module']
            level = len(raw) - len(raw.lstrip('.'))
            base = raw.lstrip('.')
            if level:
                base = '.'.join(package[:len(package) - level + 1] + ([base] if base else []))
            candidates = [base]
            if imp.get('name') and imp['name'] != '*':
                candidates.insert(0, base + '.' + imp['name'] if base else imp['name'])
            for name in candidates:
                targets = modules.get(name, [])
                if len(targets) == 1:
                    edges.append({'source': f['path'], 'target': targets[0], 'kind': 'import', 'line': imp['line'], 'symbol': imp.get('name'), 'confidence': 'static'})
                    break
    return edges


def _function_impact(report, graph, changed, changed_symbols=None):
    changed_set = set(changed)
    reverse = defaultdict(list)
    for edge in graph['edges']:
        reverse[edge['target']].append(edge)

    if changed_symbols:
        seeds = set(changed_symbols)
    else:
        seeds = set()
        for file in report['files']:
            if file['path'] not in changed_set:
                continue
            seeds.add(f"{file['path']}::<module>")
            seeds.update(f"{file['path']}::{item['qualified_name']}" for item in file['functions'])
            seeds.update(f"{file['path']}::{item['name']}" for item in file['classes'])

    node_map = {node['id']: node for node in graph['nodes']}
    queue = deque((seed, 0) for seed in seeds)
    seen = set(seeds)
    results = []
    while queue:
        target, distance = queue.popleft()
        for edge in reverse.get(target, []):
            caller = edge['source']
            if caller in seen:
                continue
            seen.add(caller)
            node = node_map.get(caller, {'file': caller.split('::', 1)[0], 'name': caller.split('::', 1)[-1], 'type': 'function'})
            results.append({'id': caller, 'file': node['file'], 'function': node['name'], 'type': node['type'],
                            'distance': distance + 1, 'via': target, 'line': edge['line'], 'confidence': edge['confidence']})
            queue.append((caller, distance + 1))
    return {'changed_symbols': sorted(seeds), 'affected': sorted(results, key=lambda x: (x['distance'], x['file'], x['function']))}


def predict(report, changed, hist, min_shared=2, changed_symbols=None):
    known = {f['path']: f for f in report['files']}
    changed = sorted(set(changed))
    edges = connections(report)
    call_graph = build_call_graph(report)
    function_impact = _function_impact(report, call_graph, changed, changed_symbols)
    reverse = defaultdict(list)
    for e in edges:
        reverse[e['target']].append(e['source'])
    reasons = defaultdict(list)
    queue = deque(changed)
    seen = set(changed)
    for p in changed:
        reasons[p].append({'kind': 'changed'})
    while queue:
        target = queue.popleft()
        for source in reverse[target]:
            reasons[source].append({'kind': 'imports_affected_file', 'via': target})
            if source not in seen:
                seen.add(source)
                queue.append(source)
    for item in function_impact['affected']:
        if item['file'] not in changed:
            reasons[item['file']].append({'kind': 'calls_changed_function', 'via': item['via'], 'function': item['function'], 'distance': item['distance'], 'confidence': item['confidence']})
    # Historical candidates remain separate and do not seed structural traversal.
    for pair in hist['pairs']:
        a, b = pair['files']
        if pair['count'] >= min_shared:
            for source, target in [(a, b), (b, a)]:
                if source in changed and target in known:
                    reasons[target].append({'kind': 'historical_cochange', 'via': source, 'count': pair['count'], 'jaccard': pair['jaccard']})
    items = []
    functions_by_file = defaultdict(list)
    for item in function_impact['affected']:
        functions_by_file[item['file']].append(item['function'])
    for file in report['files']:
        if file['path'] in changed:
            functions_by_file[file['path']].extend(fn['qualified_name'] for fn in file.get('functions', []))
    for p, evidence in sorted(reasons.items()):
        f = known.get(p, {})
        is_test = any(x.startswith('test') for x in Path(p).parts) or Path(p).stem.endswith('_test')
        candidates = sorted(set(functions_by_file[p]))
        items.append({'path': p, 'is_test': is_test, 'evidence': evidence,
                      'function_candidates': candidates,
                      'function_scope': 'call-graph candidates' if candidates else 'no function-level call evidence'})
    return {'changed': changed, 'unknown_or_deleted': [p for p in changed if p not in known], 'import_edges': edges,
            'call_graph': call_graph, 'function_impact': function_impact,
            'candidates': items, 'test_candidates': [i['path'] for i in items if i['is_test']],
            'limitations': ['Static analysis can miss dynamic imports, fixtures, monkeypatching, callbacks and runtime dispatch.',
                            'Co-change is correlation, not a dependency. Lower-confidence heuristic call edges require review.']}
