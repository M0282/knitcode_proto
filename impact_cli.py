import argparse
import atexit
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from analyzer.python_analyzer import analyze_repository
from analyzer.impact import history, predict, git
from analyzer.api_surface import build_api_surface, compare_api
from analyzer.html_report import write_html
from analyzer.markdown_report import render_markdown
from analyzer.project_insight import build_project_insight
from analyzer.repository_source import github_clone_url, github_identity, local_repository


def analyze_revision(repo, revision, owner='git', repo_name=None):
    """Materialize only Python files from a Git tree into a temporary safe directory."""
    names = [x for x in git(repo, 'ls-tree', '-r', '--name-only', '-z', revision).split('\0') if x.endswith('.py')]
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for name in names:
            relative = Path(name)
            if relative.is_absolute() or '..' in relative.parts:
                continue
            content = subprocess.run(
                ['git', '-C', str(repo), 'show', f'{revision}:{name}'],
                capture_output=True, check=True,
            ).stdout
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        return analyze_repository(root, f'{repo}@{revision}', owner, repo_name or repo.name)

p = argparse.ArgumentParser(description='v0.6: detailed Python structure, Git, calls, tests, API and HTML report')
p.add_argument('repository', nargs='?', help='Local repository path, or a GitHub repository/issue/PR URL')
p.add_argument('--repo-url', help='GitHub repository, issue or pull-request URL; cloned automatically')
p.add_argument('--changed', nargs='*', default=[])
p.add_argument('--base', help='Git revision to compare against HEAD')
p.add_argument('--changed-symbol', action='append', default=[], metavar='FILE::FUNCTION',
               help='Limit function impact seeds, e.g. service.py::save (repeatable)')
p.add_argument('--commits', type=int, default=500)
p.add_argument('--output', default='impact_output')
a = p.parse_args()
if bool(a.repository) == bool(a.repo_url):
    p.error('provide exactly one repository path/URL or --repo-url URL')
source = a.repo_url or a.repository
try:
    clone_url = github_clone_url(source)
except ValueError as exc:
    p.error(str(exc))
temporary = None
if clone_url:
    temporary = tempfile.TemporaryDirectory(prefix='impact_repo_')
    atexit.register(temporary.cleanup)
    repo = Path(temporary.name) / 'repository'
    print(f'[1/3] GitHub clone: {clone_url}')
    try:
        subprocess.run(['git', 'clone', '--quiet', clone_url, str(repo)], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        p.error('GitHub clone failed; check the URL, network connection and Git installation')
else:
    repo = local_repository(source)
if not repo.is_dir() or a.commits < 1:
    p.error('repository must exist; commits >=1')
changed = a.changed
if a.base:
    changed += [x for x in git(repo, 'diff', '--name-only', '-z', a.base, 'HEAD').split('\0') if x]
changed = [Path(x).as_posix() for x in changed]
if clone_url:
    repo_owner, repo_name = github_identity(clone_url)
else:
    repo_owner, repo_name = 'local', repo.name
report = analyze_repository(repo, clone_url or str(repo), repo_owner, repo_name)
hist = history(repo, a.commits)
impact = predict(report, changed, hist, changed_symbols=a.changed_symbol)
api_surface = build_api_surface(report)
base_report = None
if a.base:
    try:
        base_report = analyze_revision(repo, a.base, repo_owner, repo_name)
    except (subprocess.CalledProcessError, FileNotFoundError):
        base_report = None
api_changes = compare_api(base_report, report)
if a.base and base_report is None:
    api_changes['reason'] = f'Git 기준 리비전을 분석할 수 없습니다: {a.base}'
project_insight = build_project_insight(report, impact['call_graph'])
result = {'schema_version': '0.6', 'structure': report, 'history': hist, 'impact': impact,
          'api_surface': api_surface, 'api_changes': api_changes, 'project_insight': project_insight}
out = Path(a.output).resolve()
out.mkdir(parents=True, exist_ok=True)
analysis_text = json.dumps(result, ensure_ascii=False, indent=2)
(out / 'analysis.json').write_text(analysis_text, encoding='utf-8')
(out / 'impact.json').write_text(analysis_text, encoding='utf-8')
(out / 'call_graph.json').write_text(json.dumps(impact['call_graph'], ensure_ascii=False, indent=2), encoding='utf-8')
(out / 'api_surface.json').write_text(json.dumps({'surface': api_surface, 'changes': api_changes}, ensure_ascii=False, indent=2), encoding='utf-8')
markdown = render_markdown(result)
(out / 'report.md').write_text(markdown, encoding='utf-8')
(out / 'impact.md').write_text(markdown, encoding='utf-8')
write_html(result, out / 'report.html')
artifacts = []
for name in ['analysis.json','impact.json','call_graph.json','api_surface.json','report.md','impact.md','report.html']:
    path = out / name
    data = path.read_bytes()
    artifacts.append({'path': name, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
manifest = {'schema_version':'0.6','snapshot_sha256':hashlib.sha256(analysis_text.encode('utf-8')).hexdigest(),'artifacts':artifacts}
(out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(markdown)
print(f'\nHTML report: {out / "report.html"}')
