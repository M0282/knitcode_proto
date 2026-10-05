from __future__ import annotations
import ast
import io
import tokenize
import warnings
from collections import Counter
from pathlib import Path
from typing import Any
from analyzer.classifier import classify_file, classify_function

EXCLUDED = {'.git','.venv','venv','env','__pycache__','node_modules','dist','build','.tox','.mypy_cache','.pytest_cache','.ruff_cache'}

def dotted(node: ast.AST | None) -> str:
    if node is None: return ''
    if isinstance(node, ast.Name): return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value); return f'{left}.{node.attr}' if left else node.attr
    if isinstance(node, ast.Call): return dotted(node.func)
    if isinstance(node, ast.Subscript): return dotted(node.value)
    return ''

def ann(node: ast.AST | None) -> str | None:
    if node is None: return None
    try: return ast.unparse(node)
    except Exception: return None

def visibility(name: str) -> str:
    if name.startswith('__') and name.endswith('__'): return 'dunder'
    if name.startswith('_'): return 'private'
    return 'public'

def parameter(item: ast.arg, default: ast.AST | None = None, kind: str = 'positional') -> dict[str, Any]:
    return {'name': item.arg, 'annotation': ann(item.annotation), 'default': ann(default), 'kind': kind}

def signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
    args = node.args
    positional = list(args.posonlyargs) + list(args.args)
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    params = []
    pos_only = len(args.posonlyargs)
    for index, (item, default) in enumerate(zip(positional, defaults)):
        params.append(parameter(item, default, 'positional_only' if index < pos_only else 'positional_or_keyword'))
    if args.vararg:
        params.append(parameter(args.vararg, kind='var_positional'))
    for item, default in zip(args.kwonlyargs, args.kw_defaults):
        params.append(parameter(item, default, 'keyword_only'))
    if args.kwarg:
        params.append(parameter(args.kwarg, kind='var_keyword'))
    return {'parameters': params, 'return_annotation': ann(node.returns)}

class Visitor(ast.NodeVisitor):
    def __init__(self):
        self.imports=[]; self.classes=[]; self.functions=[]; self.calls=[]; self.instances=[]
        self.class_stack=[]; self.function_stack=[]
    @property
    def cls(self): return self.class_stack[-1] if self.class_stack else None
    @property
    def fn(self): return self.function_stack[-1] if self.function_stack else None
    def visit_Import(self,node):
        for a in node.names: self.imports.append({'type':'import','module':a.name,'alias':a.asname,'line':node.lineno})
    def visit_ImportFrom(self,node):
        module='.'*node.level+(node.module or '')
        for a in node.names: self.imports.append({'type':'from','module':module,'name':a.name,'alias':a.asname,'line':node.lineno})
    def visit_ClassDef(self,node):
        self.classes.append({'name':node.name,'line':node.lineno,'end_line':getattr(node,'end_lineno',None),'bases':[dotted(b) or ann(b) for b in node.bases if dotted(b) or ann(b)],'decorators':[dotted(d.func) if isinstance(d,ast.Call) else dotted(d) for d in node.decorator_list], 'visibility': visibility(node.name), 'docstring': ast.get_docstring(node)})
        self.class_stack.append(node.name); self.generic_visit(node); self.class_stack.pop()
    def _function(self,node,is_async):
        decorators=[dotted(d.func) if isinstance(d,ast.Call) else dotted(d) for d in node.decorator_list]
        if self.fn:
            q=f'{self.fn}.<locals>.{node.name}'
        elif self.cls:
            q=f'{self.cls}.{node.name}'
        else:
            q=node.name
        sig=signature(node)
        item={'name':node.name,'qualified_name':q,'line':node.lineno,'end_line':getattr(node,'end_lineno',None),'is_async':is_async,'is_method':self.cls is not None,'class_name':self.cls,'decorators':decorators,'return_annotation':sig['return_annotation'],'parameters':sig['parameters'],'visibility':visibility(node.name),'docstring':ast.get_docstring(node),'tags':classify_function(node.name,decorators,self.cls is not None,is_async)}
        self.functions.append(item); self.function_stack.append(q); self.generic_visit(node); self.function_stack.pop()
    def visit_FunctionDef(self,node): self._function(node,False)
    def visit_AsyncFunctionDef(self,node): self._function(node,True)
    def visit_Call(self,node):
        callee=dotted(node.func)
        if callee: self.calls.append({'callee':callee,'line':node.lineno,'inside_function':self.fn,'inside_class':self.cls})
        self.generic_visit(node)
    def visit_Assign(self,node):
        if isinstance(node.value, ast.Call):
            constructor=dotted(node.value.func)
            for target in node.targets:
                if isinstance(target,ast.Name) and constructor:
                    self.instances.append({'name':target.id,'constructor':constructor,'line':node.lineno,'inside_function':self.fn,'inside_class':self.cls})
        self.generic_visit(node)
    def visit_AnnAssign(self,node):
        if isinstance(node.target,ast.Name) and isinstance(node.value,ast.Call):
            constructor=dotted(node.value.func)
            if constructor:
                self.instances.append({'name':node.target.id,'constructor':constructor,'line':node.lineno,'inside_function':self.fn,'inside_class':self.cls})
        self.generic_visit(node)

