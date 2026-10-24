# Claude 인수인계 — 독립 카드 상태 AI, 2026-10-24 KST

> 2026-10-25 이후 Git 협업 방식은 [PAIR_CODING.md](PAIR_CODING.md)를 따른다. 아래 역할 배분과 실험 상태는 당시 인계 기록이며, 현재 배정 task·최신 실행 기록을 대신하지 않는다. 이 문서만으로 기본 checkout 편집이나 과거 실험 재개를 시작하지 않는다.

## 1. 이번 역할과 소유권

작업 루트는 `.`이다. Claude는 아래 캐시 불일치 진단과 그 근거에 따른 단일 개선 실험의 구현 담당이다. Codex는 이번 인계 후 이 영역을 병행 구현하지 않으며, 사용자가 결과 검토를 요청하면 읽기 전용 리뷰를 맡는다. 이 역할 배분은 에이전트 간 자동 통신이나 영구 잠금이 아니다. 역할을 바꾸거나 공유 소스를 수정하기 전에 현재 작성자를 확인한다. 동시에 같은 파일/학습을 두 에이전트가 수정·실행하지 않는다.

Claude 신규 작업은 `artifacts/claude-block8-cache-audit-20261024/`부터 시작한다. 기존 worker/계획/결과/사람 라벨은 그대로 보존한다. 기존 worker를 고쳐 같은 실패를 재실행하지 말고, 진단·수정 근거와 새 가설 ID를 가진 새 파일을 사용한다. 공용 모델·실행기·라벨 UI·수집기·자동 토론 코드를 일괄 리팩터링하지 않는다.

소스/worker 편집은 반드시 `./develop -- <수정 명령>`의 원자적 잠금 안에서 한다. `./develop --check` 후 별도 편집은 잠금을 소유한 편집이 아니다. 성능/학습/모델 진단은 `./experiment --plan <계획.json> -- .venv/bin/python <worker.py>`로만 실행한다. 잠금이 사용 중이면 그 실행과 충돌하지 말고 종료 기록을 확인한다. 잠금 파일을 삭제하지 않는다. 실험 반환 후 `artifacts/development-cycle/latest.json`과 참조 handoff를 읽기 전 다른 개발 명령을 시작하지 않는다.

인계 시 읽기 전용 잠금 점검에서는 비어 있었다. 전체 프로세스 목록은 실행 환경 권한으로 조회하지 못했으므로 모든 프로세스가 종료됐다고 주장하지 않는다. 이후 실행 시점의 잠금은 다시 원자적으로 획득해야 한다. 이번 인계 턴에서는 문서만 추가하고 모델·worker·라벨·운영 코드를 수정/실행하지 않았다.

## 2. 먼저 읽을 문서

아래 경로는 작업 루트 기준이다.
- `AGENTS.md`: 사람 정답/unknown 보존, 잠금, 공통 기록, 검증·보고 계약.
- `COMMON_EXPERIMENT_RECORDS.md`: 실험 계획/worker observations/실제점 guard/필수 회귀/상태 계약.
- `OBSERVATION_CONSENSUS_20261011.md`: 한 번에 변수 하나, 입력 근거/촬영 제한과 결함 구분, 사후 임계값 탐색 금지.
- `${POKECOLLECTOR_ROOT}/CONDITION_ANALYSIS_TODO.md`: 상단 실행 순서와 과거 실패 근거. 소비 프로젝트 운영 소스를 변경하지 않는다.
- `artifacts/charmander-exact-test-20261023/REPORT.md`: 직전 완료된 실제점 진단/단일 손실 대조, 리스크/롤백.
- `artifacts/development-cycle/latest.json` 및 참조 `development_handoff.json`: 최신 상태. 이 문서와 다르면 원본 최신 기록을 우선하고 차이를 기록한다.

