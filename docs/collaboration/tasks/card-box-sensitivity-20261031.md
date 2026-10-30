# 카드 상자 어긋남 민감도 측정 (카드 찾기 개발의 첫 단계)

- task_id: card-box-sensitivity-20261031
- owner: Claude (Codex 토큰 만료 기간 대행. 절차는 Codex 방식을 따른다)
- status: plan_only (worker·실행 없음)
- base_sha: 66da7b09e703b109c87396ff48439e69cdeb7f72 (main)
- approval: 2026-10-31 사용자 "응 진행해" — 운영 입력이 원본 사진(카드 외 배경·손 등 포함)이므로 "카드 찾기"를 개발 범위에 추가하는 것을 승인. **점수표(`PROGRESS_CRITERIA.md`)·`development-progress.json`의 배점·완료 조건은 변경하지 않았다.** 배점 변경은 별도 명시 승인이 필요하다.

## 배경 (근거)
- 현재 추론은 사람이 준 카드 상자를 입력으로 받고 자동 카드 검출이 없다(`card_condition/listing_inference.py:99`). 진척 기준도 수동 영역 보조 흐름이다(`PROGRESS_CRITERIA.md` 8행).
- 자동 상자 제안(`autobox.py`)은 f 배치 뒷면 21면 중 12면에서 카드가 상자 밖으로 잘렸다.
- 상자가 어긋날 때 head 3 점수가 얼마나 변하는지는 측정된 적이 없다.

## 이번 작업 범위
- 새 파일: 이 문서, `tools/experiments/box-perturbation-sensitivity-20261031/plan.json`. 코드 수정·worker·실행 없음.
- 실험(승인 후): 사람 확인 상자를 네 변 10% 넓혀 같은 head 3으로 val 275구역을 재점수. 사전 기준은 plan.json에 고정(FN<=28, FP<=69, AUC>=0.774). 허용폭은 판단값이다.
- 보조 팔(넓힘 5%·20%, 대각 이동 5%, 안쪽 3%)은 보고만 하고 판정에 쓰지 않는다.

## 구조 (worker 작성 시 준수)
- 새 worker 함수 7개 이하, 호출 깊이 4 이하. 기존 `edge-back-source-weight` worker의 `features`·`score`·`edge_rows`는 import해서 쓰고 수정하지 않는다.

## 실행 전 확인할 것
1. `./experiment`는 단일 worker·사전 계획만 허용한다. worker 작성은 `./develop -- <명령>` 안에서 한다.
2. 비교 전 점검: 상자 변경 없이 같은 코드 경로로 재점수한 값이 고정 head 3 점수(`observations.json`)와 1e-4 이내.
3. `acceptance`의 정수는 위 기준과 일치한다(placeholder 아님).
4. 결과 보고에 전체 AUC·같은 사진 AUC(`tools/within_photo_auc.py`)·FN/FP·분모를 같은 평가 자료로 쓴다. 독립 평가가 아니므로 일반화 개선은 미확인이다.

## 한계
- 상자는 축 정렬이라 회전·원근 오차, 손·받침대 오검출은 모델링하지 않는다. 이 실험이 통과해도 운영 카드 찾기가 충분하다는 뜻이 아니다.
- 통과하면 "넓은 상자에는 둔감"이고, 실패하면 "카드 찾기 정밀도가 모델 성능의 전제"다. 어느 쪽이든 카드 찾기 정확도 평가는 별도 작업이다.

## 롤백
새 파일 2개 삭제(`git revert`).
