from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


WIDTH = 78


def save_report(report: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{report['repository']['name']}_analysis.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def save_text_report(
    report: dict[str, Any],
    output_dir: Path,
    detail: str = "files",
    max_functions: int = 30,
    max_calls: int = 8,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{report['repository']['name']}_report.txt"
    text = build_human_report(
        report,
        detail=detail,
        max_functions=max_functions,
        max_calls=max_calls,
    )
    path.write_text(text, encoding="utf-8")
    return path


def _clip(values: Iterable[str], limit: int) -> tuple[list[str], int]:
    data = list(values)
    return data[:limit], max(0, len(data) - limit)


def _fmt_import(item: dict[str, Any]) -> str:
    if item.get("type") == "from":
        name = item.get("name") or "*"
        alias = f" as {item['alias']}" if item.get("alias") else ""
        return f"from {item.get('module', '')} import {name}{alias}"
    alias = f" as {item['alias']}" if item.get("alias") else ""
    return f"import {item.get('module', '')}{alias}"


def _calls_by_function(file_info: dict[str, Any]) -> dict[str | None, list[dict[str, Any]]]:
    grouped: dict[str | None, list[dict[str, Any]]] = defaultdict(list)
    for call in file_info.get("calls", []):
        grouped[call.get("inside_function")].append(call)
    return grouped


def _functions_by_class(file_info: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    module_functions: list[dict[str, Any]] = []
    class_functions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fn in file_info.get("functions", []):
        if fn.get("class_name"):
            class_functions[fn["class_name"]].append(fn)
        else:
            module_functions.append(fn)
    return module_functions, class_functions


def _render_function(
    fn: dict[str, Any],
    calls_by_function: dict[str | None, list[dict[str, Any]]],
    indent: str,
    max_calls: int,
) -> list[str]:
    async_prefix = "async " if fn.get("is_async") else ""
    tags = ", ".join(fn.get("tags", []))
    line = f"{indent}- {async_prefix}{fn['name']}()  [line {fn['line']}]"
    if tags:
        line += f"  <{tags}>"

    lines = [line]
    calls = calls_by_function.get(fn.get("qualified_name"), [])
    call_names, hidden = _clip((c["callee"] for c in calls), max_calls)
    if call_names:
        lines.append(f"{indent}    calls:")
        for callee in call_names:
            lines.append(f"{indent}      -> {callee}()")
        if hidden:
            lines.append(f"{indent}      ... +{hidden} more call expression(s)")
    return lines


def _render_file(
    file_info: dict[str, Any],
    detail: str,
    max_functions: int,
    max_calls: int,
) -> list[str]:
    lines: list[str] = []
    lines.append(f"FILE  {file_info['path']}")
    lines.append(
        f"  category={file_info['category']} | code_lines={file_info['code_lines']} | "
        f"classes={len(file_info.get('classes', []))} | functions={len(file_info.get('functions', []))} | "
        f"calls={len(file_info.get('calls', []))}"
    )

    if file_info.get("parse_status") != "ok":
        err = file_info.get("syntax_error") or {}
        lines.append(f"  !! syntax error: line {err.get('line')}: {err.get('message')}")
        return lines

    imports = sorted({_fmt_import(i) for i in file_info.get("imports", [])})
    if imports:
        shown, hidden = _clip(imports, 12 if detail == "files" else 40)
        lines.append("  imports:")
        lines.extend(f"    - {value}" for value in shown)
        if hidden:
            lines.append(f"    ... +{hidden} more import(s)")

    if detail == "summary":
        return lines

    calls_by_function = _calls_by_function(file_info)
    module_functions, class_functions = _functions_by_class(file_info)

    rendered_count = 0
    classes = file_info.get("classes", [])
    if classes:
        lines.append("  classes:")
        for cls in classes:
            bases = ", ".join(cls.get("bases") or [])
            base_text = f"({bases})" if bases else ""
            lines.append(f"    + {cls['name']}{base_text}  [line {cls['line']}]")
            methods = class_functions.get(cls["name"], [])
            for fn in methods:
                if rendered_count >= max_functions:
                    break
                lines.extend(_render_function(fn, calls_by_function, "      ", max_calls))
                rendered_count += 1
            if rendered_count >= max_functions:
                break

    if rendered_count < max_functions and module_functions:
        lines.append("  module functions:")
        for fn in module_functions:
            if rendered_count >= max_functions:
                break
            lines.extend(_render_function(fn, calls_by_function, "    ", max_calls))
            rendered_count += 1

    total_functions = len(file_info.get("functions", []))
    if total_functions > rendered_count:
        lines.append(f"  ... +{total_functions - rendered_count} more function/method(s)")

    if detail == "full":
        module_calls = calls_by_function.get(None, [])
        if module_calls:
            shown, hidden = _clip((c["callee"] for c in module_calls), max_calls * 2)
            lines.append("  module-level calls:")
            lines.extend(f"    -> {callee}()" for callee in shown)
            if hidden:
                lines.append(f"    ... +{hidden} more module-level call(s)")

    return lines


def build_human_report(
    report: dict[str, Any],
    detail: str = "files",
    max_functions: int = 30,
    max_calls: int = 8,
) -> str:
    summary = report["summary"]
    repo = report["repository"]
    lines: list[str] = []

    lines.append("=" * WIDTH)
    lines.append("PYTHON REPOSITORY STATIC ANALYZER  v0.2")
    lines.append("No AI / No graph construction / Python AST based")
    lines.append("=" * WIDTH)
    lines.append(f"Repository       : {repo['owner']}/{repo['name']}")
    lines.append(f"Source           : {repo['source_url']}")
    lines.append(f"Python files     : {summary['python_file_count']}")
    lines.append(f"Code lines       : {summary['code_line_count']}")
    lines.append(f"Classes          : {summary['class_count']}")
    lines.append(f"Functions        : {summary['function_count']}")
    lines.append(f"Imports          : {summary['import_count']}")
    lines.append(f"Call expressions : {summary['call_expression_count']}")
    lines.append("")

    lines.append("FILE CLASSIFICATION")
    lines.append("-" * WIDTH)
    for category, count in sorted(
        summary["file_categories"].items(), key=lambda item: (-item[1], item[0])
    ):
        lines.append(f"  {category:<18} {count:>5}")
    lines.append("")

    top_imports = summary.get("top_import_roots", [])
    if top_imports:
        lines.append("TOP IMPORT ROOTS")
        lines.append("-" * WIDTH)
        for name, count in top_imports[:15]:
            lines.append(f"  {name:<32} {count:>5}")
        lines.append("")

    lines.append("SOURCE STRUCTURE")
    lines.append("=" * WIDTH)
    for index, file_info in enumerate(report.get("files", []), start=1):
        if index > 1:
            lines.append("-" * WIDTH)
        lines.extend(
            _render_file(
                file_info,
                detail=detail,
                max_functions=max_functions,
                max_calls=max_calls,
            )
        )

    lines.append("")
    lines.append("=" * WIDTH)
    lines.append("STATUS")
    lines.append("  [DONE] GitHub repository ingestion")
    lines.append("  [DONE] Python file discovery")
    lines.append("  [DONE] AST parsing")
    lines.append("  [DONE] File / class / function / import / call extraction")
    lines.append("  [TODO] Symbol resolution")
    lines.append("  [TODO] Function definition <-> call connection")
    lines.append("  [TODO] Call/dependency graph")
    lines.append("  [TODO] Git history / test impact analysis")
    lines.append("=" * WIDTH)
    return "\n".join(lines) + "\n"


def print_console_report(
    report: dict[str, Any],
    json_report_path: Path,
    text_report_path: Path,
    detail: str = "files",
    max_functions: int = 30,
    max_calls: int = 8,
) -> None:
    print("[3/3] 분석 완료")
    print(
        build_human_report(
            report,
            detail=detail,
            max_functions=max_functions,
            max_calls=max_calls,
        ),
        end="",
    )
    print(f"JSON report : {json_report_path}")
    print(f"TEXT report : {text_report_path}")