현재 열려 있는 `artifacts/charmander-exact-test-20261023/index.html`은 마지막으로 완성한 성과 HTML이다. 이후 B 정상 답변 평가·좌우 반전 진단·중간층 실행 실패는 아직 이 HTML에 추가되지 않았다. 오래된 화면을 최신 결과라고 소개하지 않는다.

## 3. 전체 프로젝트와 현재 연구 경로를 구분

독립 카드 상태 분석 프로젝트이며 수집/라벨 UI/단독 추론·실험 도구가 있다. 현재 인계하는 좁은 경로는 **뒷면 미세 엣지 마모** 연구다. 표면/모서리/센터링/관찰 제한 전체가 같은 모델로 해결된 상태가 아니다.

이 경로는 고정 DINOv2 vits14, 입력448, 14px 패치, 32×32개 384차원 특징과 선형 head를 쓴다. 현재74행은 74장의 독립 실물이 아니라 정상/손상 구간·사람점 행이다. 정확한 양성점과 약한 구간 존재 감독을 구별하며, 사람이 확인하지 않은 양성 사진의 다른 픽셀을 음성으로 만들지 않는다. 기존 normal max_bound 손실, L2=1, 임계값0.5, 그룹·클래스 가중치, 기존3fold를 유지해 단일 가설을 검증한다.

`card_condition/point_patch_head.py`, `card_condition/dino_wear_lora.py::point_token_index`, `card_condition/side_experiment.py::prepared_image/view_tensors`, `card_condition/local_wear_cnn.py::physical_pixel_mask`가 관련 구현이다. 실제 학습 helper는 `artifacts/inner-whitening-confounder-20261021/confounder_head.py`다. 소스/계획/실행 worker를 직접 대조하고 이름만 보고 추정하지 않는다.

정답 기준: 바깥 끝선 손상=엣지, 둥근 모서리=모서리, 안쪽 인쇄면의 화이트닝·오염·기스=표면. 원인(제조/사용 마모)과 관찰된 손상 유무는 별개다. 반사·가림·흐림은 관찰 제한이고 손상 자체가 아니다.

## 4. 실제 유지 기준과 미해결 품질

유지 중인 **연구 대조군74**:
`artifacts/experiments/20261022T154044-9fe16ae3/`
- 같은 개발26구간: 정상 오탐2/22(9.09%), 결함 구간 누락0/4, 실제 사람점 누락0/4.
- 필수 알려진 회귀3구간: 오탐1/1, 누락1/2로 최종 acceptance_passed=false.
- 따라서 이것도 품질 전체를 통과한 운영 채택 모델이 아니다. 전체 제품 진척률67%나 일반 정확도로 환산하지 않는다.

정확점76 후보:
`artifacts/experiments/20261022T210245-0ccf2afd/`
- 같은26에서 오탐3/22, 구간 누락0/4, 실제점 누락1/4로 미채택.
- 구간에 경고가 있어도 실제 마모점을 놓치면 통과시키지 않는다.

공통 성공 기준을 약화하지 않는다: 주평가 FP≤2/22, 구간 FN0/4, 실제점 FN0/4, 기존 대비 새 오류 없음; 필수 회귀 FP0/1·FN0/2까지 모두 통과하고 실제 개선도 있어야 한다. 실행 completed는 성공/향상을 뜻하지 않는다. 개발 평가 반복에 따른 선택 편향이 있으므로 별도 독립 평가 없이 일반화 개선이라고 하지 않는다.

## 5. 최신 확정 사람 정답과 새로 확인한 문제

같은 파이리 뒷면 `ebay-pair-4a2997a87ea591`:
- 왼쪽 중간 짧은 바깥 끝선: 엣지 손상 확정. 실제26점 저장→21개 유효 토큰. 모두 입력 마스크 안인데 두 고정 모델 모두21/21 토큰을 놓쳤다. 동일 사진의 연속점이므로 독립21개 결함/실물이 아니다.
- 오른쪽 중간 B의 짧은 바깥 끝선: 사용자 **정상** 확정. 다른 구역/표면/모서리 정상으로 확대하지 않는다. ID에 `unconfirmed`가 남아 있어도 최신 human-truth target=0을 읽는다.
- 두 구간과 저장 좌표는 **test 전용·학습 금지**다. 잠만보의 시험 구간도 학습에 넣지 않는다. 완료한 사람 라벨/좌표는 다시 요청하지 않는다.