def _is_main_guard(node: ast.AST) -> bool:
    if not isinstance(node, ast.Compare) or len(node.ops) != 1 or not isinstance(node.ops[0], ast.Eq):
        return False
    values = [node.left, *node.comparators]
    has_name = any(isinstance(x, ast.Name) and x.id == '__name__' for x in values)
    has_main = any(isinstance(x, ast.Constant) and x.value == '__main__' for x in values)
    return has_name and has_main

def entrypoint_data(tree: ast.Module) -> dict[str, Any]:
    guards = []
    for node in tree.body:
        if isinstance(node, ast.If) and _is_main_guard(node.test):
            calls = []
            for child in node.body:
                for nested in ast.walk(child):
                    if isinstance(nested, ast.Call):
                        callee = dotted(nested.func)
                        if callee:
                            calls.append({'callee': callee, 'line': nested.lineno})
            guards.append({'line': node.lineno, 'calls': calls})
    return {'has_main_guard': bool(guards), 'main_guards': guards}

def discover(repo: Path) -> list[Path]:
    return sorted(p for p in repo.rglob('*.py') if p.is_file() and not any(x in EXCLUDED for x in p.relative_to(repo).parts))

def analyze_file(path: Path, repo: Path) -> dict[str,Any]:
    rel=path.relative_to(repo); category, reason=classify_file(rel)
    before = path.stat()
    raw = path.read_bytes()
    read_diagnostics=[]
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
        text = raw.decode(encoding)
    except (SyntaxError, UnicodeDecodeError, LookupError) as exc:
        encoding = 'utf-8-replace'
        text = raw.decode('utf-8', errors='replace')
        read_diagnostics.append({'kind':'encoding_fallback','message':str(exc)})
    lines=text.splitlines()
    after = path.stat()
    changed_during_analysis = (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size)
    if changed_during_analysis:
        read_diagnostics.append({'kind':'file_changed','message':'분석 중 파일의 크기 또는 수정 시간이 변경되었습니다.'})
    out={'path':rel.as_posix(),'category':category,'category_reason':reason,'total_lines':len(lines),'code_lines':sum(1 for l in lines if l.strip() and not l.lstrip().startswith('#')),'encoding':encoding,'replacement_character_count':text.count('\ufffd'),'changed_during_analysis':changed_during_analysis,'read_diagnostics':read_diagnostics,'parse_status':'ok','syntax_error':None,'syntax_warnings':[],'module_docstring':None,'has_main_guard':False,'main_guards':[],'imports':[],'classes':[],'functions':[],'calls':[],'instances':[]}
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always', SyntaxWarning)
            tree=ast.parse(text,filename=str(rel))
        out['syntax_warnings']=[{'message':str(w.message),'line':w.lineno} for w in caught if issubclass(w.category,SyntaxWarning)]
    except SyntaxError as e:
        out['parse_status']='syntax_error'; out['syntax_error']={'message':e.msg,'line':e.lineno,'offset':e.offset}; return out
    out['module_docstring']=ast.get_docstring(tree)
    out.update(entrypoint_data(tree))
    v=Visitor(); v.visit(tree); out.update(imports=v.imports,classes=v.classes,functions=v.functions,calls=v.calls,instances=v.instances); return out

def analyze_repository(repo_path: Path, source_url: str, owner: str, repo_name: str) -> dict[str,Any]:
    print('[2/3] Python source scan + AST analysis')
    files=[analyze_file(p,repo_path) for p in discover(repo_path)]
    categories=Counter(f['category'] for f in files); parses=Counter(f['parse_status'] for f in files); imports=Counter(); calls=Counter()
    for f in files:
        for i in f['imports']:
            if i.get('module'): imports[i['module'].lstrip('.').split('.')[0]] += 1
        for c in f['calls']: calls[c['callee']] += 1
    public_symbols=sum(sum(1 for x in f['classes'] + f['functions'] if x['visibility']=='public') for f in files)
    documented_symbols=sum(sum(1 for x in f['classes'] + f['functions'] if x.get('docstring')) for f in files)
    return {'schema_version':'0.6','analyzer':{'name':'Python Repository Analyzer Demo v0.6','ai_used':False,'parser':'Python ast','scope':'Python files only','api_model':'Griffe-inspired static symbol model'},'repository':{'source_url':source_url,'owner':owner,'name':repo_name},'summary':{'python_file_count':len(files),'code_line_count':sum(f['code_lines'] for f in files),'class_count':sum(len(f['classes']) for f in files),'function_count':sum(len(f['functions']) for f in files),'public_symbol_count':public_symbols,'documented_symbol_count':documented_symbols,'import_count':sum(len(f['imports']) for f in files),'call_expression_count':sum(len(f['calls']) for f in files),'syntax_warning_count':sum(len(f['syntax_warnings']) for f in files),'read_diagnostic_count':sum(len(f['read_diagnostics']) for f in files),'files_changed_during_analysis':sum(1 for f in files if f['changed_during_analysis']),'file_categories':dict(categories),'parse_status':dict(parses),'encodings':dict(Counter(f['encoding'] for f in files)),'top_import_roots':imports.most_common(20),'top_called_symbols':calls.most_common(20)},'files':files}
