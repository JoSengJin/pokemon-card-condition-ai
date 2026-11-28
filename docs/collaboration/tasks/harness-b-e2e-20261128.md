# harness-b-e2e-20261128 — B5-11 합성 종단 시험 (구현 담당 b)

- 브랜치 `claude/harness-b-e2e-20261128`, 분기 `71ae689`. 새 파일만: `tests/harness_b5_e2e_kit.py`, `tests/test_harness_b5_e2e_synthetic.py`, 이 문서. `harness/` 코드 변경 0(경로 변경 없음, 연결이 끊겨 고칠 결함 없음).
- 증거 구분: **합성 종단 검증**까지만. 실제 실험·다음 가설 검증, 실제 학습·평가·자동 재개 검증, 모델 누락·오탐 개선 입증은 **모두 아님**. **실제 `./experiment`·실제 claude·실제 학습·평가·승격·모델·네트워크 호출 0건**(가짜 executor·가짜 claude·합성 구역 행).

## 연결된 것 (한 번의 Supervisor 실행)
`python -m harness.supervisor --max-cycles 3`(프로세스 1개, 실제 sandbox-exec 안 runner) 하나로 사용자 추가 입력 없이 이어진다. 사람이 쓰는 입력은 `supervisor/declared.json`(대조 실험 E1·학습·평가)뿐.

| 회차 | 일어난 일(장부 줄 seq, 증거 폴더의 ledger.jsonl) |
|---|---|
| 1 | E1·학습 등록·실행(0~7) → 적용기가 학습을 모델 레지스트리에 등록(8, `apply_drain`) |
| 2 | 게이트: E1 VERIFIED → 분석 선언(9) → 분석·평가 등록(10·11, 평가는 학습 VERIFIED 뒤) → 평가 실행(12~14) → 채점 판정 `통과`, promoted=false(15·16) → 가짜 claude가 `next_plan.json` 작성(17~23) |
| 3 | 게이트: 분석 VERIFIED → 다음 실험 E2 선언(24, `experiment_parameter.value` 0.7 하나만 변경) → 등록·실행(25~28) |

회차가 3인 이유: 의존 선언(분석·평가·다음 실험)은 의존 작업이 VERIFIED가 된 **다음 회차 시작**에 등록된다(`plan_gate.gate`·`graph.register_missing` 설계). 한 회차로는 안 이어진다. 예산 차감 4건 = 실험 2·학습 1·평가 1(runner 설계: 실험·학습·평가 실행 시작마다 1건).

증거 복사본: `<SP>/logs/b-e2e-evidence/`(ledger.jsonl, supervisor-summary.json, registry.jsonl, verdict-*.json). SP=/private/tmp/claude-501/-Users-jueun-WebstormProjects-pokemon-card-condition/3ac90d12-9006-4053-8e80-9c07f515da2d/scratchpad

## 끊긴 곳 (연결 시험에서 확인, 장부·큐 줄로 증거)
1. **실제 어댑터 경로(experiment_exec) + 실제 sandbox**: 가짜 `./experiment`를 부르는 실제 어댑터를 진입점에서 돌리면 sandbox가 원본 저장소 `artifacts/` 쓰기를 막아 E1이 결과 불명(INTERRUPTED)이 되고, `plan_gate_declared`·분석 등록·`apply_drain`·`promotion_verdict` 줄이 하나도 생기지 않는다(둘째 시험이 고정). 알려진 결정(D안: 실제 연결은 첫 실험 승인 뒤)이며 `harness/experiment_exec.py`는 다른 담당(A4)이라 건드리지 않았다. 따라서 위 종단 시험의 실험 단계는 `tests/harness_plan_gate_kit.fake_experiment`(심은 동결 기록을 옮기는 가짜 executor)이지 어댑터가 아니다. 어댑터가 해석하는 실험 결과 → 분석 연결은 실제 경로에서 미검증이다.
2. **다음 가설 ↔ 학습 연결 없음(설계상)**: PLAN_GATE는 다음 *실험*만 선언한다. 학습·평가 계약은 사람이 선언하며, 다음 가설(E2)이 새 학습을 만들지 않는다. 판정(`promotion_verdict`)도 분석 입력으로 돌아가지 않는다(분석 입력은 실험 기록뿐). "실험→다음 가설"과 "학습→평가→승격 판정"은 한 실행 안에서 병행하지만 서로 먹이지 않는다.
3. **알려진 한계(재확인만, 이번에 시험하지 않음)**: 부모 가중치를 CAS에서 꺼내는 경로가 없어 두 번째 학습부터 막힘(R/HANDOFF 0절 C1). 승격 실행 없음(미승인).

## 범위 밖
B5-9(Silver·능동 학습·감사): 입력 없음으로 미구현이라 이 시험에서 뺀다. 자동 재개·한도 재개·Gold 경로는 기존 시험이 다룬다.

## 시험 (대상 SHA는 커밋 로그 참조)
- 새 시험 3건: 종단 1, 실제 어댑터 sandbox 끊김 1, 구조(함수 ≤7·호출 깊이 ≤4) 1. 모두 통과.
- 보호 확인: 일부러 `supervisor.run`의 `plan_gate.gate` 호출을 제거하거나 `_apply` 호출을 제거하면 종단 시험이 실패한다(둘 다 확인 후 원복).
- 전체 시험(커밋 85eda3c 코드, 이 문서만 추가 전): 3.12(.venv) 550 OK 334초, 3.9(/usr/bin/python3) 550 OK 381초(기준 547 + 새 3). 로그 `<SP>/logs/b-e2e-312.log`·`b-e2e-39.log`. kill9 시험 간헐 실패는 이번엔 없었다.

## 한계·미검증·사용자 확인 필요
- 합성이다. 가짜 실험 executor는 실제 어댑터의 결과 해석(record·result 해시 대조)을 거치지 않는다(끊긴 곳 1).
- 사용자 확인 필요: 끊긴 곳 1·2를 어떻게 다룰지(첫 실험 승인 때 sandbox 프로필 구현, 판정→다음 가설 입력은 설계 결정).

## 롤백
`git revert <이 브랜치 커밋>`(새 파일 3개뿐). 통합 전이므로 worktree·브랜치 삭제로도 충분.
