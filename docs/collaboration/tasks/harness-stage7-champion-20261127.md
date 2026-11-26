# 하네스 7단계 — Champion 레지스트리·승격·복원 (2026-11-27)

```text
task_id: harness-stage7-champion-20261127
owner: Claude (하위 에이전트, 구현·시험. 독립 Opus 검증은 메인이 따로 수행)
status: assigned
base_sha: d582cc25196dd7b2eb49d55098363a41159979d2 (2단계 runner 작업 계약 커밋)
branch: claude/harness-champion-20261127
worktree: 로컬 경로는 커밋하지 않음(세션 전달)
goal: IMPLEMENTATION.md 2절 7행 "승격 중 kill -9에도 포인터 일관, 복원 Champion 출력 해시 재현,
  감사 미완료 시 승격 거절"을 합성 시험으로 통과한다(검증: 강제 종료·복원·감사 대기 시험).
  (a) 승격 중 어느 시점에 kill -9를 맞아도 포인터는 이전 또는 새 Champion 하나를 완전하게 가리킨다
  (b) 필요한 Silver 감사가 끝나지 않았으면 승격을 거절한다(`audit_pending`)
  (c) 같은 층·분모·봉인 판본이 아니면 비교·승격을 거절한다(`not_comparable`)
  (d) 현재 Champion이 무효이면 마지막 검증된 Champion으로 되돌리고, CAS에서 꺼낸 가중치 해시를 기록값과 재대조한다
  (e) Silver 묶음 무효화는 그 묶음을 쓴 모델과 후속 모델을 모두 invalidated로 표시하고, 현재 Champion이 포함되면 복원한다
allowed_files:
  - harness/registry.py, harness/champion.py, harness/lineage.py
  - harness/gate.py (함수 수 제한 때문에 추가: 승격 관문 검사. 아래 "구현 명세" 참조)
  - tests/test_harness_champion_*.py (신규만, 시험 공용 도구 tests/test_harness_champion_support.py 포함)
  - 이 task 문서
forbidden_files: harness/runner.py, harness/route.py(다른 에이전트 작업 중), 1단계 파일(harness/{cas,ledger,jsonio,contract,manifest,
  queue,states,holder,recovery,lease,checkpoint,graph}.py 수정 금지: 공개 함수 호출만),
  card_condition/**, tools/**, 기존 tests/**, AGENTS.md, docs/agent/**, artifacts/**, data/**, 라벨·사진·모델·비밀 설정, .claude/**, 다른 plan 문서
contract:
  입력: 호출자가 준 root(런타임 상태는 root 아래에만), now(시각, 호출자 주입), 모델 식별 필드(코드 SHA·가중치 파일·자료 manifest SHA·설정),
        평가 결과 {layer, denominator, seal_version, metrics}, 사용한 Silver 묶음 ID 목록, 부모 모델 ID(선택), 감사 상태 {batch_id: 상태}.
  출력: root/models/registry.jsonl(1단계 ledger 해시 체인), root/models/champion.json(포인터), root/cas/(1단계 CAS 공유),
        root/ledger.jsonl(1단계 주 장부에 승격·복원·무효화 요약 추가), root/models/restored/<model_id>/weights(복원 재현본).
  보존할 조건: stdlib만, Python 3.9+ 문법. 네트워크·LLM·`claude`·학습·추론 없음. 1단계 55개 시험 통과 유지.
structure: 파일당 함수 정의 ≤7(클래스 메서드·중첩 포함), 이 작업이 만든 공개 함수의 파일 안 호출 깊이 ≤2(PAIR_CODING 한도 4보다 엄격:
  2단계가 1단계 내부를 평탄화할 수 있고 supervisor가 이 함수를 다시 부르기 때문). 1단계 호출을 포함한 현재 측정 깊이는 인계 절 표.
checks:
  - `PYTHONDONTWRITEBYTECODE=1 /Users/jueun/WebstormProjects/pokemon-card-condition/.venv/bin/python -m unittest discover -s tests -p "test_harness_*.py"` 종료 코드 0 (1단계 55개 포함)
  - 같은 명령 `/usr/bin/python3`(3.9)
  - 변이 시험(임시 복사본에서만): 감사 검사 제거, 원자 교체를 직접 쓰기로 변경, 계보 후속 처리 제거 등이 시험에서 잡힘
  - ast 함수 수·호출 깊이, `git diff --check`, `git diff --name-only d582cc2 HEAD`가 허용 파일 안
experiment: 없음. 합성 시험이며 모델 성능 근거가 아니다.
handoff: (구현 후 아래 인계 절을 채움)
```

## 설계 근거(원문)

- DESIGN.md 8절: 레지스트리 `registry.jsonl`(해시 체인)과 내용 주소 저장소에 코드 SHA·가중치 SHA·자료 manifest SHA·설정·평가 결과·봉인 판본·
  사용한 Silver 묶음 ID(계보)를 보존. 비교는 같은 층·분모·봉인 판본에서만. 승격은 포인터 파일 원자 교체, 이전 Champion은 삭제하지 않음.
  회귀·장애·감사 실패 시 마지막 검증된 Champion으로 복원.
