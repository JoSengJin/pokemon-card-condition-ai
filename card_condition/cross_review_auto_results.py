"""Usage reports, reversible proposals, and measured-result display."""
import ast
import base64
import hashlib
import html
import io
import json
from pathlib import Path
from .cross_review_auto_child import sum_usage
from .cross_review_auto_contract import UntrustedExecutionError
from .cross_review_auto_sources import model_file
from .experiment_record import read, save, sha
from .review import atomic_write


def token_report(folder, result):
    calls = [read(p) for p in (folder / 'codex').glob('*/call.json')]
    codex = sum_usage([c.get('usage') for c in calls], ('input_tokens', 'cached_input_tokens', 'output_tokens', 'reasoning_output_tokens'))
    codex['total_tokens'] = codex['input_tokens']+codex['output_tokens'] if codex['input_tokens'] is not None and codex['output_tokens'] is not None else None
    gemini = sum_usage([c.get('usage') for c in result.get('attempts', [])],
                       ('prompt_token_count', 'candidates_token_count', 'thoughts_token_count', 'total_token_count'))
    report = dict(codex_calls=len(calls), codex_usage=codex, gemini_calls=len(result.get('attempts', [])), gemini_usage=gemini,
                  before_automation_codex_usage=None, reduction_percent=None,
                  comparison_note='동일 작업의 자동화 이전 Codex 실측 기준 없음. CLI 사용량과 현재 채팅 사용량은 별개이며 절감률 미측정.')
    reuse = folder / 'response_reuse.json'
    if reuse.exists():
        report.update(gemini_calls=0, gemini_response_imports=len(result.get('attempts', [])),
                      response_reuse=read(reuse))
    from .cross_review_nemotron import usage_totals
    extra=[read(p) for p in (folder/'nemotron').glob('*.json') if p.name!='status.json']
    report.update(nemotron_calls=sum(bool(v.get('attempted')) for v in extra),nemotron_usage=usage_totals(extra))
    save(folder / 'token_report.json', report)
    return report


def implement(root, folder, selected, verdict, data):
    raise UntrustedExecutionError('Generated workers require an isolated trusted evaluation path; automatic execution is disabled')


def stage_implementation(root, folder, verdict, data):
    """Save a reviewable proposal only. No project edits and no worker execution."""
    if set(data)!={'edits','worker'} or not isinstance(data['worker'],str):
        raise ValueError('Invalid implementation proposal')
    ast.parse(data['worker'])
    edits=[];proposed={}
    if not isinstance(data['edits'],list):raise ValueError('Invalid edits')
    for edit in data['edits']:
        if set(edit)!={'path','before_sha256','old','new'} or edit['path'] not in verdict['implementation_files']:
            raise ValueError('Unapproved source edit')
        file=model_file(root,edit['path']);check=next(c for c in verdict['code_checks'] if c['path']==edit['path'])
        if sha(file)!=edit['before_sha256'] or sha(file)!=check['sha256']:
            raise ValueError('Source changed after verification')
        current=proposed.get(edit['path'],file.read_text())
        if not edit['old'] or current.count(edit['old'])!=1:
            raise ValueError('Edit anchor must match exactly once')
        proposed[edit['path']]=current.replace(edit['old'],edit['new'],1)
        ast.parse(proposed[edit['path']])
        edits.append(edit)
    path=folder/'implementation-proposal.json'
    save(path,dict(edits=edits,worker=data['worker'],applied=False,executed=False,
        blocker='Trusted isolated execution and independent model evaluation are not configured'))
    return path


def restore_unaccepted(root, folder):
    transaction = read(folder / 'implementation/apply.json')
    for index, item in enumerate(transaction['files']):
        file = model_file(root, item['path'])
        baseline=folder / 'implementation' / (str(index)+'-before.py')
        if sha(baseline)!=item['before_sha256'] or sha(file) not in (item['before_sha256'],item['after_sha256']):
            raise ValueError('User source changed; do not overwrite during rollback')
    for index, item in enumerate(transaction['files']):
        atomic_write(root / item['path'], (folder / 'implementation' / (str(index)+'-before.py')).read_text())


