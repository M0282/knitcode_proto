"""Self-contained detailed HTML report for v0.6 analysis results."""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any


def _e(value: Any) -> str:
    return escape(str(value), quote=True)


def _empty(rows: list[str], columns: int, message: str) -> str:
    return ''.join(rows) if rows else f'<tr><td colspan="{columns}" class="empty">{_e(message)}</td></tr>'


def _signature(symbol: dict[str, Any]) -> str:
    parts = []
    for param in symbol.get('parameters', []):
        name = param['name']
        if param['kind'] == 'var_positional': name = '*' + name
        if param['kind'] == 'var_keyword': name = '**' + name
        if param.get('annotation'): name += ': ' + param['annotation']
        if param.get('default') is not None: name += ' = ' + param['default']
        parts.append(name)
    result = f"{symbol['name']}({', '.join(parts)})"
    if symbol.get('return_annotation'):
        result += ' -> ' + symbol['return_annotation']
    return result


def _tree_html(tree: dict[str, Any]) -> str:
    def render(node: dict[str, Any]) -> str:
        rows = []
        for name, children in node.items():
            icon = '📁' if children else '🐍'
            rows.append(f'<li><span>{icon} {_e(name)}</span>{render(children) if children else ""}</li>')
        return '<ul>' + ''.join(rows) + '</ul>' if rows else ''
    return render(tree)


EVIDENCE = {
    'changed': '직접 변경', 'imports_affected_file': '변경 파일을 import',
    'calls_changed_function': '변경 함수를 호출', 'historical_cochange': 'Git 동시 수정',
}
UNRESOLVED = {
    'builtin': 'Python 내장 함수', 'external_import': '외부 라이브러리 호출',
    'dynamic_attribute': '동적 객체·속성 호출', 'unknown_name': '정의를 찾지 못한 이름',
}


def _evidence(items: list[dict[str, Any]]) -> str:
    result = []
    for item in items:
        detail = f" · {_e(item['via'])}" if item.get('via') else ''
        result.append(f'<span class="tag">{_e(EVIDENCE.get(item["kind"], item["kind"]))}{detail}</span>')
    return ''.join(result)


def _risk(item: dict[str, Any]) -> tuple[str, str]:
    kinds = {x['kind'] for x in item['evidence']}
    if 'changed' in kinds: return 'high', '변경'
    if kinds & {'calls_changed_function', 'imports_affected_file'}: return 'medium', '검토'
    return 'low', '참고'


