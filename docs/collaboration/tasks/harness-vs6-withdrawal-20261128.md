# 하네스 VS6 철회 복구 연결 (B5-1, 2026-11-28)

브랜치 `claude/harness-vs6-withdrawal-20261128`, 분기점 `ab9bf2d`. 합성 root만 썼다. 실제 승격·학습·실험·모델 호출·push·main 통합은 하지 않았다.

## 목표와 결함
- 결함(R/verify-b924753.md 중요 ①): 철회가 `policy_withdrawn` 기록 직후 kill되면, 포인터가 철회된 모델을 계속 가리킨다. 이때 `read_current`가 `valid=True`를 낸다. 복구 함수 `withdrawal.withdraw(root, now)`를 부르는 곳이 없었다.
- 정책 원문(policy-final.md 5줄): "무효 모델을 Champion 포인터가 계속 가리켜서는 안 된다." 또 25줄에 따라 처리 도중 kill 뒤에도 복구할 수 있어야 한다.
- 새 정책은 만들지 않았다. 자동 재적격 경로도 없다. 기존 `withdraw`의 복구 전용 호출(`policy_id=None`)만 연결했다.

## 커밋
- `5ebb01e` feat(harness): Supervisor 회차 앞 끊긴 Silver 철회 복구 연결(B5-1, VS6, 합성)
- `5b3aeef` test(harness): 복구 시험 도우미 분리(파일당 함수 ≤7, 동작 불변)
- (이 문서 커밋)

## 변경
- `harness/supervisor.py`(+6/−3)
  - `run`은 회차마다 정지 확인(`_live`) 직후에 `withdrawal.withdraw(root, now)`를 직접 부른다. 순서는 그래프 등록·Python·Claude보다 앞이다.
  - 조건은 `silver/store.jsonl`이 있을 때만이다. 저장소가 없으면 철회도 있을 수 없다. 조건 없이 부르면 빈 root에 `models/`·`silver/` 잠금 폴더가 생긴다.
  - 결과는 요약 `summary["withdrawal"]`(진입점 stdout JSON)에 남는다.
  - 장부 변조(StoreError·RegistryError)와 CAS 손상(ChampionError)은 새 코드로 처리하지 않는다. 기존 `except Exception`이 받아 INTEGRITY_HALT와 알림으로 올린다.
- `tests/test_harness_b5_recover.py`(새 파일, 시험 5개)와 `tests/harness_recover_kit.py`(새 공용 도구, 시험 없음)

## 증거 연결(C): 합성 root에서 실제 진입점 실행
- 스크립트: `<SP>/vs6_c_evidence.py`. 로그: `<SP>/vs6_c_evidence.log`. 여기서 SP는 이번 세션 scratchpad다.
- 준비: 장면 CLEAR(Champion m1을 legacy로 승격)를 만들고, 수동 철회 `batch_label_error [b1]`을 `after:policy_withdrawn:1`에서 SIGKILL로 죽였다.
- 복구 전: `read_current`가 m1(`6b953e…`)을 `valid=true`로 읽었다. 파생 계산으로는 무효다(결함 재현).
- `python -m harness.supervisor --root R --max-cycles 1 --poll 0`의 결과는 exit 0이다. stdout `withdrawal`은 다음과 같다.
  - `invalidated`: [m1, c1]
  - `restore`: `{cleared: true, reason: no_verified_champion, restored_from: m1}`
- 장부에 남은 줄
  - registry: `invalidated`(seq 10), `switch_intent`(seq 11, clear), `switched`(seq 12)
  - ledger.jsonl: `lineage_invalidated`(seq 2), `champion_cleared`(seq 3)
- 복구 뒤 `read_current`는 `null`이다(Champion 없음).
- 2회차: `invalidated: []`, `restore: null`. 장부 줄 수(registry, ledger.jsonl)는 (13, 4)에서 (13, 4)로 그대로다(멱등).
- 이것은 합성 root의 연결 증거다. 실환경 동작·launchd 활성화·모델 성능은 주장하지 않는다.

## 시험
- `test_kill_at_every_write_then_one_entry_cycle_recovers_and_repeats_are_no_ops`
  - 대상 장면 세 가지: 수동 철회로 base 복원, 수동 철회로 Champion 없음, 감사 실패 자동 철회로 base 복원.
  - 끊김 없는 실행이 지나간 모든 쓰기 지점마다 실제 SIGKILL을 넣고, 진입점 1회차를 돌렸다.
  - 확인 내용
    - 무효 모델이 유효로 읽히지 않는다.
    - 수동 철회는 끊김 없는 결과와 같다. 시작 기록 전에 kill된 경우는 아무 변화가 없다.
    - 2회차는 root 전체(Supervisor 폴더 제외)가 한 바이트도 바뀌지 않는다.
    - 복구 전에는 유효로 읽히는 지점이 실제로 있었다(결함 재현 단언).
- `test_tampered_ledgers_fail_closed_without_writes`
  - Silver 저장소나 레지스트리의 첫 줄 ts를 해시 재계산 없이 바꿨다.
  - 결과: 1·2회차 모두 INTEGRITY_HALT다. silver/·models/·포인터·가중치에는 쓰기가 없다. 주 장부에는 `opstate_transition`만 더해진다.
