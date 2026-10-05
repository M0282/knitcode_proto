from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlparse


def parse_github_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        raise ValueError("현재 데모는 github.com 공개 저장소 URL만 지원합니다.")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise ValueError("예: https://github.com/owner/repo")
    owner, repo = parts[0], parts[1].removesuffix(".git")
    valid = re.compile(r"^[A-Za-z0-9_.-]+$")
    if not valid.match(owner) or not valid.match(repo):
        raise ValueError("잘못된 owner/repository 이름입니다.")
    return owner, repo


def _remove_readonly(func, path, _exc_info) -> None:
    """Windows에서 read-only Git object 삭제가 막힐 때 쓰는 callback."""
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        func(path)
    except OSError:
        pass


def safe_rmtree(path: Path) -> bool:
    """가능한 범위에서 디렉터리를 안전하게 삭제한다.

    삭제 실패는 False로 반환한다. 분석 결과 생성 자체를 실패시키지 않도록
    호출부에서 경고만 출력할 수 있게 한다.
    """
    if not path.exists():
        return True
    try:
        shutil.rmtree(path, onerror=_remove_readonly)
        return not path.exists()
    except OSError:
        return False


def clone_repository(repo_url: str, workspace: Path, branch: str | None = None) -> Path:
    if shutil.which("git") is None:
        raise RuntimeError("Git이 설치되어 있지 않습니다.")

    owner, repo = parse_github_url(repo_url)
    workspace.mkdir(parents=True, exist_ok=True)

    # v0.2.1: 고정 폴더를 재사용하지 않는다.
    # 이전 clone의 .git pack 파일이 Windows에서 잠겨 있어도 새 실행을 방해하지 않게 한다.
    run_id = uuid.uuid4().hex[:8]
    dst = workspace / f"{owner}__{repo}__{run_id}"

    cmd = ["git", "clone", "--depth", "1"]
    if branch:
        cmd += ["--branch", branch]
    cmd += [repo_url, str(dst)]

    print(f"[1/3] GitHub clone: {owner}/{repo}")
    print(f"      workspace: {dst.name}")

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:
        safe_rmtree(dst)
        raise RuntimeError("git clone 실패\n" + result.stdout)

    return dst
