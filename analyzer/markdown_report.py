"""Readable Korean Markdown summary backed by the same v0.6 result."""
from __future__ import annotations

from typing import Any


def render_markdown(result: dict[str, Any]) -> str:
    report, impact, history = result['structure'], result['impact'], result['history']
    graph, api, changes = impact['call_graph'], result['api_surface'], result['api_changes']
    insight = result['project_insight']
    s = report['summary']
    lines = [
        f"# {report['repository']['name']} 분석 보고서", '',
        f"- 입력: `{report['repository']['source_url']}`",
        f"- Python 파일: {s['python_file_count']}개 / 코드: {s['code_line_count']:,}줄",
        f"- 클래스: {s['class_count']}개 / 함수·메서드: {s['function_count']}개",
        f"- 호출 해석: {graph['resolved_call_count']}건 / 미해결: {graph['unresolved_call_count']}건",
        f"- Git 이력: {'사용 가능' if history.get('available') else '사용 불가'}", '',
        '## 진입점과 읽기 시작점', '', '|파일|종류|위치|호출|', '|---|---|---:|---|',
    ]
    for item in insight['entrypoints']:
        lines.append(f"|{item['file']}|{item['kind']}|{item['line']}|{', '.join(x['callee'] for x in item['calls']) or '-'}|")
    if not insight['entrypoints']:
        lines.append('|명시적 진입점 없음|구조 기반 대안|-|-|')
    lines += ['', '## 변경 영향 파일', '', '|파일|테스트|근거|함수 후보|', '|---|---|---|---|']
    for item in impact['candidates']:
        evidence = ', '.join(x['kind'] + (': ' + x['via'] if x.get('via') else '') for x in item['evidence'])
        lines.append(f"|{item['path']}|{item['is_test']}|{evidence}|{', '.join(item['function_candidates']) or '-'}|")
    if not impact['candidates']:
        lines.append('|없음|-|-|-|')
    lines += ['', '## 함수 영향 전파', '', '|거리|영향 함수|경유 대상|신뢰도|', '|---:|---|---|---|']
    for item in impact['function_impact']['affected']:
        lines.append(f"|{item['distance']}|{item['id']}|{item['via']}|{item['confidence']}|")
    if not impact['function_impact']['affected']:
        lines.append('|-|-|-|-|')
    lines += ['', '## 테스트 후보', '']
    lines += [f"- `{path}`" for path in impact['test_candidates']] or ['정적으로 연결된 테스트 후보가 없습니다.']
    lines += ['', '## 공개 API', '', f"공개 심볼 {api['counts']['public']}개, 문서화된 공개 심볼 {api['counts']['documented_public']}개입니다.", '']
    if changes['available']:
        lines += ['|심각도|심볼|변화|설명|', '|---|---|---|---|']
        for item in changes['changes']:
            lines.append(f"|{item['severity']}|{item['symbol']}|{item['kind']}|{item['detail']}|")
        if not changes['changes']:
            lines.append('|-|-|변화 없음|-|')
    else:
        lines.append(f"API 변화 비교 대기: {changes['reason']}. `--base HEAD~1`로 활성화할 수 있습니다.")
    lines += ['', '## 미해결 호출 분류', '']
    labels = {'builtin':'Python 내장 함수','external_import':'외부 라이브러리','dynamic_attribute':'동적 객체·속성','unknown_name':'정의 미확인 이름'}
    for reason, count in graph.get('unresolved_reason_counts', {}).items():
        lines.append(f"- {labels.get(reason, reason)}: {count}건")
    lines += ['', '## 분석 한계', '',
              '- 동적 import, fixture 주입, monkeypatch, 콜백과 런타임 디스패치를 놓칠 수 있습니다.',
              '- Git 동시 수정은 코드 의존성이 아니라 경험적 상관관계입니다.',
              '- 낮은 신뢰도의 이름 기반 호출 추정은 직접 검토해야 합니다.',
              '- 테스트 미검출은 테스트 영향이 없다는 뜻이 아닙니다.']
    return '\n'.join(lines) + '\n'