- `test_halting_states_do_not_recover_until_cleared`
  - 4개 정지 상태 각각에서 root에 쓰기가 0이고, 요약에 `withdrawal`이 없다.
  - 정지 중에는 결함이 남는다(m1이 유효로 읽힘). 이 틈을 단언으로 고정했다.
  - USER_STOPPED를 사람 해제(시험이 `clear_by_user`를 직접 불러 흉내 냄)한 뒤 첫 회차에서 복구된다.
- `test_roots_without_a_silver_store_get_no_side_effects`
  - 빈 root: Supervisor 폴더 밖에 파일이 0이다.
  - 대조(pre-b5 확인 동작): 조건 없이 `withdraw`를 부르면 `models`·`silver` 폴더가 생긴다.
  - Silver 없이 Champion만 있는 root: 파일 바이트가 그대로다.
- `test_recovery_runs_before_graph_and_python_and_keeps_depth`
  - 호출 순서는 withdraw → graph.register_missing → _python이고, 그래프·Python 시점에는 이미 복구돼 있다.
  - `supervisor.run` 깊이는 4 이하이고 래퍼 없이 직접 부른다.
- 변이 5종(`<SP>/vs6_mut.py`)은 모두 잡혔다: 조건 제거, 정지 확인보다 앞, 예외 삼킴, Python 뒤로 이동, 호출 삭제.
- 관련 모듈 시험
  - `test_harness_supervisor_*` 47개 OK
  - `test_harness_withdrawal_*` 20개 OK
  - `test_harness_b5_*` 33개 OK
- 전체 시험 결과(아래 "전체 시험" 절)

## 구조
- `harness/supervisor.py`의 함수 수는 4에서 4로 그대로다.
- `supervisor.run`의 최장 경로는 4다. 기존 경로는 `claude_job.execute`를 지난다.
- 새 경로 `run → withdrawal.withdraw → champion.restore_locked → cas.get → cas.blob_path`도 4다. AST 측정 도구는 `tests/harness_depth_kit.py`다.
- 시험 파일의 함수 수는 lambda를 포함해 7 이하다. `tests/test_harness_b5_recover.py`는 5개(시험 메서드)다. `tests/harness_recover_kit.py`도 5개(call_for·interrupted·tree·stale·entry)다.

## 사용자 확인 필요
1. **정지 상태 중 복구 여부.** 지금은 4개 정지 상태(INTEGRITY_HALT·USER_STOPPED·DONE·BUDGET_EXCEEDED) 모두에서 복구하지 않는다.
   - 근거: supervisor 기존 계약("정지 상태면 아무 작업도 시작하지 않고 감시만")과 사용자 제어권(완화 금지)이다. pre-b5 결정 9의 보수 쪽인 (나) "모든 반영 정지"와도 맞춘 것이다.
   - 대가: 정지 중에는 끊긴 철회의 Champion이 `valid=True`로 읽힌다. 다만 그 동안에도 승격·복원 후보 계산은 eligibility 파생 계산이 막는다(기존 kill 시험).
   - 대안: pre-b5 3절 단계 1의 제안안이다. INTEGRITY_HALT만 제외하고 다른 정지 상태에서는 복구를 허용한다. 복구는 개발 작업 시작이 아니라는 해석이다.
2. **읽기 시점 보장(pre-b5 결정 4).** 지금은 (가) 단계 1만 적용했다. Supervisor 회차 사이(최대 poll 간격, 기본 60초)와 Supervisor가 꺼져 있는 동안에는 `read_current`가 여전히 `valid=True`를 낼 수 있다. (나)는 `pointer.current`가 파생 무효를 보게 하는 안이다. 이번 범위 밖이라 하지 않았다.
3. CAS 손상으로 복원이 실패하면(ChampionError) 기존 except가 INTEGRITY_HALT로 올린다. 이 경우 포인터는 무효 모델에 머물고 사람 확인을 기다린다. 이 기본값을 유지할지 확인이 필요하다.

## 한계·미검증
- 실제 launchd 상시 실행, 실데이터 Silver·레지스트리, 장시간 경합은 확인하지 않았다. 확인한 것은 합성 root와 1~2회차뿐이다.
- 매 회차 Silver·레지스트리 잠금을 잡고 두 장부를 전부 읽는다. 장부가 커지면 회차 비용이 늘 수 있다(측정하지 않음).
- `withdraw`의 잠금은 기다림 제한 없는 flock이다. 다른 프로세스가 잠금을 오래 쥐면 그 회차가 기다린다. 정지 확인과 `withdraw` 사이에 건 정지는 그 복구 1회를 막지 못한다. supervisor 3단계 문서의 확인과 사용 사이 경합과 같은 종류다.
- 복구 결과는 진입점 stdout과 기존 장부 줄에만 남는다. 복구 전용 알림(`opstate.notify`)은 추가하지 않았다(운영 뒤 개선 후보).
- registry `invalidated` 직후 kill하면 주 장부 `lineage_invalidated`가 영구히 빠지는 문제(verify-b924753 경미)는 고치지 않았다. 범위 밖이다.
- runner.py·budget.py·experiment_exec.py는 VS2 담당이라 수정하지 않았다. 적용기(B5-7) 쪽에서 `withdraw`를 부르는 경로는 이번 시험 대상이 아니다.
- 정확도 변화는 없다. 이번 작업은 합성 시험이며 모델의 결함 누락·오탐에 대한 근거가 아니다.

## 롤백
- `git revert <문서 커밋> 5b3aeef 5ebb01e`. 바뀌는 것은 supervisor.py 6줄, 새 시험·도구 파일 2개, 이 문서뿐이며 데이터 이전은 없다.
