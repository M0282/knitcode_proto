"""Best-effort, evidence-labelled Python call graph construction."""
from __future__ import annotations

from collections import defaultdict
import builtins
from pathlib import Path
from typing import Any


def _module_name(path: str) -> str:
    parts = list(Path(path).with_suffix('').parts)
    if parts and parts[0] == 'src':
        parts.pop(0)
    if parts and parts[-1] == '__init__':
        parts.pop()
    return '.'.join(parts)


def _absolute_module(file_path: str, raw: str) -> str:
    level = len(raw) - len(raw.lstrip('.'))
    base = raw.lstrip('.')
    if not level:
        return base
    package = _module_name(file_path).split('.')
    if Path(file_path).name != '__init__.py':
        package = package[:-1]
    keep = max(0, len(package) - level + 1)
    return '.'.join(package[:keep] + ([base] if base else []))


def build_call_graph(report: dict[str, Any]) -> dict[str, Any]:
    """Resolve common Python call forms without claiming runtime certainty."""
    nodes: dict[str, dict[str, Any]] = {}
    function_ids: dict[tuple[str, str], str] = {}
    class_ids: dict[tuple[str, str], str] = {}
    functions_by_name: dict[str, list[str]] = defaultdict(list)
    classes_by_name: dict[str, list[str]] = defaultdict(list)
    module_files: dict[str, list[str]] = defaultdict(list)
    files = {item['path']: item for item in report['files']}

    for file in report['files']:
        path = file['path']
        module_files[_module_name(path)].append(path)
        module_id = f'{path}::<module>'
        nodes[module_id] = {'id': module_id, 'type': 'module', 'file': path, 'name': '<module>'}
        for cls in file['classes']:
            node_id = f"{path}::{cls['name']}"
            nodes[node_id] = {'id': node_id, 'type': 'class', 'file': path, 'name': cls['name'], 'line': cls['line']}
            class_ids[(path, cls['name'])] = node_id
            classes_by_name[cls['name']].append(node_id)
        for fn in file['functions']:
            node_id = f"{path}::{fn['qualified_name']}"
            node_type = 'method' if fn['is_method'] else 'function'
            nodes[node_id] = {'id': node_id, 'type': node_type, 'file': path, 'name': fn['qualified_name'], 'line': fn['line']}
            function_ids[(path, fn['qualified_name'])] = node_id
            functions_by_name[fn['name']].append(node_id)

    def single_module(name: str) -> str | None:
        candidates = module_files.get(name, [])
        return candidates[0] if len(candidates) == 1 else None

    bindings: dict[str, dict[str, dict[str, str]]] = {}
    for path, file in files.items():
        table: dict[str, dict[str, str]] = {}
        for imp in file['imports']:
            if imp['type'] == 'import':
                module = _absolute_module(path, imp['module'])
                visible = imp.get('alias') or module.split('.')[0]
                table[visible] = {'kind': 'module', 'module': module if imp.get('alias') else visible}
                if not imp.get('alias'):
                    table[module] = {'kind': 'module', 'module': module}
            else:
                module = _absolute_module(path, imp['module'])
                visible = imp.get('alias') or imp.get('name')
                if visible:
                    table[visible] = {'kind': 'symbol', 'module': module, 'symbol': imp.get('name', '')}
        bindings[path] = table

    def imported_target(path: str, visible: str, remainder: str = '') -> tuple[str | None, str | None]:
        binding = bindings[path].get(visible)
        if not binding:
            return None, None
        if binding['kind'] == 'module':
            module = binding['module']
            target_file = single_module(module)
            return target_file, remainder or None
        module = binding['module']
        symbol = binding['symbol']
        submodule_file = single_module('.'.join(x for x in (module, symbol) if x))
        if submodule_file:
            return submodule_file, remainder or None
        target_file = single_module(module)
        qualified = '.'.join(x for x in (symbol, remainder) if x)
        return target_file, qualified or None

    def definition(path: str | None, qualified: str | None) -> str | None:
        if not path or not qualified:
            return None
        return function_ids.get((path, qualified)) or class_ids.get((path, qualified))

    def resolve_constructor(path: str, name: str) -> str | None:
        if '.' in name:
            prefix, remainder = name.split('.', 1)
            imported_file, qualified = imported_target(path, prefix, remainder)
            found = definition(imported_file, qualified)
            if found and nodes[found]['type'] == 'class':
                return found
        imported_file, qualified = imported_target(path, name)
        found = definition(imported_file, qualified)
        if found and nodes[found]['type'] == 'class':
            return found
        found = class_ids.get((path, name))
        if found:
            return found
        candidates = classes_by_name.get(name.split('.')[-1], [])
        return candidates[0] if len(candidates) == 1 else None

    instance_tables: dict[str, dict[tuple[str | None, str], str]] = defaultdict(dict)
    for path, file in files.items():
        for item in file.get('instances', []):
            constructor = resolve_constructor(path, item['constructor'])
            if constructor:
                instance_tables[path][(item.get('inside_function'), item['name'])] = constructor

    edges: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, int]] = set()
    builtin_names = set(dir(builtins))
    for path, file in files.items():
        for call in file['calls']:
            caller_name = call.get('inside_function') or '<module>'
            caller = f'{path}::{caller_name}'
            callee = call['callee']
            target = None
            confidence = 'static'

            if callee.startswith('self.') and call.get('inside_class'):
                target = function_ids.get((path, f"{call['inside_class']}.{callee.split('.', 1)[1]}"))
            elif '.' in callee:
                prefix, remainder = callee.split('.', 1)
                constructor = instance_tables[path].get((call.get('inside_function'), prefix)) or instance_tables[path].get((None, prefix))
                if constructor:
                    class_name = nodes[constructor]['name']
                    target = function_ids.get((nodes[constructor]['file'], f'{class_name}.{remainder}'))
                    confidence = 'inferred_instance'
                if not target:
                    imported_file, qualified = imported_target(path, prefix, remainder)
                    target = definition(imported_file, qualified)
            else:
                target = function_ids.get((path, callee)) or class_ids.get((path, callee))
                if not target:
                    imported_file, qualified = imported_target(path, callee)
                    target = definition(imported_file, qualified)
                if not target:
                    candidates = functions_by_name.get(callee, []) + classes_by_name.get(callee, [])
                    if len(candidates) == 1:
                        target = candidates[0]
                        confidence = 'unique_name_heuristic'

            if target:
                edge_key = (caller, target, call['line'])
                if edge_key not in seen_edges:
                    edge_type = 'instantiates' if nodes[target]['type'] == 'class' else 'calls'
                    edges.append({'source': caller, 'target': target, 'type': edge_type, 'line': call['line'], 'callee': callee, 'confidence': confidence})
                    seen_edges.add(edge_key)
            else:
                prefix = callee.split('.', 1)[0]
                binding = bindings[path].get(prefix)
                if callee in builtin_names:
                    reason = 'builtin'
                elif binding and single_module(binding.get('module', '')) is None:
                    reason = 'external_import'
                elif '.' in callee:
                    reason = 'dynamic_attribute'
                else:
                    reason = 'unknown_name'
                unresolved.append({'caller': caller, 'callee': callee, 'line': call['line'], 'reason': reason})

    used = {edge['source'] for edge in edges} | {edge['target'] for edge in edges}
    reason_counts: dict[str, int] = defaultdict(int)
    for item in unresolved:
        reason_counts[item['reason']] += 1
    return {
        'nodes': [nodes[node_id] for node_id in sorted(used)],
        'edges': edges,
        'resolved_call_count': len(edges),
        'unresolved_call_count': len(unresolved),
        'unresolved_reason_counts': dict(sorted(reason_counts.items(), key=lambda x: (-x[1], x[0]))),
        'unresolved_calls': unresolved,
        'unresolved_examples': unresolved[:50],
        'limitations': [
            '정적 규칙 기반 해석이므로 동적 import, 콜백, 데코레이터와 다형성 호출을 놓칠 수 있습니다.',
            'unique_name_heuristic 관계는 낮은 신뢰도의 검토 후보입니다.',
        ],
    }
