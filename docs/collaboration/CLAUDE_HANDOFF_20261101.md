# Claude → Codex 인계 (2026-11-01)

## 한눈에
- 진척률 **42/100**(기준 v1.3). 통과한 항목: C1(후면 엣지 점검 우선순위, 독립 보류 통과). C2(모서리)·C3(표면)·C4(센터링)·C5는 pending. 이번 세션에 점수 변화 없음.
- 기준 변경(사용자 승인 2026-11-01): v1.2 C2(후면 모서리), v1.3 C3(후면 표면)을 "점검 우선순위 제안"으로 재정의. snapshot `artifacts/progress-baseline-20261101/criteria-v1.{1,2,3}.json`. 점수 합 42 검산 완료.
- 모든 변경은 `origin/main`에 푸시됨(최신 `48af643`). 실행 중인 실험·잠금 없음, stash 없음.

## 이번 세션 결과(모두 기록·푸시, 상세는 `docs/collaboration/reports/performance-top3-consensus-20261030.md` §43~§56)
| § | 내용 | 결과 |
|---|---|---|
| 43·45 | 후면 모서리 독립 보류 2회(y·z / aa·ab·ac) | 사전 기준 미충족(격차 하한·적중 하한 미달, AUC 0.75~0.81) |
| 44·46 | 자료 2배 / 크롭 확대 개발 CV | 개선 없음 |
| 47·53 | 후면 표면 독립 보류 / 가장자리 마스크 CV | 미충족(AUC 0.615 / 0.687<0.738) |
| 48·49·51·52 | 라벨 재현성·시대별·확대 11곳 진단 | 시대 이동 가설 약함, 보류 "정상" 라벨 일부 누락 가능, 과경고는 모서리·가장자리 칸에 집중 |
| 50·54 | 후면 엣지 후보 동결(head SHA `4b0412c4…1924`) + 호출 모듈 | 재현 오차 0, 모듈 점수 최대 차 6e-8 |
| 55·56 | 센터링 외형 학습 / 기하 규칙 | 우연 수준(AUC 0.45~0.58) |

## 산출물
- 코드: `card_condition/back_edge_triage.py`(독립 호출, 함수 5개, 호출 경로 1회), 테스트 `tests/test_back_edge_triage.py`·`tests/test_back_edge_triage_guards.py`(통과), 도구 `tools/mobile_surface_label_pages.py`·`mobile_surface_label_import.py`·`mobile_corner_label_pages.py`·`mobile_corner_label_import.py`, 실험 계획·워커 `tools/experiments/<id>/`.
- 동결 head: `artifacts/triage-edge-back-candidate-20261101/head.pt`(force-add). 사용 계약: `docs/collaboration/reports/back-edge-triage-candidate-contract-20261101.md`.
- 제안서: `corner-back-triage-proposal-20261101.md`, `surface-back-triage-proposal-20261101.md`.

## 주의(미커밋·로컬 전용)
- 커밋하지 않은 파일: `tools/mobile_surface_label_pages_v2.py`(취소한 24장 재판정 페이지용 — 사용자가 이미 확대 라벨했다고 해서 폐기 예정, 삭제 가능), `artifacts/surface-v2-20261101/`. 세션 시작 전부터 미추적이던 `docs/collaboration/DATA_INVENTORY_20261028.md`, `tools/corner_review_pages.py`, `tools/ebay_back_edge_review_pages.py`, `tools/ebay_pairing_review_pages.py`는 건드리지 않았다.
- `artifacts/`는 대부분 git 무시 대상이라 라벨 가져오기 결과(`labels-corner-imported.jsonl`, `labels-surface-imported.jsonl` 등)·보류 행·사진은 이 컴퓨터 로컬에만 있다. 계획에 해시로 고정돼 있어 변조는 실행 시 거부된다. 다른 기계에서는 재생성 불가.
- 보류 자료 소진: 후면 엣지 y·z(§41), 모서리 y·z(§43)·aa·ab·ac(§45), 표면 y·z·aa(§47). 같은 후보를 같은 보류로 재평가하지 말 것. 새 후보는 새 독립 보류 필요.
- 이번에 발생한 실수: 테스트 오류 확인 중 `git stash`·`git checkout 2f90ea5 -- .`를 잘못 실행했다가 `git checkout HEAD -- .`로 복구(손실 없음, 푸시본 영향 없음).
- `tests/test_point_dataset.py`는 `python -m unittest tests.test_point_dataset`로는 import 오류(기존 문제: `from test_pipeline import fixture`). `discover -s tests`로는 통과.

