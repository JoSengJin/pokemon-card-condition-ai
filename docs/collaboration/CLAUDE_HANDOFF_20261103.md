# Claude → Codex 인계 (2026-11-03)

기준 시점: origin/main = 로컬 HEAD = `2736c1fc4d97e21f41896ba64cbdcb14455a48d4`(확인 시점 일치). 작업 트리 깨끗, stash 없음, 실행 중인 실험·잠금 없음(수집은 중단함). 이전 인계는 `CLAUDE_HANDOFF_20261101.md`(진척 42점, 지금은 낡았다).

## 한눈에
- 진척률 **63/100**(기준 **v1.10**, `PROGRESS_CRITERIA.md`·`development-progress.json`, rubric_sha256 `2dd4db1ff6aa65fb1674f413109657af5d2c155eb1a07bb7c3b79003ca60636a`). 11-01 인계 때 42점 → C2·C3·C5가 각각 독립 보류 평가를 통과해 +21.
- verified: C1(후면 엣지) C2(후면 모서리, 후보 E, §72) C3(후면 표면, 후보 B, §68) C5(후면 관찰 제한, 후보 F, §79). pending: **C4(센터링)**. D·E2·F는 문서상 C 전체 통과가 선행(확인 필요).
- 모두 "점검 우선순위/재촬영 권고" 용도만이며 결함·제한 확정이나 FN≤5%·FP≤10% 주장 아님. 앞면은 C1~C3·C5 모두 미지원.

## 기준 변경 이력(사용자 승인, 각 snapshot은 `artifacts/progress-baseline-20261102/criteria-v1.{4..10}.json`)
v1.4 C3 후보 B 교체 / v1.5 C3 격차 기준 완화 / v1.6 C2 격차 완화 / v1.7 C2 후보 E / v1.8 C5 후면 우선순위 재정의 / v1.9 C4 앞면 상하 우선순위 재정의 / v1.10 C5 후보 F(267면 학습). 배점·다른 항목·수치는 각 변경에서 불변이고 결과를 본 뒤 기준을 바꾼 경우(v1.5·v1.6·v1.10)는 그 사실과 이전 자료를 증거에서 제외한 것을 기준 본문에 명시했다.

## 이번 세션 결과(상세는 `docs/collaboration/reports/performance-top3-consensus-20261030.md` §65~§79)
| § | 내용 | 결과 |
|---|---|---|
| 65~67,69 | 표면 후보 B 추가 보류·자료 +50%·layer-8·마지막 2블록 미세조정 | 미충족/개선 없음 |
| 68 | C3 새 보류(aj·ak·al) | 충족(격차 0.363) |
| 70~72 | C2 §43 후보 실패 → 같은 사진 쌍 순위 항(후보 E) 개발 CV 충족 → 새 보류(am·an·ao) | 충족(격차 0.544) |
| 73 | C5 v1.8 첫 보류(후면 120, 제한 39, 개발 147 학습) | **미충족** AUC 0.696[0.595,0.798] |
| 74~76 | 센터링 사람 8점 표시 시범: 뒷면 신호 없음, 앞면 상하 비대칭 AUC 0.806→재확인 0.845(사전 기준 충족) | 사람 표시 값이며 제품 신호 아님 |
| 77 | 자동 상하 테두리 측정기 규칙 2종 | 실패(Spearman −0.03·0.08, 라벨 AUC 0.43·0.56) |
| 78 | C5 화질 통계 8개 추가 | 미채택(Δ −0.007). 자료원 분해 실험은 구현 오류 있음(아래) |
| 79 | C5 v1.10 후보 F 새 보류(ap~aw 후면 101, 제한 26) | **충족** AUC 0.792[0.681,0.886] |

## 정직하게 기록할 실수·미검증
1. **§78 자료원 분해 실험(`20261102T225059-98b83ef4`)**: 워커가 ID 접두 `ebay-pair-`로 구분해 계획의 "eBay 120면" 대신 221면으로 계산했다. 기록의 `criterion_met=true`는 잘못된 분모의 결과라 가설 검증으로 쓰지 않았다(문서에 명시). 사후로 저장 점수에서 120면만 골라 0.785를 얻었으나 확증 아님.
2. **v1.5 첫 커밋의 rubric 해시 오류**: 평가 상태 필드까지 해시에 넣었다가 본문만으로 재계산해 수정(§68에 공개).
3. **실패한 첫 실행 3건**(모델 실행 전 실패, 성능 수치 없음): `20261102T103444-ec2316a1`(가설 ID 검사식 오류, r2로 재실행) `20261102T215710-f9160113`(계획에 `input_sha256` 누락) 그리고 C5 계획 재작성 중 §57과 다른 풀링(평균+표준편차)을 쓴 초안은 실행 전에 평균 풀링으로 고침.
4. **원치 않은 파일을 커밋**: `git add docs`/`git add tools`가 세션 전부터 미추적이던 다른 작업 파일 6개를 함께 커밋했다(내용 수정 없음). `docs/collaboration/DATA_INVENTORY_20261028.md`·`docs/collaboration/reports/corner-rectify-plan-20261030.md`(커밋 `b2fcf08`), `tools/corner_review_pages.py`·`tools/ebay_back_edge_review_pages.py`·`tools/ebay_pairing_review_pages.py`·`tools/mobile_surface_label_pages_v2.py`(커밋 `f0fa847`). 이 중 `ebay_pairing_review_pages.py`는 내가 실제 사용했다. 나머지가 의도치 않았다면 `git rm --cached` 후 새 커밋으로 추적 해제(force push 불필요).
5. 센터링 8점 표시·§74~§76과 C5 자료원 사후 산출은 **공통 실험 기록(`./experiment`)을 쓰지 않은 진단**이다. 측정기 §77과 C5 H1·F 평가는 `./experiment`로 실행했다.
6. 보류 후면의 카드 상자는 사람 확인 전 자동 제안(`box_reviewed=false`)이다. 개발 147장은 사람 확인 상자라 입력 조건이 다르다.
7. C5 보류 계획을 101장으로 동결한 뒤 답이 오지 않은 5쌍(`580ff960…`·`ab77b6ca…`·`881a86c8…`·`609bfbed…`·`e0eb5f16…`)은 추가하지 않았다. 미확인 2장은 분모 밖.
8. 공통 실행기는 독립성을 인증하지 않아 모든 계획이 `independent=false`이며 격리는 수집 때 `HOLDOUT.md`로 선언했다.