실제 점수(경고 기준0.5):
| 같은 사진의 구간 | 연구74 | 기존정확76 |
|---|---:|---:|
| 왼쪽 실제 손상 | .201404, 누락 | .215157, 누락 |
| 오른쪽 B 정상 | .767167, 오탐 | .680518, 오탐 |

한 사진 안에서도 정상/손상 순위가 거꾸로다. 임계값을 낮추는 것으로 이 두 구간을 동시에 올바르게 분리할 수 없다.
- B 최초 평가: `artifacts/experiments/20261023T122121-bf9570a2/record.json`, completed. 정답/사전 동결: `artifacts/charmander-matched-normal-20261023/human-truth.json`, `artifacts/charmander-exact-test-20261023/right-edge-before-truth.json`.
- 좌우 반전 대조: `artifacts/experiments/20261023T122255-24592f38/mirror.json`, record completed. 2구간×2모델 네 판정 모두 반전 후에도 동일하게 틀렸다. 단순한 좌우 방향 탓이라는 가설은 지지되지 않았다. 배경·특징·head 중 주원인을 확정한 것은 아니다.
- 직전 학습 적합도 진단: `artifacts/experiments/20261023T121028-6e297840/diagnostics.json`. 기존74의 학습 정상 bag 오탐은 fold별0/22·0/28·0/18, 실제 양성점 누락1/37·0/35·1/37, 약한 존재감독 각0/5. 학습을 거의 맞혀도 새 사진에서 실패한다. 이 수치를 독립 성능으로 합산하지 않는다.

## 6. 최우선: 최신 실행 실패 진단, 성능 실험 재시도 아님

가장 최신 공통 기록:
`artifacts/experiments/20261023T143432-1ac2dc2c/record.json`
상태 **failed / stage=execute / return_code=1**, handoff=execution_failed.
실행 worker 원본은 같은 폴더 `code/0-after.py`, 작업 파일은 `artifacts/dino-block8-features-20261023/worker.py`, 사전 계획은 같은 폴더 `plan.json`이다.

가설은 마지막12층 특징 대신 고정8번째 층(index7) 특징만 쓰는 것이다. 하지만 첫 입력의 `get_intermediate_layers(n=[7,11], norm=True)`에서 얻은 최종층 특징과 기존 마지막층 특징 캐시 사이의 최대 절대 오차가 사전 기준2e-4 아래인지 검사하다 line23에서 AssertionError로 종료됐다. 오차의 실제 값은 출력되지 않았으며 이유는 미확정이다. **학습 fold/성능 평가 전에 실패했다. 중간층이 성능을 개선/악화했다고 말할 결과가 없다.**

첫 작업은 새 진단 ID/worker로 소수 입력만 확인하는 것이다:
1. 캐시 `feature_sources` 계보, 행ID·사진 SHA·EXIF·crop 반올림·448 resize/pad·정규화, 백본 가중치/코드 SHA·CPU/MPS 출처를 추적한다. row와 cache 순서도 검증한다.
2. 같은 입력 텐서·같은 모델·같은 실행 환경에서 `get_intermediate_layers(...)[최종층]`와 `forward_features()['x_norm_patchtokens']`부터 대조한다.
3. 이어 기존 캐시와 max/mean 오차·실제 head 점수 차이를 측정해 원인을 구분한다. 두 API가 같은데 캐시만 다르면 캐시/입력/생성 환경의 문제일 가능성을 조사한다. 원인을 아직 단정하지 않는다.
4. assert를 지우거나 tolerance를 올려 강제 통과시키지 않는다. 수치 환경 차이로 확인됐다면 영향 범위·기준 재현 근거를 먼저 기록하고 새 사전 계획을 세운다. 원본 캐시/실패 기록/기준 점수는 덮어쓰지 않는다.
5. 동일 조건의 실패를 자동 재실행하지 않는다. 반증 가능한 수정 근거가 확보될 때만 중간층 단일 실험의 재개 여부를 정한다. 층 번호 sweep·테스트 정답 학습·파이리 결과에 맞춘 튜닝은 금지한다.