def measured_gain(result, *, verified=False):
    if not verified:return False
    cohorts=[result,*result.get('required_cohorts',[])]
    return (result['acceptance_passed'] and any(c['comparison']['informative_improvement'] for c in cohorts)
        and all(c['comparison']['no_new_errors'] and not (c.get('point_comparison') or {}).get('new_misses') for c in cohorts))


def render_result(root, experiment_folder, verified_reference=None):
    root = root.resolve()
    from PIL import Image, ImageDraw, ImageOps
    result = read(experiment_folder / 'result.json')
    blocks = ['<!doctype html><meta charset="utf-8"><title>자동 실험 결과</title>',
              '<h1>개발용 동일 평가 자료 비교 — 독립 검증 아님</h1>',
              '<p>사전 성공 기준 충족: ' + str(result['acceptance_passed']) + '</p>']
    evaluations = [('주 평가', result)] + [('필수 평가: ' + c['id'], c) for c in result.get('required_cohorts', [])]
    for label, result in evaluations:
        cmp = result['comparison']
        blocks.extend(['<h2>' + html.escape(label) + '</h2>',
                       '<p>해당 평가 기준 충족: ' + str(result.get('primary_acceptance_passed', result['acceptance_passed'])) + '</p>',
                       '<pre>' + html.escape(json.dumps(cmp, ensure_ascii=False, indent=2)) + '</pre>'])
        for metric, denominator in [('fp',cmp['before']['fp']+cmp['before']['tn']),('fn',cmp['before']['fn']+cmp['before']['tp'])]:
            old,new=cmp['before'][metric],cmp['after'][metric]
            delta=(new-old)/denominator*100 if denominator else None
            blocks.append('<p>'+metric.upper()+': '+str(old)+'/'+str(denominator)+' → '+str(new)+'/'+str(denominator)
                          +' / 변화 '+(str(round(delta,2))+'%p' if delta is not None else '미확인')+'</p>')
        if result.get('point_comparison'):
            blocks.append('<h2>실제 사람점 누락 비교</h2><pre>'+html.escape(json.dumps(result['point_comparison'],ensure_ascii=False,indent=2))+'</pre>')
        for row, before, after in zip(result['rows'], result['before_scores'], result['scores']):
            blocks.append('<h2>' + html.escape(row['id']) + '</h2><p>사람 정답: ' + str(row['target'])
                          + ' / 이전: ' + str(before) + ' / 이후: ' + str(after) + '</p>')
            image = (root / row.get('image', '')).resolve()
            if row.get('image') and image.is_file() and (image.is_relative_to(root) or verified_reference is not None and any(row==r for r in verified_reference['rows']+sum([c['rows'] for c in verified_reference.get('required_cohorts',[])],[]))):
                with Image.open(image) as original:
                    picture = ImageOps.exif_transpose(original).convert('RGB')
                # Match data.load_manifest's decoded-size + RGB-pixels identity contract.
                if row.get('image_sha256') not in (sha(image),hashlib.sha256(str(picture.size).encode()+picture.tobytes()).hexdigest()):
                    blocks.append('<p>사진 해시 불일치 — 다른 사진을 평가 결과로 표시하지 않습니다.</p>')
                    continue
                box = row['box']
                if len(box) == 4 and all(0 <= x <= 1 for x in box):
                    ImageDraw.Draw(picture).rectangle((box[0]*picture.width, box[1]*picture.height, box[2]*picture.width, box[3]*picture.height), outline='cyan', width=4)
                    picture.thumbnail((700,700))
                    output = io.BytesIO(); picture.save(output, format='JPEG')
                    blocks.append('<img alt="검증 구역" src="data:image/jpeg;base64,' + base64.b64encode(output.getvalue()).decode() + '">')
            else:
                blocks.append('<p>사진 경로 없음 — 수치만 표시</p>')
    atomic_write(experiment_folder / 'comparison.html', '\n'.join(blocks))