def render_html(result: dict[str, Any]) -> str:
    report, impact, history = result['structure'], result['impact'], result['history']
    graph, api = impact['call_graph'], result['api_surface']
    changes, insight = result['api_changes'], result.get('project_insight', {})
    summary, files = report['summary'], report['files']
    repo = report['repository']['name'] or 'Python Repository'
    source = report['repository'].get('source_url', '')
    candidates, affected = impact['candidates'], impact['function_impact']['affected']
    tests = [x for x in candidates if x['is_test']]
    public_count = api['counts']['public']
    documented = api['counts']['documented_public']
    doc_rate = round(documented / public_count * 100) if public_count else 0

    scope_rows = [
        ('분석기', report['analyzer']['name']), ('입력', source), ('파서', report['analyzer']['parser']),
        ('분석 범위', report['analyzer']['scope']), ('Git 이력', '사용 가능' if history.get('available') else '사용 불가'),
        ('분석 커밋', history.get('commits_scanned', 0)), ('얕은 clone', history.get('shallow', False)),
    ]
    entry_rows = []
    for item in insight.get('entrypoints', []):
        calls = ', '.join(x['callee'] for x in item['calls']) or '모듈 진입'
        entry_rows.append(f'<tr><td><code>{_e(item["file"])}:{item["line"]}</code></td><td>{_e(item["kind"])}</td><td>{_e(calls)}</td></tr>')
    guide = insight.get('reading_guide', {})
    read_rows = [f'<li><span class="depth">{x["depth"]}</span><code>{_e(x["id"])}</code></li>' for x in guide.get('order', [])]
    guide_note = []
    if guide.get('cycles_or_revisits'):
        guide_note.append(f"순환·재방문 {len(guide['cycles_or_revisits'])}건")
    if guide.get('truncated'):
        guide_note.append('탐색 상한으로 일부 순서 생략')

    candidate_rows = []
    for item in candidates:
        level, label = _risk(item)
        functions = ', '.join(item['function_candidates'][:8])
        if len(item['function_candidates']) > 8: functions += f' 외 {len(item["function_candidates"])-8}개'
        candidate_rows.append(f'<tr data-search="{_e(item["path"]+" "+functions)}"><td><span class="risk {level}">{label}</span></td><td><code>{_e(item["path"])}</code>{"<b class=\"test\">TEST</b>" if item["is_test"] else ""}</td><td><div class="tags">{_evidence(item["evidence"])}</div></td><td>{_e(functions or "파일 단위 후보")}</td></tr>')
    test_rows = [f'<tr><td><code>{_e(x["path"])}</code></td><td>{_e(", ".join(x["function_candidates"]) or "파일 단위 후보")}</td><td>{_evidence(x["evidence"])}</td></tr>' for x in tests]
    affected_rows = [f'<tr><td><span class="distance">{x["distance"]}</span></td><td><code>{_e(x["id"])}</code></td><td><code>{_e(x["via"])}</code></td><td><span class="tag">{_e(x["confidence"])}</span></td></tr>' for x in affected]

    import_rows = [f'<tr data-search="{_e(x["source"]+" "+x["target"])}"><td><code>{_e(x["source"])}</code></td><td>→</td><td><code>{_e(x["target"])}</code></td><td>{x["line"]}</td><td>{_e(x.get("symbol") or "module")}</td></tr>' for x in impact['import_edges']]
    call_rows = [f'<tr data-search="{_e(x["source"]+" "+x["target"])}"><td><code>{_e(x["source"])}</code></td><td>→</td><td><code>{_e(x["target"])}</code></td><td>{x["line"]}</td><td><span class="tag">{_e(x["confidence"])}</span></td></tr>' for x in graph['edges']]
    unresolved_rows = [f'<tr data-search="{_e(x["caller"]+" "+x["callee"]+" "+x.get("reason", ""))}"><td><code>{_e(x["caller"])}</code></td><td><code>{_e(x["callee"])}</code></td><td>{x["line"]}</td><td>{_e(UNRESOLVED.get(x.get("reason"), x.get("reason", "기타")))}</td></tr>' for x in graph.get('unresolved_calls', graph.get('unresolved_examples', []))]

    api_rows = []
    for x in api['public_symbols']:
        sig = _signature(x) if x['kind'] in {'function', 'method'} else x['name'] + ('(' + ', '.join(x.get('bases', [])) + ')' if x.get('bases') else '')
        api_rows.append(f'<tr data-search="{_e(x["id"]+" "+sig+" "+(x.get("docstring") or ""))}"><td>{_e(x["kind"])}</td><td><code>{_e(x["file"])}:{x["line"]}</code></td><td><code>{_e(sig)}</code></td><td>{_e(x.get("docstring") or "없음")}</td></tr>')
    change_rows = [f'<tr><td><span class="risk {"high" if x["severity"]=="breaking" else "low"}">{_e(x["severity"])}</span></td><td><code>{_e(x["symbol"])}</code></td><td>{_e(x["kind"])}</td><td>{_e(x["detail"])}</td></tr>' for x in changes.get('changes', [])]

    detail_cards = []
    for file in files:
        definitions = []
        for cls in file['classes']:
            definitions.append(f'<li><b>class</b> <code>{_e(cls["name"])}</code> · L{cls["line"]}{f" · extends {_e(', '.join(cls['bases']))}" if cls["bases"] else ""}<p>{_e(cls.get("docstring") or "docstring 없음")}</p></li>')
        for fn in file['functions']:
            definitions.append(f'<li><b>{"async " if fn["is_async"] else ""}{"method" if fn["is_method"] else "function"}</b> <code>{_e(_signature({**fn,"name":fn["qualified_name"]}))}</code> · L{fn["line"]}<p>{_e(fn.get("docstring") or "docstring 없음")}</p></li>')
        imports = [f'<li><code>L{x["line"]}</code> {_e(x["type"])} {_e(x["module"])}{(" import "+_e(x.get("name"))) if x.get("name") else ""}{(" as "+_e(x.get("alias"))) if x.get("alias") else ""}</li>' for x in file['imports']]
        detail_cards.append(f'<details data-search="{_e(file["path"])}"><summary><code>{_e(file["path"])}</code><span>{file["code_lines"]} lines · {len(file["classes"])} classes · {len(file["functions"])} functions · {_e(file["parse_status"])} · {_e(file.get("encoding", "unknown"))}</span></summary><div class="file-detail"><h4>모듈 설명</h4><p>{_e(file.get("module_docstring") or "docstring 없음")}</p><h4>정의와 선언</h4><ul>{"".join(definitions) or "<li>정의 없음</li>"}</ul><h4>Import</h4><ul>{"".join(imports) or "<li>import 없음</li>"}</ul></div></details>')

    cochange_rows = []
    changed_set = set(impact['changed'])
    for x in [p for p in history.get('pairs', []) if changed_set.intersection(p['files'])][:50]:
        cochange_rows.append(f'<tr><td><code>{_e(x["files"][0])}</code> ↔ <code>{_e(x["files"][1])}</code></td><td>{x["count"]}</td><td>{x["jaccard"]:.3f}</td></tr>')
    diagnostics = []
    for file in files:
        if file.get('syntax_error'):
            diagnostics.append(f'<li><span class="risk high">오류</span> <code>{_e(file["path"])}:{file["syntax_error"].get("line", "-")}</code> {_e(file["syntax_error"]["message"])}</li>')
        for warning in file.get('syntax_warnings', []):
            diagnostics.append(f'<li><span class="risk medium">경고</span> <code>{_e(file["path"])}:{warning.get("line", "-")}</code> {_e(warning["message"])}</li>')
        for diagnostic in file.get('read_diagnostics', []):
            diagnostics.append(f'<li><span class="risk medium">읽기</span> <code>{_e(file["path"])}</code> {_e(diagnostic["message"])}</li>')

    generated = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    source_line = f'<a href="{_e(source)}">{_e(source)}</a>' if str(source).startswith('https://') else _e(source)
    reason_cards = ''.join(f'<div class="mini"><strong>{count}</strong><span>{_e(UNRESOLVED.get(reason, reason))}</span></div>' for reason, count in graph.get('unresolved_reason_counts', {}).items())
    scope_table = ''.join(f'<tr><th>{_e(k)}</th><td>{_e(v)}</td></tr>' for k, v in scope_rows)

    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{_e(repo)} · 분석 보고서</title>
