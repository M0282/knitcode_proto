import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from analyzer.impact import history, predict
from analyzer.call_graph import build_call_graph
from analyzer.python_analyzer import analyze_repository
from analyzer.api_surface import build_api_surface, compare_api
from analyzer.html_report import render_html
from analyzer.repository_source import github_clone_url
from analyzer.project_insight import build_project_insight
from agent import apply_edits

class ExtensionTests(unittest.TestCase):
    def test_nested_github_url_becomes_clone_url(self):
        self.assertEqual(
            github_clone_url('https://github.com/aboul3la/Sublist3r/issues'),
            'https://github.com/aboul3la/Sublist3r.git',
        )
        self.assertEqual(
            github_clone_url('https://github.com/aboul3la/Sublist3r/pull/123'),
            'https://github.com/aboul3la/Sublist3r.git',
        )
        self.assertIsNone(github_clone_url('C:/work/repository'))

    def test_html_report_is_self_contained_and_escapes_repository_data(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'core.py').write_text('def value(): return 1\n')
            report = analyze_repository(root,'','','<script>alert(1)</script>')
            impact = predict(report, ['core.py'], {'available': False, 'pairs': []})
            surface = build_api_surface(report)
            result = {'structure': report, 'impact': impact, 'history': {'available': False, 'pairs': []},
                      'api_surface': surface, 'api_changes': compare_api(None, report),
                      'project_insight': build_project_insight(report, impact['call_graph'])}
            page = render_html(result)
            self.assertIn('구조부터 영향까지', page)
            self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', page)
            self.assertNotIn('<script>alert(1)</script>', page)
            self.assertNotIn('https://', page)

    def test_entrypoint_and_unresolved_reasons(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'main.py').write_text('import json\ndef run():\n    print(json.dumps({}))\nif __name__ == "__main__":\n    run()\n')
            report = analyze_repository(root,'','','demo')
            graph = build_call_graph(report)
            insight = build_project_insight(report, graph)
            self.assertEqual(insight['entrypoints'][0]['file'], 'main.py')
            self.assertEqual(insight['entrypoints'][0]['calls'][0]['callee'], 'run')
            self.assertGreaterEqual(graph['unresolved_reason_counts']['builtin'], 1)
            self.assertGreaterEqual(graph['unresolved_reason_counts']['external_import'], 1)
            self.assertEqual(len(graph['unresolved_calls']), graph['unresolved_call_count'])

    def test_nested_function_and_declared_source_encoding(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = '# -*- coding: cp949 -*-\ndef outer():\n    def inner():\n        return "한글"\n    return inner()\n'
            (root/'legacy.py').write_bytes(source.encode('cp949'))
            report = analyze_repository(root,'','','demo')
            file = report['files'][0]
            names = {item['qualified_name'] for item in file['functions']}
            self.assertIn('outer.<locals>.inner', names)
            self.assertEqual(file['encoding'], 'cp949')
            self.assertEqual(file['read_diagnostics'], [])

    def test_api_surface_and_breaking_signature_change(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = 'def public(value: int = 1) -> int:\n    """Return a value."""\n    return value\n\ndef _private():\n    pass\n'
            (root/'api.py').write_text(source)
            before = analyze_repository(root,'','','')
            surface = build_api_surface(before)
            public = next(item for item in surface['public_symbols'] if item['name'] == 'public')
            self.assertEqual(public['parameters'][0]['annotation'], 'int')
            self.assertEqual(surface['counts']['documented_public'], 1)
            self.assertEqual(public['docstring'], 'Return a value.')
            (root/'api.py').write_text('def public(value, required):\n    return value\n')
            after = analyze_repository(root,'','','')
            changes = compare_api(before, after)
            self.assertEqual(changes['breaking'][0]['kind'], 'signature_changed')

    def test_history_and_transitive_tests(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'tests').mkdir()
            (root/'core.py').write_text('def value(): return 1\n')
            (root/'service.py').write_text('from core import value\n')
            (root/'tests/test_service.py').write_text('import service\n')
            def git(*args):
                subprocess.run(['git','-C',d,*args], check=True, capture_output=True)
            git('init'); git('config','user.name','Fixture'); git('config','user.email','fixture@example.invalid')
            git('add','.'); git('commit','-m','initial')
            (root/'core.py').write_text('def value(): return 2\n')
            (root/'service.py').write_text('from core import value\n# change\n')
            git('add','.'); git('commit','-m','cochange')
            h = history(root)
            pair = next(p for p in h['pairs'] if p['files']==['core.py','service.py'])
            self.assertEqual(pair['count'], 2)
            result = predict(analyze_repository(root,'','', ''), ['core.py'], h)
            self.assertIn('tests/test_service.py',result['test_candidates'])
            self.assertTrue(any(e['kind']=='imports_affected_file' for i in result['candidates'] if i['path']=='service.py' for e in i['evidence']))
    def test_function_call_impact_reaches_test(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'tests').mkdir()
            (root/'core.py').write_text('def value(): return 1\n')
            (root/'service.py').write_text('from core import value\ndef load(): return value()\n')
            (root/'tests/test_service.py').write_text('from service import load\ndef test_load(): assert load() == 1\n')
            report = analyze_repository(root,'','','')
            result = predict(report, ['core.py'], {'pairs': []})
            affected = {item['id'] for item in result['function_impact']['affected']}
            self.assertIn('service.py::load', affected)
            self.assertIn('tests/test_service.py::test_load', affected)
            test_item = next(item for item in result['candidates'] if item['path'] == 'tests/test_service.py')
            self.assertIn('test_load', test_item['function_candidates'])
    def test_instance_method_resolution_and_warning_capture(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'models.py').write_text("class Calc:\n    def add(self): return 1\npattern='\\.'\n")
            (root/'service.py').write_text('from models import Calc\ndef run():\n    calc = Calc()\n    return calc.add()\n')
            report = analyze_repository(root,'','','')
            graph = build_call_graph(report)
            pairs = {(edge['source'], edge['target']) for edge in graph['edges']}
            self.assertIn(('service.py::run', 'models.py::Calc.add'), pairs)
            self.assertEqual(report['summary']['syntax_warning_count'], 1)
    def test_escape_rejected_before_any_edit(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with self.assertRaises(ValueError):
                apply_edits(root,[{'path':'ok.py','content':'x'}, {'path':'../escape.py','content':'x'}])
            self.assertFalse((root/'ok.py').exists())
    def test_repair_feedback_loop(self):
        project=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); repo=root/'repo'; repo.mkdir()
            (repo/'calc.py').write_text('def add(a,b): return a-b\n')
            adapter=root/'adapter.py'
            adapter.write_text('import sys,json\nr=json.load(sys.stdin)\nassert r["attempt"]==1 or r["previous_checks"][0]["returncode"]!=0\ncontent="def add(a,b): return a-b\\n" if r["attempt"]==1 else "def add(a,b): return a+b\\n"\nprint(json.dumps({"edits":[{"path":"calc.py","content":content}]}))\n')
            work=root/'work'
            cmd=[sys.executable,str(project/'agent.py'),'--repo',str(repo),'--work',str(work),'--task','fix add','--adapter',json.dumps([sys.executable,str(adapter)]),'--checks',json.dumps([[sys.executable,'-c','from calc import add; assert add(2,3)==5']])]
            result=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            log=json.loads((work/'agent_log.json').read_text())
            self.assertEqual(len(log['attempts']),2)
            self.assertIn('a-b',(repo/'calc.py').read_text())

if __name__=='__main__': unittest.main()
