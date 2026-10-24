"""Read-only NVIDIA operational measurements; not self-rated accuracy or a paid benchmark."""
from datetime import datetime,timezone
import json
from .experiment_record import read,sha


def metrics(root):
    entries=[];annotations=root/'artifacts/nvidia-quality/annotations.json'
    notes=read(annotations) if annotations.exists() else {}
    for file in (root/'artifacts/nemotron-cache').glob('*/call.json'):
        if file.is_symlink():continue
        value=read(file)
        if value.get('attempted') is not True:continue
        body=value.get('response') or {}
        if not body:
            try:body=json.loads(value.get('raw_response','{}'))
            except (ValueError,TypeError):body={}
        if not isinstance(body,dict):body={}
        note=notes.get(file.parent.name)
        if note and note.get('source_sha256')!=sha(file):note=None
        entries.append(dict(id=file.parent.name,model=value.get('model'),role=value.get('role','skeptic'),
            status=value.get('status'),started_at=value.get('started_at'),elapsed_seconds=value.get('elapsed_seconds'),
            usage=value.get('usage'),validation_errors=value.get('validation_errors',[]),error_kind=value.get('error_kind'),
            rationale=body.get('rationale'),raw_response=value.get('raw_response'),audit=note,source=str(file)))
    entries.sort(key=lambda x:x.get('started_at') or '',reverse=True)
    from .cross_review_nemotron import usage_totals
    setting=read(root/'nemotron-review.json') if (root/'nemotron-review.json').exists() else {}
    circuit=read(root/'artifacts/provider-alerts/nemotron-disabled.json') if (root/'artifacts/provider-alerts/nemotron-disabled.json').exists() else {}
    proof=setting.get('free_verification') or {}
    current=False
    try:current=datetime.fromisoformat(proof['verified_at'])<=datetime.now(timezone.utc)<datetime.fromisoformat(proof['expires_at'])
    except (KeyError,TypeError,ValueError):pass
    cost=dict(nvidia=dict(model=setting.get('model'),last_free_verified=proof.get('verified_at'),expires_at=proof.get('expires_at'),
        verification_current=current,billing_disabled_verified=proof.get('billing_disabled') is True,
        blocked=circuit.get('disabled',False),block_reason=circuit.get('reason'),live_validation_pending=circuit.get('live_validation_pending',False),automatic_paid_fallback=False),
        gemini=dict(blocked=True,reason='free_confirmation_missing'),codex=dict(scope='unchanged',note='기존 Codex 이용 방식 유지. 이번 무료 API 차단 대상 아님.'))
    gemini=root/'artifacts/cross-review-20261019/local-config.json'
    if gemini.exists():
        from .cross_review import free_project_reason
        reason=free_project_reason(read(gemini));cost['gemini']=dict(blocked=reason is not None,reason=reason)
    durations=[v['elapsed_seconds'] for v in entries if isinstance(v.get('elapsed_seconds'),(int,float))]
    from .review_chat import redact
    return redact(dict(model=setting.get('model'),calls=len(entries),schema_passed=sum(v['status']=='complete' for v in entries),
        roles={r:sum(v['role']==r for v in entries) for r in ('skeptic','judge')},usage=usage_totals([dict(v,attempted=True) for v in entries]),
        latency=dict(samples=len(durations),mean_seconds=sum(durations)/len(durations) if durations else None),
        accuracy=None,controlled_benchmark_samples=0,model_improvement=None,entries=entries,cost=cost,
        benchmark_cases=['참인 주장','거짓 주장','근거 부족','상충하는 근거','양측의 오답 합의'],read_only=True,
        note='실제 저장된 요청 journal만 집계합니다. 캐시 재사용은 추가 요청으로 세지 않습니다. 서로 다른 역할·프롬프트의 소표본이며 모델 정확도나 카드 분석 성능을 뜻하지 않습니다.'))
