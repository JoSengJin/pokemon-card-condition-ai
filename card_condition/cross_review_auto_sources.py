"""Frozen code excerpts and read-only source checks for review."""
import ast
import os
import re
from pathlib import Path
from .cross_review_auto_contract import PROTECTED
from .experiment_record import read, sha


def model_file(root, name):
    root = root.resolve()
    path = (root / name).resolve()
    if (not path.is_relative_to(root / 'card_condition') or path.suffix != '.py'
            or path.name.startswith('cross_review') or path.name in PROTECTED or not path.is_file()):
        raise ValueError('Only existing model Python files are editable')
    return path


def verify_sources(root, packet):
    from .experiment_record import project_file
    from .cross_review_evidence_manifest import expand_manifest
    root=root.resolve()
    for source in expand_manifest(packet):
        if sha(project_file(root,source['path']))!=source['sha256']:
            raise ValueError('Review evidence changed; a new input is required')


def diagnostic_text(value):
    """Bounded diagnostics with credential values removed before any persistence."""
    text = str(value)
    for name, secret in os.environ.items():
        if re.search(r'KEY|TOKEN|SECRET|PASSWORD', name, re.I) and len(secret) >= 6:
            text = text.replace(secret, '[REDACTED]')
    text = re.sub(r'(?i)(bearer\s+)[^\s"\']+', r'\1[REDACTED]', text)
    text = re.sub(r'(?i)(["\']?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|client[_-]?secret)["\']?\s*[:=]\s*)["\']?[^\s,"\'}]+', r'\1[REDACTED]', text)
    text = re.sub(r'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{24,}(?:\.[A-Za-z0-9_-]+)*',
                  lambda m:m.group() if m.group() in ('skip_host_skill_discovery','suppress_unstable_features_warning') else '[REDACTED]', text)
    return text[-8192:]


def source_context(root, packet, allowed=None):
    """Only plan-linked workers and their imported functions; never cut a function mid-body."""
    from .experiment_record import project_file
    root = root.resolve()
    plan = read(project_file(root, str(Path(packet['latest_result']).parent / 'plan.json')))
    names = list(allowed or []) + packet.get('implementation_sources' if allowed is not None else 'verification_sources', [])
    names += [x['path'] for x in plan.get('code_changes', [])]
    if allowed is None:
        names += list(plan.get('tracked_sha256', {}))
        names += [v['path'] for v in packet['evidence'].values() if isinstance(v,dict) and str(v.get('path','')).endswith('.py')]
    trusted=root/'trusted-experiment.json'
    if trusted.exists():
        setting=read(trusted)
        names=list(allowed or [])+setting['editable_sources']+setting.get('trainer_sources',[])
    catalog = [project_file(root,n) for n in dict.fromkeys(names + list(plan.get('input_sha256', {})))
               if str(n).endswith('.py')]
    pending, trees, requested = list(dict.fromkeys(names)), {}, {}
    while pending and len(trees) < 4:
        file = project_file(root, pending.pop(0))
        if file in trees or file.suffix != '.py' or not any(file.is_relative_to(root/d) for d in ('card_condition','artifacts')):
            continue
        text = file.read_text(); tree = ast.parse(text)
        trees[file] = (text, tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            if node.module.startswith('card_condition.'):
                candidates = [root/(node.module.replace('.', '/')+'.py')]
            else:
                candidates = [p for p in catalog if p.stem == node.module and p.is_relative_to(root/'artifacts')]
            if len(candidates) != 1 or not candidates[0].is_file():
                continue
            imported = candidates[0]
            requested.setdefault(imported,set()).update(a.name for a in node.names)
            if imported not in trees:
                pending.append(str(imported.relative_to(root)))
    sources = []
    for file,(text,tree) in trees.items():
        wanted = requested.get(file)
        selected = list(tree.body)
        omitted = []
        if wanted and '*' not in wanted:
            definitions = {n.name:n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))}
            keep = set(wanted)
            while True:
                dependencies = {n.id for name in keep & definitions.keys() for n in ast.walk(definitions[name]) if isinstance(n,ast.Name)}
                expanded = keep | (dependencies & definitions.keys())
                if expanded == keep: break
                keep = expanded
            omitted = [name for name in definitions if name not in keep]
            selected = [n for n in tree.body if not isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) or n.name in keep]
        lines=text.splitlines(True)
        excerpt=('\n'.join(''.join(lines[n.lineno-1:n.end_lineno]) for n in selected) if wanted else text)
        complete=len(excerpt.encode())<=10000
        if not complete:
            excerpt=''  # Oversized source is explicit missing evidence, never a misleading prefix.
        try:
            model_file(root,str(file.relative_to(root)));editable=allowed is None or str(file.relative_to(root)) in allowed
        except ValueError:
            editable=False
        sources.append(dict(path=str(file.relative_to(root)),sha256=sha(file),excerpt=excerpt,
                            truncated=not complete,omitted_definitions=omitted,editable=editable))
    return dict(sources=sources,omitted_sources=list(dict.fromkeys(pending)))


def provided_code_sources(context):
    sources=list(context['source_context']['sources'])
    contract=context.get('baseline_training_contract',{})
    if all(contract.get(k) for k in ('source','source_sha256','quote')):
        match=next((v for v in sources if v['path']==contract['source']),None)
        if match is None:sources.append(dict(path=contract['source'],sha256=contract['source_sha256'],excerpt=contract['quote']))
        else:
            if match['sha256']!=contract['source_sha256']:raise ValueError('Conflicting provided source SHA')
            sources=[dict(v,excerpt=v['excerpt']+'\n'+contract['quote']) if v is match else v for v in sources]
    return sources


def review_rules(path):
    if not path.exists():return ''
    # Exact child-relevant rules; parent-only reporting/coordination is not model input.
    prefixes=('- 독립 카드','- 완료한 라벨','- 학습과 검증','- 실험 전에',
              '- 공통 기록은','- 읽기 전용 Codex','- 실험 하나를','- 토큰 절약형')
    return '\n'.join(line for line in path.read_text().splitlines() if line.startswith(prefixes))
