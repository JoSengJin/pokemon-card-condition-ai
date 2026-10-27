# 약한 양성 반응 집계 후보 — 2026-10-27 실행

개발 진척률 **30/100 (usable-card-analysis-v1.0, +0%p)**. 약한 양성 집계 하나를 바꾼 실제4-fold 실험은 **세 번째 fold의 수렴 검사 실패**로 종료했다. 앞선2개 fold는 완료됐지만 전체 평가가 끝나지 않아 후보 성능은 미측정이다.

## 실제 record와 판정

- record: `artifacts/experiments/20261027T144107-8f7674cd/record.json`
- status=failed, stage=execute, return_code=1, error_kind=child_exit.
- failure-diagnostics.json: fold=front-joint-3, completed_folds=2. max_gradient=2.461965647833353e-5, 허용1e-5; objective=0.2782141331330776.
- 실제 gradient 보호를 통과하지 못했다. 왜 optimizer가 이 값에서 끝났는지는 추적 상태가 없어 확정하지 않는다. 반복수·온도·허용 gradient를 바꾸거나 다시 실행하지 않았다.
- observations.json/result.json/전체 후보 score가 없다. 후보 FN/FP/실제점 누락률/after 변화와 acceptance를 산출하지 않았다. 앞선2fold만 뽑아 성능으로 발표하지 않는다.

## 가설과 변경 파일

062258의RGB153 gradient 진단에서 놓친 실제점20개 중15개가 presence항의 국소 하강 방향과 겹쳤다. 가중치절반 변경062428은FN12→16/94·새누락4로 미채택이었다. 이번에는 가중치를 유지하고 정확점 없는 양성의 max를 고정T.1 log-mean-exp로 바꾸는 다른 가설을 검증했다. 국소 기울기는 인과 근거가 아니며 smooth pooling도 비볼록성 제거를 보장하지 않는다.

- `tools/experiments/surface-smooth-presence-20261027/objective.py`: weak-positive 집계만 변경. 정상/정확점 loss와 gradient는 기존 함수 그대로 반환한다. 기존 fitter 초기화·중심화·mass·L2·LBFGS100·수렴조건은 보존하고 실패 gradient/objective 메시지만 추가했다.
- 같은 폴더 `worker.py`: 고정 입력·4-fold·기준선 재생, 결과/실패 증거와 사진 보고 경로. 실제 데이터·새 backbone 계산 없음.
- 같은 폴더 `plan.json`: 고유가설·성공/실패 수치·11cohort·입력SHA·code_changes 신규2파일(baseline=null).
- `tests/test_smooth_presence_objective.py`: 정상/정확점 값·gradient bitwise동치, 동일토큰 weak loss동일·masked불변, weak없는fit동치, 합성수렴/invalid point 거절.
- `docs/collaboration/tasks/surface-smooth-presence-20261027.md`, 이MD와 동명HTML: 고정계약·실행/미채택·검증/롤백 기록.

## 실행 검증

명령: `./experiment --plan tools/experiments/surface-smooth-presence-20261027/plan.json -- .venv/bin/python artifacts/surface-smooth-presence-20261027/worker.py`

격리 관련13검사OK(1.070초), main 관련13검사OK(0.960초). 최종 두 후보 관련17검사OK. source 함수수 objective3/worker2/test4, fit→closure→smooth_presence_loss→detail_bag_loss→point_bag_loss 최대4전이. 정상/실제점 동치 검사는 실제자료 수렴을 보장하지 않으며 이번 실험에서 구분했다.

검증/실행 source: main b5fc5b2. 실행 source와 snapshot은 record.json/code/changes.diff에 보존했다. 과거 failed normal-group-objective와 다른 가설이며 그 source/기록을 수정하거나 재시도하지 않았다.

## 위험·롤백·보고서

