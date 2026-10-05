"""Griffe-inspired API surface and change-risk analysis without runtime imports."""
from __future__ import annotations

from typing import Any


def _symbols(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for file in report['files']:
        for item in file['classes']:
            symbol_id = f"{file['path']}::{item['name']}"
            result[symbol_id] = {
                'id': symbol_id, 'file': file['path'], 'name': item['name'], 'kind': 'class',
                'visibility': item['visibility'], 'line': item['line'], 'bases': item['bases'],
                'decorators': item['decorators'], 'documented': bool(item.get('docstring')),
                'docstring': item.get('docstring'),
            }
        for item in file['functions']:
            symbol_id = f"{file['path']}::{item['qualified_name']}"
            result[symbol_id] = {
                'id': symbol_id, 'file': file['path'], 'name': item['qualified_name'],
                'kind': 'method' if item['is_method'] else 'function',
                'visibility': item['visibility'], 'line': item['line'],
                'parameters': item['parameters'], 'return_annotation': item['return_annotation'],
                'decorators': item['decorators'], 'documented': bool(item.get('docstring')),
                'docstring': item.get('docstring'),
            }
    return result


def build_api_surface(report: dict[str, Any]) -> dict[str, Any]:
    symbols = _symbols(report)
    public = [item for item in symbols.values() if item['visibility'] == 'public']
    return {
        'symbols': list(symbols.values()),
        'public_symbols': public,
        'counts': {
            'all': len(symbols),
            'public': len(public),
            'documented_public': sum(1 for item in public if item['documented']),
            'functions': sum(1 for item in symbols.values() if item['kind'] == 'function'),
            'methods': sum(1 for item in symbols.values() if item['kind'] == 'method'),
            'classes': sum(1 for item in symbols.values() if item['kind'] == 'class'),
        },
        'limitations': ['정적 API 모델이므로 export 별칭과 런타임 생성 멤버를 놓칠 수 있습니다.'],
    }


def _signature(item: dict[str, Any]) -> tuple:
    return tuple((p['name'], p['kind'], p.get('annotation'), p.get('default')) for p in item.get('parameters', [])), item.get('return_annotation')


def compare_api(base_report: dict[str, Any] | None, current_report: dict[str, Any]) -> dict[str, Any]:
    if base_report is None:
        return {'available': False, 'breaking': [], 'changes': [], 'reason': '기준 리비전을 지정하지 않았거나 읽을 수 없습니다'}
    before, after = _symbols(base_report), _symbols(current_report)
    changes = []
    for symbol_id in sorted(before.keys() - after.keys()):
        old = before[symbol_id]
        severity = 'breaking' if old['visibility'] == 'public' else 'review'
        changes.append({'symbol': symbol_id, 'kind': 'removed', 'severity': severity, 'detail': '기준 리비전에 있던 심볼이 현재 코드에서 삭제되었습니다.'})
    for symbol_id in sorted(after.keys() - before.keys()):
        changes.append({'symbol': symbol_id, 'kind': 'added', 'severity': 'info', 'detail': '새 심볼이 추가되었습니다.'})
    for symbol_id in sorted(before.keys() & after.keys()):
        old, new = before[symbol_id], after[symbol_id]
        if old['kind'] in {'function', 'method'} and _signature(old) != _signature(new):
            severity = 'breaking' if old['visibility'] == 'public' else 'review'
            changes.append({'symbol': symbol_id, 'kind': 'signature_changed', 'severity': severity, 'detail': '매개변수 또는 반환 타입 주석이 변경되었습니다.'})
        if old['kind'] == 'class' and old.get('bases') != new.get('bases'):
            severity = 'breaking' if old['visibility'] == 'public' else 'review'
            changes.append({'symbol': symbol_id, 'kind': 'bases_changed', 'severity': severity, 'detail': '상속하는 기반 클래스가 변경되었습니다.'})
    return {'available': True, 'breaking': [x for x in changes if x['severity'] == 'breaking'], 'changes': changes}