- DESIGN.md 5-4절 비동기 규칙: 필요한 감사가 끝나기 전에는 Champion 승격 불허. 감사 실패 시 그 Silver를 쓴 모델과 후속 모델을 계보로 추적해
  무효화하고 마지막 정상 Champion으로 복원. (정책 철회·Silver→Pending 전환은 이번 범위 밖.)
- 범위 밖(설계에 있으나 이번 단계 아님, 구현하지 않음): 감사 실행·Silver 생성·평가 지표 계산·"개선되었는가" 판정(6단계)·승격 예산·봉인 교체·
  초기 Champion의 실제 SHA 등록·회귀 검사 실행·Supervisor 자동 호출.

## 구현 명세

모든 경로·시각은 호출자가 준다(기본값 없음). 포인터 교체는 임시 파일 + fsync + `os.replace` + 디렉터리 fsync.

1. `registry.py` — 모델 레지스트리(해시 체인 ledger 재사용). 이벤트: `registered`(모델 기록), `switch_intent`·`switched`·`switch_aborted`
   (Champion 전환의 선기록 로그), `invalidated`(모델 목록과 원인). `load(root)`는 체인 검증(`ledger.verify`) 실패 시 `RegistryError`,
   성공 시 이벤트를 접어 `{models, history, pending, hashes}`를 만든다. `register(...)`는 가중치를 CAS에 보관하고 모델 ID(식별 필드의 해시)를 돌려준다.
   등급(`Challenger`·`Dev-leader`·`Champion`)과 상태(`valid`·`invalidated`)를 가진다. 등급 `Champion`은 승격으로만 붙는다.
2. `gate.py` — 승격 관문: 모델 유효성(자신과 조상), 가중치 CAS 보관, 비교 가능성(층·분모·봉인 판본), 봉인 층, 감사 상태(계보 전체의 Silver 묶음).
3. `champion.py` — 포인터와 전환. 전환은 선기록(WAL): `switch_intent` 기록 → 포인터 원자 교체 → `switched` 기록 → 주 장부 요약.
   중간에 죽으면 다음 호출의 `settle`이 포인터와 의도를 대조해 `switched`를 마저 쓰거나(포인터가 이미 바뀜) `switch_aborted`를 쓴다(안 바뀜).
   `promote`는 이미 그 모델이 현재 Champion이면 아무 것도 쓰지 않고 성공(멱등). `restore_last_verified`는 현재 Champion이 무효일 때만
   (또는 `regression` 사유를 주면 그 사유로 무효화한 뒤) 가장 최근의 다른 유효한 이전 Champion으로 돌리고, CAS에서 꺼낸 가중치의 해시를
   레지스트리 기록값과 재대조한다. 해시 불일치·CAS 손상은 `ChampionError`이며 포인터는 바꾸지 않는다.
4. `lineage.py` — `invalidate_lineage(root, now, silver_batch_id)`: 해당 묶음을 쓴 모델 + 부모 관계로 이어진 모든 후속을 한 이벤트로 무효화하고,
   현재 Champion이 포함되면 복원한다.
5. 동시 호출은 `root/models/.lock`(`fcntl.flock`)으로 직렬화한다. 잠금은 프로세스가 죽으면 풀린다.

## 필수 시험

시험 파일당 정의 ≤7개로 나눈다.

| 시험 | 방법 | 기대 |
|---|---|---|
| kill 승격 | 하위 프로세스가 승격 중 SIGKILL을 스스로 맞음(의도 기록 후·교체 직전·교체 직후·완료 기록 전 등 지점 지정) + 임의 지연 외부 kill 반복 | 포인터는 항상 이전 또는 새 Champion 하나를 완전히 가리킴, 재호출로 일관 상태 복구 |
| 감사 대기 | 계보의 Silver 묶음 감사가 미완료·실패·누락 | `audit_pending`/`audit_failed` 거절, 완료·`not_required`만 통과 |
| 비교 불가 | 층·분모·봉인 판본 중 하나만 다름 | 각각 `not_comparable` 거절 |
| 복원 | 이전 Champion으로 복원, 가중치 해시 재현 / CAS 손상 / 재대조 불일치 | 재현 성공, 손상은 명시적 오류 + 포인터 불변 |
| 계보 | 직접·후속·무관 모델, Champion 포함 시 자동 복원 | 직접·후속만 invalidated, 무관 유지 |
| 변조 | 레지스트리 줄 변조·삭제·순서 변경, 포인터가 가리키는 항목 삭제 | `RegistryError`로 거절 |
| 멱등 | 같은 모델 이중 승격, 같은 모델 이중 등록 | 두 번째는 장부·포인터 변화 없음 |

## 인계 (구현 후 채움)

(구현·검증 후 작성)
