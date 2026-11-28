# 하네스 7단계 — Champion 레지스트리·승격·복원 (2026-11-27)

```text
task_id: harness-stage7-champion-20261127
owner: Claude (하위 에이전트, 구현·시험. 독립 Opus 검증은 메인이 따로 수행)
status: ready_for_review
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
  - harness/pointer.py (독립 검증 반영으로 추가: 포인터 읽기·대조·읽기 규약·임시 파일 정리. champion.py 함수 수 한도 때문에 분리)
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
handoff: 아래 인계 절. 독립 Opus 검증은 메인이 따로 수행(이 하위 에이전트는 구현·시험·변이 확인만).
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
3. `pointer.py` — 포인터 읽기와 대조. `current(root, state)`는 포인터가 마지막 완료 전환(`history[-1]`) 또는 대기 중 의도(`pending`)의
   (의도 해시, 대상 모델)과 정확히 같고 가중치 해시도 같을 때만 통과한다(다른 모델로 바꾼 포인터·의도가 아닌 줄 해시·오래된 포인터 파일 복귀·포인터 삭제는 `ChampionError`).
   **읽기 규약:** `current`는 `registry.lock` 안에서 load한 state와만 쓴다. 잠금 없이 `load` 뒤에 `current`를 부르면 그 사이 다른 프로세스의 승격과 어긋나
   거짓 오류가 날 수 있으므로, 잠금을 쥐지 않은 읽는 쪽은 `read_current(root)`(잠금 안에서 load+current, 쓰기 없음)를 쓴다.
   `clean_tmp(root)`는 kill로 남은 `*.tmp.<pid>`를 지운다(잠금 안에서만).
3-1. `champion.py` — 포인터와 전환. 전환은 선기록(WAL): `switch_intent` 기록 → 포인터 원자 교체 → `switched` 기록 → 주 장부 요약.
   중간에 죽으면 다음 호출의 `settle`이 포인터와 의도를 대조해 `switched`를 마저 쓰거나(포인터가 이미 바뀜) `switch_aborted`를 쓴다(안 바뀜).
   `promote`는 이미 그 모델이 현재 Champion이면 아무 것도 쓰지 않고 성공(멱등). `restore_last_verified`는 현재 Champion이 무효일 때만
   (또는 `regression` 사유와 `model_id`를 주면, 현재 Champion이 그 모델일 때만 그 사유로 무효화한 뒤) 자신과 모든 조상이 유효한 가장 최근의 다른 이전 Champion으로 돌리고, CAS에서 꺼낸 가중치의 해시를
   레지스트리 기록값과 재대조한다. 해시 불일치·CAS 손상은 `ChampionError`이며 포인터는 바꾸지 않는다.
4. `lineage.py` — `invalidate_lineage(root, now, silver_batch_id)`: 해당 묶음을 쓴 모델 + 부모 관계로 이어진 모든 후속을 한 이벤트로 무효화하고,
   현재 Champion이 무효이면(이번 무효화 때문이든, 무효화 뒤 복원 전에 죽은 이전 호출 때문이든) 복원한다. 새로 무효화할 모델이 없어도 복원은 이어간다.
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

## 인계

### 결과

필수 시험 7종을 실제 subprocess·실제 SIGKILL로 통과했다. 합성 시험이며 모델 성능·정확도 근거가 아니다. 이번 변경은 개발 진척 7단계(Champion
레지스트리·승격·복원)의 구현이며 실험·학습·추론·외부 AI 호출은 없다. 1차 독립 검증(Opus, `647cd77` 기준)은 "조건부 통과"(중요 3·경미 4)였고 아래 "독립 검증 지적 반영"으로 고쳤다. 고친 뒤의 재검증은 아직 받지 않았다.

### 대상 SHA와 실행 명령

| 항목 | 값 |
|---|---|
| 작업 계약 커밋 | `d1cb8a34e3f4445b1088215c02d524dd72d87d2d` |
| 구현 (`feat(harness)`) | `794bbb7b620cc985c34e489b388059a08565acc7` |
| **최종 시험 대상 (구현 + 시험, `test(harness)`)** | `9ec67e7b578bd3068e42918d1bccbd048f1410d4` (88개 = 1단계 55 + 이번 33) |
| 인계 문서 (1차) | `647cd7753332078fc4cefcdbcbd22e610920f5ce` |
| 검증 지적 반영 구현 (`fix(harness)`) | `053dde788e931b021ab3c7957838f8c1291e49dd` |
| **검증 지적 반영 후 최종 시험 대상 (`test(harness)`)** | `65bb1eb552e906657f28281f7f7ee90c657a44da` (95개 = 1단계 55 + 이번 40) |
| 이 문서 갱신 커밋 | 시험 대상 위에 문서만 추가(코드 변경 없음). SHA는 `git log`로 확인 |

위 표의 앞쪽 행(`9ec67e7` 등)과 그 아래 첫 번째 명령 표는 1차 인계 시점의 기록이다. 최신 결과는 "지적 반영 후 실행 명령"을 본다.

| 명령 (cwd = worktree, 시험 대상 SHA에서 실행) | 종료 코드 |
|---|---|
| `PYTHONDONTWRITEBYTECODE=1 /Users/jueun/WebstormProjects/pokemon-card-condition/.venv/bin/python -m unittest discover -s tests -p "test_harness_*.py"` (Python 3.12.14) | 0 (88개 통과) |
| 같은 명령 `/usr/bin/python3` (Python 3.9.6) | 0 (88개 통과) |
| 위 3.12 명령 + `-W error::ResourceWarning`, 3회 반복(시험 대상 SHA, 88개) | 0, 0, 0 |
| `git diff --check d582cc2 HEAD` | 0 |
| `git diff --name-only d582cc2 HEAD` | 허용 파일 안(이 문서, harness/{registry,gate,champion,lineage}.py, tests/test_harness_champion_*.py 8개) |

변이 시험(임시 복사본에서만, 원본 수정 없음. 스크립트는 scratchpad): 22개 변이 모두 시험 실패로 잡힘(살아남은 변이 0).
감사 검사 제거(M1), pending을 통과로 취급(M2), 조상 묶음 감사 무시(M2b), 원자 교체를 직접 쓰기로(M3a), 선기록 순서 위반(M3b),
settle 항상 abort(M3c)·비활성(M3d), 계보 후속 처리 제거(M4), 무효화 뒤 자동 복원 제거(M4b), 복원 CAS 재현 제거(M5)·해시 재대조 제거(M5b),
비교 가능성 검사 제거(M6)·봉인 층 검사 제거(M6b), 이중 승격 멱등 제거(M7), 체인 검증 생략(M8), 복원이 가장 오래된 Champion 선택(M9),
포인터-레지스트리 대조 제거(M10), 복원이 무효 후보 선택(M11), 잠금 제거(M12), 무효 모델 승격 허용(M13), 무효 Champion을 valid로 취급(M14),
CAS 존재 검사 제거(M15). 잡지 못하는 것: 디렉터리 fsync 제거(정전 내구성은 프로세스 kill로 시험할 수 없음).

### 독립 검증 지적 반영 (`647cd77` → `65bb1eb`)

| # | 지적 | 조치 | 시험 |
|---|---|---|---|
| 1 중요 | `invalidate_lineage` 재호출 시 `ids=[]`이면 복원을 건너뛰어 무효 Champion이 남음 | `ids`가 비어도 현재 Champion이 무효이면 `restore_locked`를 수행(`lineage.py`). 반환 `invalidated`는 "이번에 새로 무효화한 모델" | kill_points :: test_kill_during_lineage_invalidation_then_same_call_again_finishes_the_restore (무효화 전·후 + 승격 7지점 + CAS 꺼내기 중, 10지점) |
| 2 중요 | 잠금 없이 `load` 뒤 `current` 호출 시 거짓 `ChampionError` | `pointer.read_current(root)` 신설(잠금 안에서 load+current, 쓰기 없음). `current`는 잠금 안에서 load한 state와만 쓰도록 docstring·이 문서에 규약 명시. `champion.current`·`champion.read_current`는 `pointer`의 별칭 | kill_random :: test_unlocked_readers_get_no_false_error_while_promotions_keep_happening (승격이 계속되는 2초간 `read_current` 반복, 오류 0, 두 모델 모두 관측) |
| 3 중요 | 포인터 대조가 약함(다른 모델·registered 줄 해시·오래된 포인터 통과) | `pointer.current`가 포인터의 (의도 해시, 모델 ID)가 `history[-1]` 또는 대기 중 의도와 정확히 같고 가중치 해시도 같을 때만 통과. 포인터 삭제(승격 기록 있음)도 거절 | guards :: test_tampered_stale_or_missing_pointer_is_refused (7종 + 삭제) |
| 4 경미 | 복원 후보가 조상 유효성을 안 봄 | `restore_locked`가 후보의 조상 사슬 전체(`gate.ancestors`)가 유효해야 선택 | guards :: test_child_of_an_invalid_ancestor_is_refused_for_promotion_and_restore |
| 5 경미 | `restore_last_verified(regression=...)` 재호출이 복원한 정상 Champion까지 무효화 | `model_id` 인자 신설: regression은 `model_id` 필수, 현재 Champion이 그 모델일 때만 무효화 | restore :: test_regression_restores_..., kill_points 복원 시험의 같은 인자 재호출 |
| 6 경미 | 승격 중 kill 뒤 `champion.json.tmp.<pid>` 누적 | `pointer.clean_tmp`(models/ 아래 `*.tmp.*`)를 `settle`이 잠금 안에서 호출 | guards :: test_settle_supplements_main_ledger_and_removes_leftover_temp_files |
| 7 경미 | 시험 공백 N10·N11·N16·N6 | 무효 현재 Champion 재승격 거절, 조상 무효 자식 승격·복원 거절, 승격 kill 뒤 lineage 호출, settle의 주 장부 보충 단언 | guards :: test_invalid_current_champion_cannot_be_reconfirmed_by_promote, test_child_of_an_invalid_ancestor_..., test_lineage_call_after_a_killed_promotion_settles_first, test_settle_supplements_... |

추가로 N1(settle이 모델 ID로 판단) 변이가 살아남아 같은 시험에 "포인터가 이미 같은 모델을 가리키는 오래된 의도"를 `switch_aborted`로 처리하는지 단언을 더했다.
`champion.py`가 함수 수 한도(7)에 닿아 포인터 읽기·대조·임시 파일 정리를 `harness/pointer.py`(함수 3개)로 분리했다. `pointer.py`는 이 작업 계약의 allowed_files에 추가한다.

### 지적 반영 후 실행 명령 (시험 대상 `65bb1eb552e906657f28281f7f7ee90c657a44da`)

| 명령 | 종료 코드 |
|---|---|
| `PYTHONDONTWRITEBYTECODE=1 /Users/jueun/WebstormProjects/pokemon-card-condition/.venv/bin/python -m unittest discover -s tests -p "test_harness_*.py"` (3.12.14) | 0 (95개) |
| 같은 명령 `/usr/bin/python3` (3.9.6) | 0 (95개) |
| 3.12 + `-W error::ResourceWarning`, 3회 | 0, 0, 0 |
| `git diff --check` | 0 |

변이 재실행(임시 복사본, 원본 수정 없음): 최초 22개 변이 중 지적 반영으로 대상 코드가 바뀐 4개(M4b·M10·M11·M14는 P8·N17·P7·P9로 대체)를 뺀 18개 모두 잡힘.
검증자 `mutate.py` 복사본(바뀐 문자열만 맞춤) N1~N19 19개 중 18개 잡힘, N18(디렉터리 fsync 제거)은 프로세스 kill로 관측할 수 없어 살아남는다(알려진 한계, 미검증 참조). N1은 처음 실행에서 살아남았으나 시험 보강 뒤 잡힘.
새 변이 P1(포인터가 과거 어느 전환이든 허용)·P2(포인터 삭제 허용)·P3(포인터 가중치 해시 미검사)·P4(`read_current` 잠금 제거)·P5(`clean_tmp` 무동작)·P6(회귀 무효화가 model_id 무시)·P7(복원 후보 조상 무시)·P8(계보 복원 조건을 옛 방식으로)·P9(valid 항상 True) 9개 모두 잡힘.
N10·N11·N16·N6도 잡힘.

### 필수 시험 대응

| 필수 | 시험 (파일 :: 이름) |
|---|---|
| kill 승격 | kill_points :: test_kill_while_replacing_an_existing_champion, test_kill_during_the_first_promotion(지점 7개: 의도 기록 전·후, 포인터 임시 파일 fsync 전, 교체 전·후, switched 후, 주 장부 후), test_kill_during_restore_...(같은 7개 + CAS 꺼내기 중). kill_random :: test_repeated_kill_at_random_moments... (30회, 임의 지연 외부 SIGKILL. 일회성 별도 관찰에서 30회 중 6회가 짝 없는 의도를 남겨 settle 경로가 실제로 쓰였으나 시험이 그 횟수를 단언하지는 않는다), test_reader_never_sees_a_partial_pointer... (읽는 쪽 1.5초) |
| 감사 대기 | audit :: 5개(누락·pending·부분 완료 `audit_pending`, `audit_failed`, complete·not_required 통과와 재시도, 조상 묶음, 묶음 없는 모델) |
| 비교 불가 | promote :: test_different_layer_denominator_or_seal_version_is_refused (3개 각각), test_non_sealed_layer_cannot_become_champion |
| 복원 | restore :: 5개 (해시 재현·기록, 한 단계씩 되돌림·더 갈 곳 없음, CAS 손상 시 오류+포인터 불변, 복사본 해시 불일치 오류, 복원 후 재복원 무변화·후속 승격) |
| 계보 | lineage :: 5개 + kill_points 계보 kill 재호출 + guards 승격 kill 뒤 계보 호출 (직접·후속·손자 무효, 무관 유지, Champion 포함 시 이전 Champion으로 자동 복원, 무관 Champion 유지, 반복·미지 묶음 무변화, 이미 무효인 중간 모델의 후속 추적, 무효 계보 승격 거절) |
| 변조 | registry :: 줄 변조·중간 삭제·순서 변경, 꼬리 잘림(포인터 대조와 `expected_tail`), 체인은 유효하나 앞뒤가 안 맞는 줄·중복 등록 |
| 멱등 | promote :: test_double_promotion_writes_nothing_the_second_time, registry :: test_same_model_twice_is_idempotent_and_a_different_evaluation_conflicts, kill_random :: 같은 모델 동시 승격은 한 번만 전환 |

### 파일별 함수 정의 수 (ast, 한도 ≤7)

| 파일 | 수 | 파일 | 수 |
|---|---|---|---|
| harness/registry.py | 5 | tests/test_harness_champion_support.py (시험 아님) | 7 |
| harness/gate.py | 3 | tests/test_harness_champion_registry.py | 7 (시험 6) |
| harness/champion.py | 6 | tests/test_harness_champion_promote.py | 7 (시험 6) |
| harness/lineage.py | 2 | tests/test_harness_champion_audit.py | 7 (시험 5) |
| harness/pointer.py (신규) | 3 | tests/test_harness_champion_restore.py | 7 (시험 5) |
| | | tests/test_harness_champion_lineage.py | 7 (시험 5) |
| | | tests/test_harness_champion_guards.py (신규) | 7 (시험 5) |
| | | tests/test_harness_champion_kill_points.py | 6 (시험 4) |
| | | tests/test_harness_champion_kill_random.py | 6 (시험 4) |

### 호출 깊이 (전이 수)

현재 코드 기준(`7062c52`, 2026-11-27 재측정). 통합 뒤 `6103a41`이 `champion._materialize`를 `restore_locked` 안에, `ledger._hash_entry`를 `ledger.append`·`_check_line` 안에 펼쳐
함수 수가 `champion.py` 6→5, `ledger.py` 6→5가 됐다(위 "파일별 함수 정의 수" 표는 구현 당시 값이며 `champion.py`는 현재 5).
측정: ast로 이름 참조(호출과 콜백)를 간선으로 센 보수적 상한. 스크립트는 저장소에 두지 않음(scratchpad). 순환 없음.
"이 작업 파일 안"은 registry·gate·champion·lineage·pointer 사이의 전이만, "1단계 포함"은 1단계 호출까지 더한 값이다.

| 진입 | 이 작업 파일 안 최장 | 1단계 호출 포함 최장 경로 |
|---|---|---|
| champion.promote | 2 (promote → settle → pointer.clean_tmp) | 3 (promote → gate.check → cas.has → cas.blob_path) |
| champion.restore_last_verified | 2 (→ restore_locked → _switch) | 3 (→ restore_locked → cas.get → cas.blob_path) |
| lineage.invalidate_lineage | 2 (→ restore_locked → _switch) | 3 (같은 cas.get 경로) |
| pointer.read_current | 2 (→ registry.load → apply) | 3 (read_current → registry.load → ledger.verify → _check_line) |
| registry.register | 2 (register → load → apply) | 3 (register → load → ledger.verify → _check_line) |
| registry.load | 1 (load → apply) | 2 (load → ledger.verify → _check_line) |
| champion.settle | 1 (→ pointer.clean_tmp) | 1 |
| champion.restore_locked | 1 (→ _switch) | 2 (→ cas.get → cas.blob_path) |

이 함수들을 부르는 5단계 `audit.record_verdicts`는 합산 4다(5단계 task 문서).

### 가정 (명세가 모호해 가장 보수적으로 고른 해석)

1. 모델 ID는 `(코드 SHA, 가중치 SHA, 자료 manifest SHA, config, 정렬·중복 제거한 Silver 묶음, 부모)`의 해시다. 평가 결과는 ID에 넣지 않는다: 같은 모델을
   다른 평가로 다시 등록하면 `conflict`로 거절한다(봉인 교체 뒤 Champion 재측정 기록은 이번 범위 밖, 아래 리스크).
2. 평가 필드 이름은 `layer`·`denominator`·`seal_version`·`metrics`이고 층 값은 `sealed`여야 Champion이 될 수 있다(`not_sealed`). DESIGN 8절
   "Champion = 봉인 확증 + ..."을 반영한 해석이다. 6단계(채점·승격 판정)의 어휘가 다르면 통합 때 맞춘다.
3. `promote`는 "개선되었는가"를 판정하지 않는다(6단계 몫). 호출자가 개선·민감도·회귀 판정을 마쳤다는 전제이며, 여기서는 구조 조건(유효성, 가중치 보관, 같은 층·분모·
   봉인 판본, 봉인 층, 계보 전체 감사 완료)만 본다.
4. 감사 상태는 호출자가 `audit_status={묶음 ID: complete|not_required|pending|failed}`로 준다. 모델 자신과 모든 조상(부모 사슬)이 쓴 묶음이 모두
   `complete`/`not_required`여야 하며, 누락·pending·그 밖의 값은 `audit_pending`, 하나라도 `failed`면 `audit_failed`다. 레지스트리에는 감사 상태를 저장하지 않는다.
5. 비교 대상은 포인터가 가리키는 현재 Champion(무효 상태여도)이다. 첫 Champion은 비교 없이 승격된다(초기 Champion 등록은 승격 예산을 쓰지 않는다는 설계와 맞춤).
6. 승격 거절은 예외가 아니라 `{"ok": False, "reason", "detail"}`이다. 레지스트리 변조·포인터 손상·CAS 손상·복원 해시 불일치는 `RegistryError`/`ChampionError`다.
7. 복원 후보는 "이전에 `switched`로 Champion이었던 모델 중 현재 모델이 아니고, 자신과 모든 조상(부모 사슬)이 유효한 가장 최근 것"이다(승격 관문과 같은 보수적 기준. 부모가 회귀로 무효이고 자식은 상태상 valid인 모델은 후보가 아니다). 후보의 CAS 가중치가 손상되어도 더 오래된 후보로
   조용히 넘어가지 않고 오류를 낸다(명세: 복원하지 않고 명시적 오류). 후보가 없으면 `no_verified_champion`(오류 아님)이며 포인터는 무효인 채 남고
   `champion.current(...)["valid"]`가 False로 알린다.
8. `restore_last_verified(root, now, regression="사유", model_id=<무효화할 모델>)`는 현재 유효한 Champion이 `model_id`와 같을 때만 그 사유로 무효화한 뒤 복원한다
   (회귀·장애가 감지된 호출자가 쓰는 입구). 같은 인자로 다시 불러도(이미 복원된 뒤) 새 Champion을 무효화하지 않는다. `regression`을 주고 `model_id`가 없으면
   `ChampionError`. 무효화(`invalidated`)는 복원 전환보다 먼저 기록되므로 복원이 실패해도 무효 사실은 남는다.
9. 전환은 선기록(WAL)이다: `switch_intent` → 포인터 교체 → `switched`. 주 장부(`root/ledger.jsonl`) 요약은 그 뒤에 쓰므로(1단계 가정 9와 같음) 중간에 죽으면
   빠질 수 있다. 정본은 레지스트리와 포인터이며, 다음 호출의 settle이 짝 없는 의도를 정리할 때만 주 장부 줄을 보충한다(포인터가 이미 바뀐 경우).
10. 복원된 가중치는 `root/models/restored/<model_id>/weights`에 쓴다. CAS는 1단계와 같은 `root/cas`를 공유한다.
11a. 읽기 규약: 쓰는 함수는 모두 `registry.lock` 안에서 load → settle → 판단 → 쓰기 순서다. `current(root, state)`는 같은 잠금 안에서 load한 state와만 쓰고,
    잠금을 쥐지 않은 읽는 쪽(Supervisor 점검 등)은 `read_current(root)`를 쓴다(승격이 끝나는 짧은 시간 기다림). 잠금 없이 `load` 뒤 `current`를 부르면 거짓 오류가 날 수 있다.
11b. `invalidate_lineage`는 새로 무효화할 모델이 없어도 현재 Champion이 이미 무효이면(예: 앞선 회귀 무효화 뒤 복원 후보가 없던 경우) 복원을 시도하고 그 결과를
    `restore`로 돌려준다(후보가 없으면 `{ok: False, reason: no_verified_champion}`).
11. `register`의 등급은 `Challenger`·`Dev-leader`만 받는다(`Champion`은 승격으로만 붙음). Dev-leader 선정 로직은 이번 범위 밖(호출자가 등급을 준다).

### 미검증

- 정전·OS 충돌(디렉터리 fsync, 파일 시스템 재정렬): kill -9로는 시험할 수 없다. 코드에 fsync를 넣었으나 효과는 미검증.
- 실제 `./experiment`·6단계 채점·Supervisor와의 통합, 초기 Champion(현재 채택된 후면 점검 모델)의 실제 SHA 등록: 하지 않았다.
- 지적 반영 뒤 독립 재검증(Opus): 아직 받지 않았다(메인이 따로 수행).
- `current()`의 `valid`는 모델 자신의 상태만 본다(조상 유효성은 승격·복원 후보에만 적용). 부모가 회귀로 무효이고 자식이 현재 Champion이면 `valid`는 True다.
- 매우 큰 레지스트리의 성능(`ledger.append`는 1단계 구현상 줄 수에 비례해 읽는다): 미측정.
- 여러 호스트·네트워크 파일 시스템에서의 `flock`: 미검증(로컬 macOS만).

### 리스크

- 봉인 교체 뒤 Champion 재측정 결과를 기록할 방법이 이번 범위에 없다. 교체 후에는 `seal_version`이 달라 모든 후보가 `not_comparable`이 되므로,
  후속 단계에서 재측정 평가 이벤트(예: `evaluated`)를 레지스트리에 추가하는 설계가 필요하다(설계 8절 마지막 줄).
- 무효 Champion만 남고 복원 후보가 없으면 포인터는 무효 모델을 가리킨 채 남는다. 소비자(Supervisor)는 `read_current(root)["valid"]`를 반드시 확인해야 한다.
- `audit_status`를 호출자가 준다: 잘못된 입력은 막지 못한다. 감사 상태의 정본 저장·변조 방지는 5단계(감사)에서 정해야 한다.
- kill 시험이 `ledger.append`·`os.replace`·`os.fsync`를 하위 프로세스에서 감싸 SIGKILL을 보내는 방식이라 1단계 내부 구현(예: 이들 호출 방식) 변경 시
  시험의 지점 매칭이 어긋날 수 있다(그 경우 "SURVIVED"로 실패해 알려 준다).
- 1단계 `ledger.append`가 마지막 줄 손상을 이유로 이어 쓰기를 거절하므로, 쓰기 도중 줄이 잘리는 (이론상 가능한) 상황에서는 레지스트리가 멈추고 사람 확인이 필요하다.

### 롤백

이 작업은 새 파일만 추가했다(1단계·기존 파일 수정 없음). `git revert 65bb1eb552e906657f28281f7f7ee90c657a44da 053dde788e931b021ab3c7957838f8c1291e49dd 9ec67e7b578bd3068e42918d1bccbd048f1410d4 794bbb7b620cc985c34e489b388059a08565acc7`
(또는 harness/{registry,gate,champion,lineage,pointer}.py와 tests/test_harness_champion_*.py 삭제. 지적 반영만 되돌리려면 앞의 두 커밋만 revert)로 되돌린다. 런타임 상태는 호출자가 준 root 아래에만 생기므로
저장소에는 남는 것이 없다.


## 후속 기록 (2026-11-27, 5단계 독립 검증 지적 반영)

- 1단계 `ledger`의 줄 나누기를 `\n`으로만 하도록 고쳤다(5단계 task 문서 "독립 검증 지적 반영"). **`harness/registry.py:77`은 그 수정의 허용 파일 밖이라 `splitlines()`가 남아 있고,**
  U+2028 등이 든 레지스트리는 `registry.load`가 `json.JSONDecodeError`로 실패한다(임시 root에서 재현). 통합 담당 결정 필요.
- **결정 대기:** 철회된 정책의 다른 묶음으로 학습한 모델의 승격(`gate.audit_reason`, `audit.py:127-131`). 설명은 5단계 task 문서의 "결정 대기". 코드는 바꾸지 않았다.

## 후속 기록 (2026-11-27, Silver 정책 철회 보완)

- `champion.promote(root, now, model_id)`는 `audit_status` 인자를 받지 않는다. 승격·복원·철회가 `silver_store.lock → registry.lock` 안에서 같은 적격성 계산
  (`harness/eligibility.py`)을 쓴다. `gate.check`는 구조 조건(가중치·비교 가능성·봉인 층)만 본다. `harness/lineage.py`는 없앴다(계보 무효화 입구는 `withdrawal.withdraw`).
- 위 리스크 "무효 Champion만 남고 복원 후보가 없으면 포인터는 무효 모델을 가리킨 채 남는다"는 사용자 결정 ①로 바뀌었다: 이제 같은 WAL로 "Champion 없음"(대상 None, 사유 clear)으로 전환하고,
  `champion.set_dev_baseline`으로 개발용 Baseline(`registry.load(...)["dev_baseline"]`)을 따로 기록한다. 상세는 [`harness-withdrawal-policy-20261127.md`](harness-withdrawal-policy-20261127.md).
- 위 "후속 기록"의 `registry.py` `splitlines()` 문제는 `c249cac`(줄바꿈 문자로만 나눠 읽기)에서 이미 고쳐졌다.