## 산출물 위치
- 코드(구조 기준 확인: 파일당 함수 수 ≤7, 호출 깊이 ≤4 눈으로 확인, 정적 검사 도구는 쓰지 않음): `tools/mobile_visibility_label_pages.py`(3) `tools/obslimit_holdout_rows.py`(2) `tools/obslimit_report_html.py`(1) `tools/mobile_centering_mark_pages.py`(5) `tools/centering_mark_analysis.py`(6) `tools/centering_mark_report_html.py`(2) `tools/centering_measurer_report_html.py`(2), 실험 워커 `tools/experiments/{obslimit-back-holdout-20261103, obslimit-back-holdout-f-20261103, obslimit-quality-feat-20261103, obslimit-pooled-source-20261103, centering-tb-measurer-20261103, centering-tb-measurer-v2-20261103}` 및 `artifacts/` 미러.
- 운영 코드(`card_condition/`), PokeCollector, Gemini fallback, 모델 가중치는 수정하지 않았다. 신규 `card_condition` 모듈 없음(후면 엣지 모듈은 11-01 것 그대로).
- 사진 위 HTML(전달 완료): `artifacts/obslimit-holdout-f-20261103/report.html`(C5 충족) `artifacts/obslimit-back-holdout-20261103/report.html`(C5 v1.8 미충족) `.../report-pooled-oof.html` `artifacts/centering-marks-20261103/report{,-front,-front-rep}.html` `artifacts/centering-tb-measurer-20261103/report-v2.html`. 열기: `SendUserFile`로 사용자에게 전달했고 브라우저 렌더 확인은 하지 않았다(파일 열기 차단).
- 실험 기록: `artifacts/experiments/20261102T{214…}` 목록은 `ls artifacts/experiments | sort | tail -12`; 이번 판정 근거 `20261102T233115-f405c24a`(C5 F), `20261102T145448-7876bfd4`(C2 E), `20261102T215718-870c2647`(C5 v1.8 미충족).

## 외부 호출·로컬 전용 자료
- eBay 수집 API(수집 전용, PokeCollector 자격 읽기 전용): intake ag~ao(11-02), ap~aw 사용 + ax(30건 수집만, 미사용)·ay(중단, 비어 있음)(11-03). Gemini·Codex 호출 없음.
- `artifacts/`는 대부분 git 무시 대상이라 사진·라벨 답·review jsonl은 이 컴퓨터에만 있다. 계획은 해시로 고정되어 변조는 실행 시 거부된다. 일부 파일은 `git add -f`로 올렸다(plan·worker·행 JSON·HTML·답).
- 소비된 보류(재사용 금지): 후면 엣지 y·z, 모서리 y·z·aa·ab·ac·aj·ak·al·am·an·ao, 표면 y·z·aa·ag~ao, C5 aj~ao(v1.8, 이후 후보 F 학습에 편입)·ap~aw(v1.10 평가 완료). 새 후보는 새 독립 보류가 필요하다.

## 미결 결정(사용자 판단 필요)
1. **C4 센터링**: (a) 미지원으로 재정의(7점 포기) (b) 앞면 ≥150장 사람 표시로 학습형 측정기. 사람 표시는 앞면 상하 비대칭이 사람 라벨과 관련 있음(§75·§76)을 보였지만 규칙 측정기는 사람 표시를 재현하지 못했다(§77).
2. **D·E2·F 선행 조건 확인 결과(기준 문서 v1.10 본문, 2026-11-03)**: D1(시험셋 동결, 5점)은 C 통과를 요구하지 않는다 — 각질문/앞뒤별 양성·정상 각 30실물 이상의 미사용 시험 manifest를 선택 전에 봉인. D2(5점)는 "C의 전범위 수치조건을 모두 통과"라서 C4 선행. D3(5점)는 실물 단위 누락·오탐 사건률의 단측 Wilson 상한(10%·20%)이라 판정형 FN/FP가 필요한데 C1~C3·C5는 점검 우선순위로 재정의돼 이 지표를 낼 수 없다(기준 해석·개정 필요). E2(5점)는 센터링 포함 통합 시나리오, F1·F2(각 5점)는 통과 후보 필요. 따라서 C4를 풀지 않으면 도달 가능한 추가 점수는 D1의 +5(최대 68점)뿐이다. D1의 "각질문/앞뒤별" 범위가 미지원 칸(앞면 등)을 포함하는지는 기준에 명시돼 있지 않아 사용자 해석이 필요하다.

## 롤백
커밋 단위 `git revert`. 이번 세션(2026-11-02~03) 커밋은 약 55개, 첫 커밋 `236a67d`~`2736c1f`(+이 인계 문서 커밋). 기준만 되돌리려면 `development-progress.json`·`PROGRESS_CRITERIA.md`를 해당 버전 스냅샷(`artifacts/progress-baseline-20261102/criteria-v1.N.json`)과 대조해 revert. 운영 코드 변경은 없다.