수렴 실패는 성능 악화나 가설 반증이 아니다. 이 후보는 실제 자료에서 수렴/성능을 통과하지 못했으므로 사용하지 않는다. 코드 제거는 `./develop -- git revert b5fc5b2` 후 관련 검사와 일반 push. 연구 전용 신규 파일만 있어 운영 source/model 복구는 필요 없다. 실패 기록과 snapshot은 보존한다.

로컬 실패 HTML: `artifacts/experiments/20261027T144107-8f7674cd/failure-report.html`. 실제 after사진/점수를 대신 만들지 않았다. 열기 상태는 최종 문서와 응답에 명시한다.

## 에튜 포인트

최적화 수렴과 분류 성능은 별개다. gradient 보호가 실패하면 예측 숫자가 있더라도 완성된 비교로 받아들이지 않는다. 이번에는 허용1e-5보다 큰2.46e-5를 확인해, 일부 완료fold를 전체 성능으로 합산하지 않았다.

## 보존·호출·원격·정리

Claude의 데이터 보완 checkout·새 사진·정답·manifest·공용 학습/추론 source·운영 Gemini fallback·PokeCollector는 수정하지 않았다. 기존 모델 파일·캐시·사람 응답의 실행 전후 SHA가 같았다. 모든 source 변경은 자기 worktree의 ./develop 잠금 안에서 했고, 실제 학습은 기본 checkout의 ./experiment로 직렬 실행했다. 외부 Gemini/Codex 모델 호출0·새 backbone forward0·새 라벨0·운영채택0이다.

개발 자동검토 policy의 session_id가 현재 세션과 달라 자동 handoff/next_steps/token_report는 생성되지 않았다. artifacts/development-cycle/latest.json은 과거 세션 기록이므로 이번 실행의 대체 근거로 사용하지 않는다. 각 실제 record.json의 status/판정을 사용한다.

최종 관련17검사(main,1.399초)가 통과했다. 합성/계약 검사는 모델 성능이 아니다. source별 AST·호출 깊이는 아래 인계와 task에 명시했다. git diff --check 통과. 실행 record.files의 모든 SHA와 원본 input_sha256을 최종 대조했다.

코드 main/origin f75c0c57421aa5d6473da966af2a8ee1919262e4 일치 확인 후 이 결과 문서를 별도 커밋·일반 push한다. force push/이력 재작성 없음.

이전 Codex coverage·smooth-presence checkout은 전달 커밋의 main 대응·clean·Git 작업 없음·개발 잠금 비차단 획득·고유 lock 증거 SHA 보존을 확인한 뒤 일반 worktree remove로 정리했다. 브랜치/이력은 보존하고 같은사진 ranking checkout을 최신 롤백용으로 유지했다. Claude 데이터/작성 중/미통합/부분통합과 다른 Codex checkout은 보존했다. 감사: artifacts/surface-same-photo-ranking-20261027/worktree-cleanup/audit.json.

## 실제 성능과 진척의 경계

고정 진척은 PROGRESS_CRITERIA.md와 development-progress.json의 usable-card-analysis-v1.0 기준30/100(+0%p)을 유지했다. 같은 개발 자료의 작은 부분 개선은 전 범위 품질·독립시험·실사용 완료가 아니다. 기존11cohort의 기준을 지우거나 완화하지 않았다. 새로운 실제점·정상/독립 정답을 만들지 않았고, 검증 사진을 새 학습에 편입하지 않았다.

같은 loss의 계수·margin·온도·수렴 허용치 탐색을 더 하지 않는다. 신규 정상 실물 다양성과 독립 정답은 Claude 데이터 보완 작업의 의존으로 남는다. 이번 결과로 새 오류를 감수한 운영 채택이나 모델 완성도를 주장하지 않는다.

## 최종 HTML 열기 상태

실제 사진 index/바뀐9구역 changes 페이지, 미채택 결과 요약, 수렴 실패 HTML 모두 Codex 브라우저 도구가 queued를 반환했다. 열기 요청은 전달됐고 실제 HTML 렌더는 미확인이다. 정적 본문/수치/파일 존재 대조와 PNG1개 직접 확인만 수행했다.
