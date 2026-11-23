# 모서리 오탐·누락 감소 후보 3개 병렬 개발 (2026-11-24)

사용자 지시(이 세션 채팅): 오탐·누락을 줄일 개발 항목을 Superpowers를 활용해 선정하고 Sonnet 5.5로 병렬 개발. **개발과 합성 검증까지만이다. 실제 학습·추론·점수 열람·`./experiment` 실행·통합·push는 포함하지 않는다.**

- owner: Claude 하위 에이전트(Sonnet) 3, 통합 검토 이 세션. status: ready_for_review (미통합). base_sha: 이 계약 커밋. worktree: 에이전트마다 격리(경로 미커밋).
- 공통 허용 파일: 자기 폴더 `tools/experiments/<task_id>/{transform.py,worker.py,plan.json}`와 `tests/test_<module>.py` 하나뿐. 다른 파일·기존 실험·`card_condition/`·라벨·봉인 자료·`artifacts/` 쓰기 금지.
- 대조(공통): 저장된 네 배치 평균 개발 OOF `artifacts/experiments/20261121T050740-8588eeb0`(942구역, 결함 카드 175 중 놓침 5, 정상 카드 81 중 잘못 표시 9, 오탐 10장 맞춤 놓침 42, 같은 사진 AUC 0.81769). 정답은 v1, 독립 자료 아님.
- 사전 기준(공통, 모두 충족해야 성공): 고정 작동점 잘못 표시 ≤7/81, 놓침 ≤5/175이고 새 놓침 0, 오탐 10장 맞춤 놓침 ≤42/175, 같은 사진 AUC 하락 ≤0.01. 하나라도 어긋나면 미채택.
- 구조: 파일당 함수 ≤7, 저장소 함수 호출 깊이 ≤4. 봉인 468·독립 350 미사용, 외부 호출 0.
- checks: 새 합성 테스트, `git diff --check`, 허용 파일 대조. handoff: 커밋 SHA·변경 파일·구조·검사 명령과 종료 코드·미검증·위험·롤백.

| task_id | 바꾸는 변수 하나 | 근거 |
|---|---|---|
| corner-coverage-mask-20261124 | 점수 계산의 유효 패치 조건을 "크기 조정 여백이 아닌 사진 픽셀이 하나라도"에서 "절반 이상"으로. 학습 0 | 오탐 최고점이 여백 패치(64.3% 여백)나 카드 바깥 경계에 놓인 사례 |
| corner-canonical-orientation-20261124 | 네 모서리를 같은 방향(왼쪽 위)으로 뒤집어 학습·채점 | 946구역 선형 head가 네 방향을 따로 배워야 함. 모서리 자료에서 미시험 |
| corner-phase-train-20261124 | 학습 입력을 무이동 1배치에서 (0,0)·(7,7) 2배치로 | 채점 때 배치 평균은 개발에서 오탐 16→9·놓침 8→5. 학습 쪽은 미시험 |

## 인계와 검토 (2026-11-24, 개발만. 실제 학습·추론·점수 열람·통합·push 없음)
| task_id | branch | SHA | 함수 수 transform/worker/테스트 |
|---|---|---|---|
| corner-coverage-mask-20261124 | claude/corner-coverage-mask-20261124 | `403ffed095013f7b8176f1531c50e8acc4ae2f18` | 1/6/7 |
| corner-canonical-orientation-20261124 | claude/corner-canonical-orientation-20261124 | `e66f5fb2844bde859045bb2dda566cbda92313df` | 1/7/7 |
| corner-phase-train-20261124 | claude/corner-phase-train-20261124 | `73b8048c23e05815fcd219197c30998c07994eb3` | 2/7/6 |

- 검토 세션이 다시 실행: 세 테스트 파일 5·5·4개 `-W error` 종료 0(두 배치 학습의 실제 head 사슬 검사 포함, 건너뜀 없음), `git diff --check` 0, 허용 파일만 변경. 기본 checkout의 모듈로 worker import, 계획의 입력 SHA 전부 일치, 여백 후보는 가짜 백본으로 채점 함수 실행.
- 검토에서 고친 것: 방향 통일 worker의 없는 키 `ref['scores']`와 CPU 대체(장치 변수 추가). 방향 통일 에이전트는 구조 확인용으로 `result.json`의 `comparison` 키를 한 번 출력했다고 보고(계약 위반, 후보 설계에는 쓰지 않았다고 보고; 독립 확인 안 함).
- 실행 전에 남은 것: `artifacts/<task_id>/` 미러 배치(여백·방향 통일의 code_changes 경로), 두 배치 학습은 fold당 float64 약 4.8GB에 중심화 복사본이 더해져 16GB에서 메모리가 부족할 수 있음. 실제 실행·계획 스키마 검사·호출 깊이 도구 검사 미실행.
- 롤백: 통합 전이므로 세 브랜치를 쓰지 않으면 된다.
