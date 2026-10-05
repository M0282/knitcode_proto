from __future__ import annotations
from pathlib import Path

GROUPS = [
    ('test', {'test','tests','testing'}),
    ('config', {'config','configs','settings','setting','conf'}),
    ('model', {'model','models','schema','schemas','entity','entities'}),
    ('api', {'api','apis','route','routes','router','routers','view','views','endpoint','endpoints'}),
    ('service', {'service','services','usecase','usecases','business'}),
    ('data_access', {'db','database','repository','repositories','dao','storage'}),
    ('background_task', {'task','tasks','worker','workers','job','jobs'}),
    ('security', {'auth','authentication','authorization','security'}),
    ('cli', {'cli','command','commands','manage'}),
    ('utility', {'util','utils','helper','helpers','common','commons'}),
]

def _tokens(path: Path) -> set[str]:
    out = set()
    for part in path.parts:
        base = Path(part).stem.lower().replace('-', '_')
        out.add(base)
        out.update(x for x in base.split('_') if x)
    return out


def classify_file(path: Path) -> tuple[str, str]:
    name = path.name.lower()
    tokens = _tokens(path)
    if name.startswith('test_') or name.endswith('_test.py'):
        return 'test', '테스트 파일명 규칙'
    if name == '__init__.py':
        return 'package_init', 'Python package 초기화 파일'
    if name in {'main.py','app.py','wsgi.py','asgi.py'}:
        return 'entrypoint', '대표적인 애플리케이션 진입점 파일명'
    for category, words in GROUPS:
        if tokens & words:
            return category, f'{category} 계열 경로/파일명 규칙'
    return 'module', '특정 역할 규칙과 일치하지 않음'


def classify_function(name: str, decorators: list[str], is_method: bool, is_async: bool) -> list[str]:
    tags = ['method' if is_method else 'function']
    if is_async: tags.append('async')
    n = name.lower(); d = ' '.join(decorators).lower()
    if n.startswith('test_'): tags.append('test')
    if any(x in n for x in ('create','insert','add','save')): tags.append('write_like')
    if any(x in n for x in ('get','read','fetch','find','list','load')): tags.append('read_like')
    if any(x in n for x in ('delete','remove','drop')): tags.append('delete_like')
    if any(x in n for x in ('update','edit','patch','change')): tags.append('update_like')
    if any(x in d for x in ('route','get','post','put','patch','delete')): tags.append('web_endpoint')
    if 'staticmethod' in d: tags.append('staticmethod')
    if 'classmethod' in d: tags.append('classmethod')
    if 'property' in d: tags.append('property')
    return tags