## 7. 반복하면 안 될 실패와 경계

- 정상 손실의 패치 수 효과 제거: `artifacts/experiments/20261023T120712-fc61365d/record.json`, completed/false. 같은26 FP2→3/22(+4.55%p), 구간/실제점 FN0/4 유지. 수학4검사는 통과했지만 성능 개선은 아니다. 원래 손실을 유지한다.
- 원본+제곱 특징: `artifacts/experiments/20261022T210745-9ab8daee/record.json`, 미채택. FP4/22·실제점 FN2/4.
- ±7px 패치 위상 학습: `artifacts/experiments/20261021T215246-9cd2cfe8/record.json`, 실제점 누락 악화로 미채택.
- 공분산 보정/이웃 평균/정상 손실 절반/미세 RGB 대비 특징/과거 LoRA·CNN 등은 상단 TODO와 각 원본 계획·결과를 먼저 대조한다. 다른 실패 자료를 이름만 바꿔 재실행하지 않는다. 과거 미세대비/학습 백본 실험의 범위는 `NATIVE_REVIEW_MICROTEXTURE_20261018.md`, `WEAR_FEATURE_LEARNING_VALIDATION_20261017.md` 참조.
- OpenCV는 보류 상태다. 수집기·라벨 UI·자동 토론 프레임워크 개선을 이번 모델 캐시 진단과 섞지 않는다. eBay 수집기는 기존 `tools/collect_ebay_dataset.py`가 있고 기본 수집과 외부 모델 판독을 구분한다.
- 이 작업은 외부 Gemini/NVIDIA/추가 Codex CLI 모델 호출 없이 진행한다. 계획 `gemini_calls_allowed=0`. `./review --auto`로 별도 실제 모델/토론을 시작하지 않는다. provider 비밀 설정이나 consumer API키를 가져오지 않는다.

## 8. 사람이 필요한 경우와 보고

기존 정답을 재질문하지 않는다. 모호한 새 정답만 실제 원본 위치를 명확히 보여주고 한 번에 묻는다. unknown을 임의 정상/손상으로 만들지 않고, 모델 오답을 이유로 정답을 바꾸지 않는다. 사람 의존 작업만 대기하고 승인 범위의 독립 진단은 계속한다. 지속을 위한 임의 기능/동일 학습 반복은 금지한다.

각 결과에는 변경 파일·핵심 diff·실행한 검사·실제 record 상태/수용 판정·리스크·롤백을 남긴다. 같은 자료의 FN/FP/분모/%p, 구간과 실제점 누락, 모델선택 자료와 독립 시험을 구분한다. 성능/모델 비교를 했으면 사진 위 사람 정답·모델 출력과 분모를 담은 새 HTML을 만든다. 실행 실패는 실패 원인만 표시하고 없는 성능 수치를 만들지 않는다. file:// 브라우저 읽기는 CUA URL 정책으로 차단된 이력이 있으므로 우회 서버/다른 브라우저를 만들지 말고 직접 HTML 링크와 원본 PNG를 제공하며 렌더 검증 여부를 밝힌다.

첫 응답은 읽은 근거·최신 상태·소유 파일·첫 진단 성공/실패 기준만 짧게 확인한 뒤 진행한다. 근거가 없으면 무작정 재학습하거나 정상 사진을 또 요청하지 않는다. Codex 검토용으로 최소 diff/record/REPORT/HTML 경로를 남긴다. 합의·실행 완료와 실제 성능 향상을 구분한다.
