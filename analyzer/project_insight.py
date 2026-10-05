"""Presentation-ready repository tree, entry points and reading guidance."""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from pathlib import PurePosixPath
from typing import Any


def _tree(paths: list[str]) -> dict[str, Any]:
    root: dict[str, Any] = {}
    for path in sorted(paths):
        cursor = root
        for part in PurePosixPath(path).parts:
            cursor = cursor.setdefault(part, {})
    return root


def _entrypoints(report: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for file in report['files']:
        if PurePosixPath(file['path']).name == '__main__.py':
            items.append({'file': file['path'], 'kind': '__main__.py', 'line': 1, 'calls': []})
        for guard in file.get('main_guards', []):
            items.append({'file': file['path'], 'kind': '__main__ guard', 'line': guard['line'], 'calls': guard['calls']})
    return items


def _reading_guide(report: dict[str, Any], graph: dict[str, Any], entrypoints: list[dict[str, Any]]) -> dict[str, Any]:
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in graph['edges']:
        adjacency[edge['source']].append(edge['target'])
    starts = []
    for entry in entrypoints:
        module = f"{entry['file']}::<module>"
        starts.append(module)
        for call in entry['calls']:
            suffix = f"::{call['callee']}"
            starts.extend(node['id'] for node in graph['nodes'] if node['id'].endswith(suffix))
    if not starts:
        incoming = Counter(edge['target'] for edge in graph['edges'])
        starts = [node['id'] for node in graph['nodes'] if node['type'] == 'module' and not incoming[node['id']]][:5]
    queue = deque((item, 0) for item in dict.fromkeys(starts))
    seen = set()
    order = []
    cycles = []
    while queue and len(order) < 80:
        node, depth = queue.popleft()
        if node in seen:
            cycles.append(node)
            continue
        seen.add(node)
        order.append({'id': node, 'depth': depth})
        for target in adjacency.get(node, []):
            queue.append((target, depth + 1))
    return {
        'strategy': 'entrypoint breadth-first' if entrypoints else 'module roots fallback',
        'order': order,
        'cycles_or_revisits': sorted(set(cycles))[:30],
        'truncated': bool(queue),
    }


def build_project_insight(report: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    entrypoints = _entrypoints(report)
    return {
        'file_tree': _tree([file['path'] for file in report['files']]),
        'excluded_directory_names': sorted({'.git', '.venv', 'venv', 'env', '__pycache__', 'node_modules', 'dist', 'build', '.tox', '.mypy_cache', '.pytest_cache', '.ruff_cache'}),
        'entrypoints': entrypoints,
        'reading_guide': _reading_guide(report, graph, entrypoints),
    }
