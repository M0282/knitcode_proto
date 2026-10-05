import argparse
import json
from pathlib import Path
import subprocess
import sys

p = argparse.ArgumentParser()
p.add_argument('--repo', required=True)
p.add_argument('--work', required=True)
p.add_argument('--task', required=True)
p.add_argument('--adapter', required=True)
p.add_argument('--pytest', action='store_true')
p.add_argument('--attempts', type=int, default=3)
a = p.parse_args()
checks = [[sys.executable, '-m', 'compileall', '-q', '.'],
          [sys.executable, '-m', 'pytest', '-q'] if a.pytest else [sys.executable, '-m', 'unittest', 'discover']]
sys.exit(subprocess.call([sys.executable, str(Path(__file__).with_name('agent.py')),
    '--repo', a.repo, '--work', a.work, '--task', a.task,
    '--adapter', json.dumps([sys.executable, str(Path(a.adapter).resolve())]),
    '--checks', json.dumps(checks), '--attempts', str(a.attempts)]))
