from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from analyzer.github_loader import clone_repository, parse_github_url, safe_rmtree
from analyzer.python_analyzer import analyze_repository
from analyzer.reporter import print_console_report, save_report, save_text_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="GitHub Python repository static analyzer demo v0.2 (no AI)"
    )
    parser.add_argument("repository", help="Public GitHub repository URL")
    parser.add_argument("--branch", default=None, help="Branch/tag to clone")
    parser.add_argument("--workspace", default=".analysis_workspace")
    parser.add_argument("--output", default="analysis_output")
    parser.add_argument("--keep-repo", action="store_true")
    parser.add_argument(
        "--detail",
        choices=["summary", "files", "full"],
        default="files",
        help="Console/text report detail level (default: files)",
    )
    parser.add_argument(
        "--max-functions",
        type=int,
        default=30,
        help="Maximum functions/methods printed per file (default: 30)",
    )
    parser.add_argument(
        "--max-calls",
        type=int,
        default=8,
        help="Maximum call expressions printed per function (default: 8)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.max_functions < 1 or args.max_calls < 1:
        print("[ERROR] --max-functions와 --max-calls는 1 이상이어야 합니다.", file=sys.stderr)
        return 2

    try:
        owner, repo = parse_github_url(args.repository)
        clone_path = clone_repository(
            args.repository,
            Path(args.workspace).resolve(),
            args.branch,
        )
        report = analyze_repository(clone_path, args.repository, owner, repo)

        output_dir = Path(args.output).resolve()
        json_path = save_report(report, output_dir)
        text_path = save_text_report(
            report,
            output_dir,
            detail=args.detail,
            max_functions=args.max_functions,
            max_calls=args.max_calls,
        )
        print_console_report(
            report,
            json_path,
            text_path,
            detail=args.detail,
            max_functions=args.max_functions,
            max_calls=args.max_calls,
        )

        if not args.keep_repo:
            if not safe_rmtree(clone_path):
                print(f"[WARN] 임시 clone 폴더를 삭제하지 못했습니다: {clone_path}")
                print("       분석 결과에는 영향이 없습니다. 필요하면 나중에 수동 삭제하세요.")
        return 0
    except KeyboardInterrupt:
        print("\n[ERROR] 분석이 취소되었습니다.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