<style>
:root{{--ink:#151515;--paper:#f3f0ff;--card:#fff;--green:#14a66a;--dark:#087348;--pink:#ff4f9a;--orange:#ff6a3d;--line:#dcd7ec;--muted:#6e6a78;--shadow:0 18px 55px rgba(35,22,61,.1)}}*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--paper);color:var(--ink);font-family:Arial,"Noto Sans KR",sans-serif;line-height:1.55}}a{{color:inherit}}code{{font-family:Consolas,"Cascadia Code",monospace;overflow-wrap:anywhere}}.nav{{position:sticky;top:0;z-index:10;display:flex;justify-content:space-between;align-items:center;padding:14px 4vw;background:rgba(243,240,255,.94);border-bottom:1px solid #d9d3e9;backdrop-filter:blur(12px)}}.brand{{font-weight:900}}.navlinks{{display:flex;gap:18px;font-size:13px}}.nav a{{text-decoration:none}}.pill{{display:inline-flex;padding:10px 15px;border-radius:999px;background:var(--ink);color:#fff;font-weight:800}}.wrap{{width:min(1220px,92vw);margin:auto}}.hero{{position:relative;min-height:570px;margin:28px 0 72px;padding:58px clamp(28px,6vw,82px);overflow:hidden;border-radius:38px;background:var(--green);color:#fff}}.eyebrow{{display:inline-flex;padding:7px 12px;border:1px solid #ffffff80;border-radius:999px;font-size:12px;font-weight:800}}h1{{max-width:650px;margin:28px 0 18px;font-size:clamp(54px,7.2vw,92px);line-height:.89;letter-spacing:-.07em}}.hero-copy{{max-width:560px}}.metrics{{position:absolute;right:52px;top:46px;display:grid;grid-template-columns:repeat(2,145px);gap:12px}}.metric{{padding:18px;border:2px solid var(--ink);border-radius:18px;background:#fff;color:var(--ink);box-shadow:7px 7px 0 var(--ink)}}.metric strong{{display:block;color:var(--orange);font-size:35px;line-height:1}}.metric span{{font-size:11px;font-weight:900}}.ribbon{{position:absolute;right:-100px;bottom:115px;width:440px;height:22px;border-radius:999px;background:var(--ink);transform:rotate(-17deg)}}.ribbon.pink{{bottom:72px;width:350px;background:var(--pink)}}section{{margin-bottom:76px;scroll-margin-top:85px}}.head{{display:flex;justify-content:space-between;align-items:end;gap:20px;margin-bottom:20px}}.kicker{{margin:0 0 5px;color:var(--dark);font-size:11px;font-weight:900;letter-spacing:.12em}}h2{{margin:0;font-size:clamp(32px,5vw,58px);line-height:1;letter-spacing:-.05em}}.note{{max-width:450px;color:var(--muted)}}.grid4{{display:grid;grid-template-columns:repeat(4,1fr);gap:13px}}.stat,.mini{{padding:20px;border:1px solid var(--line);border-radius:20px;background:#fff}}.stat strong,.mini strong{{display:block;font-size:36px;line-height:1}}.stat span,.mini span{{color:var(--muted);font-size:12px}}.panel{{overflow:auto;border:1px solid var(--line);border-radius:23px;background:#fff;box-shadow:var(--shadow)}}.toolbar{{display:flex;justify-content:space-between;gap:12px;padding:16px 18px;border-bottom:1px solid var(--line)}}.search{{width:min(360px,100%);padding:10px 13px;border:1px solid var(--line);border-radius:999px;background:#faf9ff;font:inherit}}table{{width:100%;border-collapse:collapse}}th,td{{padding:13px 16px;border-bottom:1px solid #eeeaf6;text-align:left;vertical-align:top;font-size:13px}}thead th{{background:#faf9ff;color:var(--muted);font-size:10px;letter-spacing:.07em;text-transform:uppercase}}tbody tr:last-child td{{border-bottom:0}}.tags{{display:flex;flex-wrap:wrap;gap:5px}}.tag{{display:inline-flex;padding:4px 8px;border-radius:999px;background:#e7f7ef;color:var(--dark);font-size:10px;font-weight:800}}.risk{{display:inline-flex;padding:4px 8px;border-radius:999px;font-size:10px;font-weight:900}}.high{{background:#ffe0d6;color:#9d2b0c}}.medium{{background:#fff0b9;color:#755800}}.low{{background:#e7f7ef;color:#087348}}.test{{margin-left:7px;padding:3px 6px;border-radius:5px;background:#151515;color:#fff;font-size:9px}}.distance,.depth{{display:inline-grid;width:28px;height:28px;place-items:center;border-radius:50%;background:var(--pink);color:#fff;font-weight:900}}.empty{{padding:30px;text-align:center;color:var(--muted)}}.split{{display:grid;grid-template-columns:1fr 1fr;gap:15px}}.card{{padding:22px;border:1px solid var(--line);border-radius:22px;background:#fff}}.tree ul{{margin:4px 0;padding-left:22px;list-style:none}}.tree li>span{{display:inline-block;padding:3px 0}}.read-list{{max-height:470px;overflow:auto;margin:0;padding:0;list-style:none}}.read-list li{{display:flex;gap:10px;align-items:center;padding:8px;border-bottom:1px solid #eeeaf6}}.reason-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px}}.mini strong{{font-size:28px;color:var(--orange)}}details{{border-bottom:1px solid var(--line);background:#fff}}details:last-child{{border-bottom:0}}summary{{display:flex;justify-content:space-between;gap:20px;padding:17px 20px;cursor:pointer;font-weight:800}}summary span{{color:var(--muted);font-size:12px;font-weight:400}}.file-detail{{padding:0 22px 22px}}.file-detail h4{{margin:20px 0 7px}}.file-detail p{{margin:4px 0;color:var(--muted);white-space:pre-wrap}}.callout{{padding:20px;border-radius:18px;background:#ebe6ff}}.diagnostics{{margin:0;padding:18px 24px}}.diagnostics li{{margin:9px 0}}footer{{padding:42px 4vw;background:#151515;color:#fff}}footer .wrap{{display:flex;justify-content:space-between;gap:25px}}footer p{{margin:0;color:#bbb}}[hidden]{{display:none!important}}
@media(max-width:920px){{.metrics{{position:relative;right:auto;top:auto;margin-top:30px;max-width:390px}}.hero{{min-height:auto}}.navlinks{{display:none}}.grid4,.reason-grid{{grid-template-columns:repeat(2,1fr)}}.split{{grid-template-columns:1fr}}.head{{display:block}}.note{{margin-top:10px}}}}@media(max-width:560px){{.hero{{padding:38px 23px;border-radius:25px}}h1{{font-size:51px}}.metrics{{grid-template-columns:1fr 1fr}}.metric{{padding:13px}}.metric strong{{font-size:27px}}.grid4{{grid-template-columns:1fr 1fr}}summary{{display:block}}summary span{{display:block;margin-top:6px}}footer .wrap{{display:block}}}}
</style></head><body>
<nav class="nav"><div class="brand">Impact Lab <small>v0.6</small></div><div class="navlinks"><a href="#scope">범위</a><a href="#impact">영향</a><a href="#relations">관계</a><a href="#api">API</a><a href="#details">파일 상세</a></div><a class="pill" href="#diagnostics">진단</a></nav>
<main class="wrap"><header class="hero"><span class="eyebrow">Python repository analysis</span><h1>구조부터 영향까지<br>한 번에 읽다.</h1><p class="hero-copy"><strong>{_e(repo)}</strong>의 AST 구조, Git 이력, import, 함수 호출, 테스트와 공개 API를 함께 분석했습니다.<br>{source_line}</p><a class="pill" href="#impact">분석 결과 보기 →</a><div class="metrics"><div class="metric"><strong>{len(candidates)}</strong><span>영향 파일</span></div><div class="metric"><strong>{len(tests)}</strong><span>테스트 후보</span></div><div class="metric"><strong>{len(affected)}</strong><span>영향 함수</span></div><div class="metric"><strong>{len(changes.get('breaking', []))}</strong><span>API 위험</span></div></div><div class="ribbon"></div><div class="ribbon pink"></div></header>

<section id="scope"><div class="head"><div><p class="kicker">01 · SCOPE</p><h2>분석 범위</h2></div><p class="note">어떤 입력을 어떤 규칙으로 분석했는지 먼저 확인합니다.</p></div><div class="split"><div class="panel"><table><tbody>{scope_table}</tbody></table></div><div class="grid4"><div class="stat"><strong>{summary['python_file_count']}</strong><span>Python 파일</span></div><div class="stat"><strong>{summary['function_count']}</strong><span>함수·메서드</span></div><div class="stat"><strong>{summary['class_count']}</strong><span>클래스</span></div><div class="stat"><strong>{summary['code_line_count']:,}</strong><span>코드 라인</span></div></div></div></section>

<section id="start"><div class="head"><div><p class="kicker">02 · START POINTS</p><h2>진입점과 읽기 안내</h2></div><p class="note"><code>__main__.py</code>와 main guard를 우선하고, 없으면 호출 그래프의 모듈 루트를 사용합니다.</p></div><div class="split"><div class="panel"><table><thead><tr><th>위치</th><th>종류</th><th>첫 호출</th></tr></thead><tbody>{_empty(entry_rows,3,'명시적 진입점을 찾지 못해 구조 기반 대안을 사용했습니다.')}</tbody></table></div><div class="card"><strong>권장 읽기 순서 · {_e(guide.get('strategy','-'))}</strong>{f'<p class="note">{_e(" · ".join(guide_note))}</p>' if guide_note else ''}<ul class="read-list">{''.join(read_rows) or '<li>호출 그래프 기반 순서를 만들 수 없습니다.</li>'}</ul></div></div></section>

<section id="tree"><div class="head"><div><p class="kicker">03 · FILE TREE</p><h2>파일 구조</h2></div><p class="note">분석한 Python 파일만 표시합니다. 제외 디렉터리: {_e(', '.join(insight.get('excluded_directory_names', [])))}</p></div><div class="card tree">{_tree_html(insight.get('file_tree',{}))}</div></section>

<section id="impact"><div class="head"><div><p class="kicker">04 · CHANGE IMPACT</p><h2>변경 영향</h2></div><p class="note">직접 변경, import, 호출, Git 동시 수정 근거를 분리해 표시합니다.</p></div><div class="panel"><div class="toolbar"><strong>{len(candidates)}개 파일 후보</strong><input class="search" data-filter="impact-body" placeholder="파일 또는 함수 검색"></div><table><thead><tr><th>우선순위</th><th>파일</th><th>근거</th><th>함수 후보</th></tr></thead><tbody id="impact-body">{_empty(candidate_rows,4,'영향 후보가 없습니다.')}</tbody></table></div></section>

<section id="tests"><div class="head"><div><p class="kicker">05 · TESTS</p><h2>테스트 연결</h2></div><p class="note">후보가 없다는 결과는 영향이 없다는 증거가 아니라, 정적으로 연결을 발견하지 못했다는 뜻입니다.</p></div><div class="panel"><table><thead><tr><th>테스트 파일</th><th>함수 후보</th><th>연결 근거</th></tr></thead><tbody>{_empty(test_rows,3,'연결된 테스트 후보를 찾지 못했습니다. fixture·monkeypatch·동적 호출은 별도 검토가 필요합니다.')}</tbody></table></div></section>

<section id="propagation"><div class="head"><div><p class="kicker">06 · PROPAGATION</p><h2>함수 영향 전파</h2></div><p class="note">거리 1은 직접 호출, 2 이상은 다른 호출자를 거친 간접 영향입니다.</p></div><div class="panel"><table><thead><tr><th>거리</th><th>영향 함수</th><th>경유 대상</th><th>신뢰도</th></tr></thead><tbody>{_empty(affected_rows,4,'함수 단위 전파 후보가 없습니다.')}</tbody></table></div></section>

<section id="relations"><div class="head"><div><p class="kicker">07 · RELATIONS</p><h2>파일과 함수 관계</h2></div><p class="note">분석된 전체 내부 import와 호출 관계를 표시하며 각 표에서 바로 검색할 수 있습니다.</p></div><div class="panel"><div class="toolbar"><strong>내부 import 관계 · {len(import_rows)}</strong><input class="search" data-filter="import-body" placeholder="import 관계 검색"></div><table><thead><tr><th>가져오는 파일</th><th></th><th>대상 파일</th><th>줄</th><th>심볼</th></tr></thead><tbody id="import-body">{_empty(import_rows,5,'저장소 내부 import 관계가 없습니다.')}</tbody></table></div><br><div class="panel"><div class="toolbar"><strong>해석된 호출 · {graph['resolved_call_count']}</strong><input class="search" data-filter="call-body" placeholder="호출 관계 검색"></div><table><thead><tr><th>호출자</th><th></th><th>호출 대상</th><th>줄</th><th>신뢰도</th></tr></thead><tbody id="call-body">{_empty(call_rows,5,'해석된 내부 호출이 없습니다.')}</tbody></table></div></section>

<section id="unresolved"><div class="head"><div><p class="kicker">08 · UNRESOLVED</p><h2>미해결 호출</h2></div><p class="note">미해결은 오류가 아니라 현재 정적 규칙으로 저장소 내부 대상에 연결하지 못했다는 의미입니다. 전체 {graph['unresolved_call_count']}건을 표시합니다.</p></div><div class="reason-grid">{reason_cards or '<div class="mini"><strong>0</strong><span>미해결 호출</span></div>'}</div><div class="panel"><div class="toolbar"><strong>미해결 호출 상세</strong><input class="search" data-filter="unresolved-body" placeholder="호출자·표현식·사유 검색"></div><table><thead><tr><th>호출자</th><th>원문 표현식</th><th>줄</th><th>분류</th></tr></thead><tbody id="unresolved-body">{_empty(unresolved_rows,4,'미해결 호출이 없습니다.')}</tbody></table></div></section>

<section id="api"><div class="head"><div><p class="kicker">09 · API SURFACE</p><h2>공개 API</h2></div><p class="note">공개 심볼 {public_count}개 중 {documented}개가 문서화되어 있습니다. 문서화율 {doc_rate}%.</p></div><div class="panel"><div class="toolbar"><strong>공개 심볼 전체 목록</strong><input class="search" data-filter="api-body" placeholder="API·시그니처·docstring 검색"></div><table><thead><tr><th>종류</th><th>위치</th><th>시그니처·상속</th><th>docstring</th></tr></thead><tbody id="api-body">{_empty(api_rows,4,'공개 API가 없습니다.')}</tbody></table></div><br>{f'<div class="panel"><table><thead><tr><th>심각도</th><th>심볼</th><th>변화</th><th>설명</th></tr></thead><tbody>{_empty(change_rows,4,"기준 리비전 대비 API 변화가 없습니다.")}</tbody></table></div>' if changes.get('available') else f'<div class="callout"><strong>API 변화 비교 대기</strong><br>{_e(changes.get("reason","기준 리비전 없음"))}. <code>--base HEAD~1</code>을 지정하면 삭제·시그니처·상속 변화를 비교합니다.</div>'}</section>

<section id="details"><div class="head"><div><p class="kicker">10 · FILE DETAILS</p><h2>파일·코드 상세</h2></div><p class="note">파일을 펼쳐 docstring, 선언 시그니처, 위치와 import 원문을 확인합니다.</p></div><div class="panel"><div class="toolbar"><strong>{len(files)}개 파일</strong><input class="search" data-filter="detail-body" placeholder="파일 검색"></div><div id="detail-body">{''.join(detail_cards)}</div></div></section>

<section id="history"><div class="head"><div><p class="kicker">11 · GIT CONTEXT</p><h2>동시 수정 이력</h2></div><p class="note">함께 수정된 경험적 상관관계이며 코드 의존성을 의미하지 않습니다.</p></div><div class="panel"><table><thead><tr><th>파일 쌍</th><th>함께 수정</th><th>Jaccard</th></tr></thead><tbody>{_empty(cochange_rows,3,'현재 변경 파일과 관련된 동시 수정 기록이 없습니다.')}</tbody></table></div></section>

<section id="diagnostics"><div class="head"><div><p class="kicker">12 · DIAGNOSTICS</p><h2>진단과 한계</h2></div></div><div class="split"><div class="card"><strong>파싱 상태 · {_e(summary['parse_status'])}</strong><ul class="diagnostics">{''.join(diagnostics) or '<li>수집된 구문 오류나 경고가 없습니다.</li>'}</ul></div><div class="card"><strong>해석 범위</strong><ul class="diagnostics"><li>동적 import, fixture 주입, monkeypatch, 콜백과 런타임 디스패치를 놓칠 수 있습니다.</li><li>Git 동시 수정은 의존성이 아닌 상관관계입니다.</li><li><code>unique_name_heuristic</code> 호출은 낮은 신뢰도의 검토 후보입니다.</li><li>런타임 생성 멤버와 export 별칭은 API 목록에서 빠질 수 있습니다.</li><li>테스트 미검출은 테스트 영향이 없다는 뜻이 아닙니다.</li></ul></div></div></section>
</main><footer><div class="wrap"><strong>Impact Lab · Python Repository Analyzer v0.6</strong><p>생성 {generated} · 정적 분석 결과는 검토 후보이며 실행 시 동작을 보장하지 않습니다.</p></div></footer>
<script>document.querySelectorAll('[data-filter]').forEach(input=>input.addEventListener('input',()=>{{const q=input.value.toLowerCase();document.querySelectorAll('#'+input.dataset.filter+' [data-search]').forEach(row=>row.hidden=!row.dataset.search.toLowerCase().includes(q))}}));</script></body></html>'''


def write_html(result: dict[str, Any], destination: Any) -> None:
    destination.write_text(render_html(result), encoding='utf-8')
