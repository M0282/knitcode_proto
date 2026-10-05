"""Deterministic protocol demonstration, NOT an AI model."""
import json
import sys
request = json.load(sys.stdin)
edits = []
for path, content in request['sources'].items():
    if path == 'calc.py' and 'return a-b' in content:
        edits.append({'path': path, 'content': content.replace('return a-b','return a+b')})
print(json.dumps({'edits': edits}))