## 사용자 선호·원칙(메모 반영)
- 이미 완료한 라벨은 재요청하지 않는다. 사용자는 확대해서 라벨한다.
- 사용자는 새 평가에서 사진 위 구역별 HTML을 원한다(이번엔 일부 생략: 모델 평가 HTML 미갱신).
- 근거 없는 가정 금지, 미확인은 분모 밖, 사람 정답은 모델 오답 이유로 바꾸지 않는다.

## 미결 결정(사용자 판단 필요)
1. 센터링: 접기 vs 정확한 경계 4점·인쇄 틀 4점 사람 표시(규모 큼). 통과해도 +7점뿐(49/100). D2·D3·E2·F1·F2는 C 전체 통과가 선행.
2. C4 범위를 "미지원/보류"로 재정의할지(제품 범위 축소, 새 버전 승인 필요).
3. 모서리·표면은 현 레시피로 독립 평가를 통과하지 못함 → 새 후보 가설과 새 독립 보류가 있을 때만 재시도.

## 롤백
커밋 단위 `git revert`(이번 세션 커밋은 `3e9a70e`~`48af643`, 문서·실험 파일·모듈 추가만 있고 운영 코드·모델 가중치 변경 없음).

## 부작용 점검(Codex가 확인할 목록)
- **공유 파일을 수정한 것(정확히 이것뿐)**: `PROGRESS_CRITERIA.md`, `development-progress.json`(C2·C3 기준 본문, 버전 v1.1→v1.3, history 2건 추가; 점수 42 불변), `docs/collaboration/reports/performance-top3-consensus-20261030.md`(§43~§56 추가만), `back-edge-triage-candidate-contract-20261101.md`·제안서 2건·이 인계 문서(신규). 운영 코드·`card_condition/` 기존 파일·PokeCollector·Gemini fallback·모델 가중치는 수정하지 않았다. 신규 코드는 `card_condition/back_edge_triage.py`와 `tools/` 도구·`tools/experiments/*`뿐.
- **실수로 커밋했다가 되돌린 것**: 커밋 `3c9e94c`에서 `git add docs/collaboration/reports`가 다른 작업의 미추적 초안 `corner-rectify-plan-20261030.md`를 함께 커밋했다. 이후 커밋에서 `git rm --cached`로 추적만 해제했고 파일 자체는 디스크에 그대로 있다(원래 미추적 상태로 복원). 이 파일의 내용은 내가 쓰지 않았고 수정하지 않았다.
- **외부 호출**: eBay 수집 API를 3회(intake aa·ab·ac, PokeCollector의 자격 설정을 읽기 전용으로 사용). Gemini·Codex 호출은 없다. 수집 사진·카탈로그는 `artifacts/ebay-intake-20261101-{aa,ab,ac}/`에만 쓰였고 `data/ebay-learn`에는 새 파일이 없다.
- **공통 실행기·잠금**: `./experiment --plan`으로 실험 9건을 실행(모두 완료, 기록은 `artifacts/experiments/`). `./develop -- true`를 한 번 실행했다(no-op, 모델·소스 수정 없음). 현재 `workspace.lock`에 실행 중 프로세스 없음. `artifacts/development-cycle/latest.json`은 그대로(2026-10-24).
- **저장소 작업**: `git stash`·`git checkout 2f90ea5 -- .`를 잘못 실행했다가 `git checkout HEAD -- .`로 복구(손실 없음). force push·이력 재작성 없음. 푸시는 일반 push만.
- **미커밋(함께 인계, 사용자 결정 2026-11-01: 지우지 않고 Codex에게 넘김)**: `tools/mobile_surface_label_pages_v2.py`, `artifacts/surface-v2-20261101/`(취소한 재라벨 작업용 — 사용자가 이미 확대해 라벨해서 쓰지 않음. 삭제 여부는 Codex 판단, 연결된 코드·라벨 없음). 세션 전부터 미추적인 4개 파일은 손대지 않음.
