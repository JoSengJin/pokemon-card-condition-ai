# 평가 지표 이웃 모듈 계약 검증 (Codex 공백 중 Claude 수행)

- task_id: `metrics-neighbors-contract-20261025`
- owner: Claude (Codex 토큰 한도 동안 임시 수행)
- status: integrated
- base_sha: `21809d54cf4d0f7d24ddcec1566ef48a407412cb` (main)
- branch: `claude/metrics-neighbors-contract-20261025`
- allowed_files: `tests/test_threshold_contract.py`, `tests/test_paired_miss_contract.py`, 이 문서, `docs/collaboration/prompts/codex-resume-20261025.md`, `docs/collaboration/reports/metrics-neighbors-contract-20261025.md`, `docs/collaboration/reports/metrics-neighbors-contract-20261025.html`
- forbidden_files: 모든 `card_condition/` 소스(읽기 전용), cross-review 계열 전체(Codex 진행 범위), 모델·worker·실험·라벨·진척 기준·관제 파일.

## 범위

직전 평가 지표 묶음의 이웃인 `region_thresholds.py`(임계값 스윕·실물 가중)와 `defect_regressions.py`(쌍별 누락 전이)를 손계산으로 검증한다. 새 기능·지표는 만들지 않는다. 학습·추론·실자료·외부 AI·라벨 요청·main 통합·push는 하지 않는다. 모델 성능은 평가하지 않는다.

## 결과

- 소스 결함은 재현되지 않았다. 두 소스는 base와 동일(diff 0)이며 회귀 검사만 추가했다.
- 신규 테스트 7개(함수 정의 5·5), 기존 관련 5개와 함께 `PYTHONPATH=tests .venv/bin/python -m unittest test_threshold_contract test_paired_miss_contract test_region_thresholds test_defect_regressions` 12개 통과.
- 복제 mutation 8개 중 7개가 처음부터 검출됐다. 살아남은 1개(다른 종류의 false positive를 reference 쪽에서 세는 변형)는 검사 빈틈이어서 보강했고, 보강 후 검출된다.
- `listing_readiness`는 `regions → data → torch`를 import해 torch 없는 이 환경에서 확인하지 못했다(미검증).


## Codex 인수

고정7커밋을 로컬 main에 통합한 뒤 지정12검사와 listing_readiness5검사를 직접 실행해 통과했다. source diff0·정의5/5·diff검사 통과. 상세는 보고서 Codex 인수 절과 artifacts/codex-resume-20261025/. 현재 채택본4604d1ef…유지, 후보복원/채택 결정 대기. 새 개발·학습·모델 추론·외부 AI·원격 push 없음. 성과·인수 HTML 갱신 후 열기.
