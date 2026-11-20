# 후면 모서리 입력 크기 224 대조 실험 계획 (2026-11-20, 실행 전·승인 대기)

> 실행 방식은 사용자가 정하지 않았다. 이 계획은 코드·학습을 실행하지 않았다. 기준: [설계 문서](../specs/2026-11-20-corner-d3-miss-fa-design.md).

**Goal:** 가설 ①(자르기 크기·해상도)을 단일 변수로 시험한다: 모서리 입력 크기 448→224, 나머지는 후보 E 레시피와 동일.

**Spec:** docs/superpowers/specs/2026-11-20-corner-d3-miss-fa-design.md

## 가설 ①의 메커니즘 점검 (설계 때보다 약해짐)
- 모서리 자르기 폭 중앙값은 원본 사진에서 약 250~350px이다. 현재 후보 E는 이를 448px로 **확대**해서 입력한다. 확대는 정보를 더하지 않으므로 "448→672 더 키우기"는 근거가 약해 이번 계획에서 제외했다(공유 모듈이 224·448만 허용하는 점도 이유).
- 대신 정반대 방향인 224 입력을 시험한다. 결과 해석: 224가 더 나쁘면 패치가 가리는 원본 면적(14px 패치 = 원본 약 8px→16px)이 결함 포착에 중요하다는 근거가 되고, 비슷하거나 낫다면 해상도는 병목이 아니라는 근거가 된다. 어느 쪽이든 다음 가설(②·③)의 선택 근거를 준다. 224 자체가 후보 개선안이라고 기대하지 않는다.

## Global Constraints
- 변경 변수 1개: `image_size` 448→224. 학습 자료·fold·λ(1.0)·레시피·동결 임계 0.281/0.509 불변.
- 대조: 기록 `20261102T140143-82781117`의 `scores`(후보 E, 쌍 순위 항 포함)와 같은 fold 결과를 대조로 쓴다. 새 대조 학습은 하지 않는다.
- D1 봉인·D2 시험 자료 사용 0, Gemini 0, 학습 2×fold 수는 기존과 동일 규모.
- `./develop -- <명령>` 안에서만 소스 생성, 실행은 `./experiment --plan <plan.json> -- .venv/bin/python <worker>`. 기본 checkout 단일 담당자.

## 사전 수치 기준 (결과 보기 전 고정)
같은 정의(L)의 실물 단위 사건을 개발 OOF 946구역·257그룹에서 센다. 기준선: 누락 37/176, 오탐 17/81, 풀링 AUC 0.8565.
- 성공 문장: 224 입력이 누락 ≤33/176이고 오탐 ≤17/81이며 풀링 AUC ≥0.8465이다.
- 실패 문장: 위 셋 중 하나라도 어긋난다.
- 해석 규칙(결과 전 고정): 누락·오탐 모두 기준선보다 4건 넘게 나빠지면 "해상도가 병목" 신호, 어느 쪽도 4건 넘게 변하지 않으면 "해상도는 병목 아님" 신호로 적는다. 사전 기준 밖의 모든 변화는 일반화 근거로 쓰지 않는다.
- 4건 기준은 176/81 분모에서 약 10%/20% 상대 변화라는 제 판단이며 통계 검정이 아니다.

## Files
- Create: `tools/experiments/corner-input224-cv-20261120/worker.py` (함수 ≤7, 호출 깊이 ≤4)
- Create: `tools/experiments/corner-input224-cv-20261120/plan.json`
- Test: `tests/test_corner_input224_worker.py`
- 수정 금지: `card_condition/*`, 기존 worker 전부(기존 파일은 import만).

## Task 1: worker
**Interfaces**
- Produces: `features224(body, rows, device) -> (x: Tensor[n,256,384], masks: Tensor[n,256] bool)`; `main()`가 `observations.json`(rows·scores·control_scores)과 `evaluation.json`(L 사건 수, AUC, 사전 기준 판정) 저장.
- Consumes: `pool.fit_pool`, `sw.score`, `cv.fold_of`, `pair.fit_pair`(기존 worker와 동일 호출), `view_tensors(path, boxes, 224)`, `physical_pixel_mask(path, box, halo=0, image_size=224)`.

- [ ] Step 1: 테스트 작성 — 합성 이미지 3장으로 `features224` 출력 shape가 (n,256,384)·마스크 (n,256)이고 모두 유한함을 확인(백본은 가짜 모듈), L 사건 집계 함수가 알려진 점수에서 기대 건수를 반환함을 확인.
- [ ] Step 2: 테스트가 실패하는지 실행해 확인.
- [ ] Step 3: worker 구현. 기존 corner worker의 흐름(rows 동결 검증→특징→OOF 2종→평가)을 따르되 특징만 224용으로 교체. 쌍 순위 항 포함 arm 하나만 학습한다(대조는 기존 `scores`를 읽어 재사용하고 해시로 고정).
- [ ] Step 4: 테스트 통과 확인, 새 파일 함수 수·호출 깊이 기록.
- [ ] Step 5: 커밋.

## Task 2: 실행
- [ ] `./develop --check` → plan.json의 `code_changes`(worker, baseline null)·`input_sha256` 고정 → `./experiment --plan ... -- ...` 실행 → `record.json` 경로·실제 상태·`result.json` 판정을 사용자에게 보고.
- 기준 미달·실패·중단은 모델 성능 수치로 해석하지 않는다. 같은 가설을 새 반증 근거 없이 재시도하지 않는다.

## Review Focus (이 계획이 놓치기 쉬운 것)
1. 224는 대조와 입력 크기뿐 아니라 마스크 격자(16×16)도 달라진다. 마스크 reshape를 모양 불일치로 조용히 틀리지 않는지 테스트로 고정.
2. 대조 점수를 재사용하므로 fold 배정·rows 순서가 같음을 SHA로 검증해야 한다.
3. L 사건은 그룹 단위다. 한 사진의 4구역이 같은 그룹이므로 행 단위 집계로 잘못 세지 않는지 테스트로 고정.
4. 결과가 "나쁨"이어도 실패가 아니라 해석 규칙에 따른 신호다. 보고에서 실패로 뭉뚱그리지 않는다.
5. 새 후보 채택이나 D3 통과 주장은 이 실험으로 불가능하다(독립 시험 아님).

## 리스크·롤백
- 224 시험은 개선 후보가 아니라 원인 분리 실험이다. 누락·오탐 감소는 기대하지 않는다.
- 롤백: 새 파일 2종과 테스트 삭제(`git revert`), 기존 파일·점수 불변.
