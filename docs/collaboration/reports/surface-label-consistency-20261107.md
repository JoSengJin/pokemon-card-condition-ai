# 표면 라벨 일관성 확보 후 재학습 — 2026-11-07

**개발 진척 78/100(v1.13), 변화 0점. 승인된 재학습 1회 완료, 사전 성능 개선 기준 미충족·운영 미채택.**

sr1107z1=결함은 별도 응답으로 보존했다. 기존 정상과의 불일치는 사람 재판정으로 병기하며 기존 라벨 오류로 확정하지 않는다. §93 완료267구역은 사용자가 선택한 원판정을 유지했다. 기존 라벨/가중치/운영 코드/PokeCollector/Gemini fallback은 변경하지 않았다.

## 동일 ID·각 라벨 기준 안에서의 비교

두 팔 모두 같은 **1776구역·204사진 그룹**, 동일 5fold·특징448·head·seed·최대반복1000. 판단 불가15구역은 양쪽 학습/평가에서 동일 제외. 원라벨 학습→재판정 반영 학습을 비교했다. 반영한 사람 답260구역 중 원답과 다른 것은191구역(기존190+이번1)이다. 사진·그룹 기준 학습/평가 중복은 열 번의 적합 모두0. 원라벨/새라벨 사이의 숫자를 개선으로 비교하지 않는다.

|평가 정답|결함/정상 분모|AUC 대조→후보|차이 [그룹 bootstrap95% 구간]|누락 대조→후보|오탐 대조→후보|
|---|---|---|---|---|---|
|새 라벨|370/1406|0.9241 → 0.9167|-0.0074 [-0.0165, +0.0010]|91/370 → 67/370 (-6.49%p)|129/1406 → 201/1406 (+5.12%p)|
|원 라벨|179/1597|0.8516 → 0.8490|-0.0026 [-0.0184, +0.0124]|56/179 → 44/179 (-6.70%p)|285/1597 → 369/1597 (+5.26%p)|

임계는 모두0.5. 누락률은 결함 구역 중 누락, 오탐률은 정상 구역 중 오탐이다. 표면 결함만 평가했고 관찰 제한은 이번 실험에서 미평가다. 그룹 bootstrap2000회, seed20261107, 동률0.5 처리한 정확 가중 AUC와 같은 그룹 복원추출로 두 팔을 짝지었다. 합성 동률/반복 그룹 검사에서 명시적 복원추출과 일치했다.

사전 주 기준: 새라벨 AUC차≥0.03 AND 95%하한>0. 실제 차이−0.007418·하한−0.016513으로 **미충족**. 공통 실행기 고정 오류상한 FN≤95·FP≤112도 실제 FN67·FP201로 **오탐 상한 미충족**이다. 해당 상한 대조는 과거 저장 원학습 점수를 같은1776개 ID/새라벨로 재집계한 고정 참고값(FN95/FP112)이고, 위 표의 새로 적합한 원라벨 대조(FN91/FP129)와 다르다. 둘을 섞어 개선을 계산하지 않는다.

이전 §98은1775구역이고 이번은1776구역이며 대조군도 재학습했다. 따라서 §98 숫자와 이번 숫자를 개선량으로 비교하지 않는다. 새 평가를 소비 D1/표면 보류2에 수행하지 않았다. **개발·모델선택 자료의 반복 CV이고 일반화 개선은 미확인**이다. §97은 기존 점수로 표적 선정한 사람 재판정이므로 선택 편향/부분 순환이 남는다. 누락 감소만으로 채택하거나 임계/성공 기준을 사후 조정하지 않았다.

## 실행 기록과 보존

- 계획: `artifacts/surface-label-consistency-20261107/plan.json` (실행 전 고정, 실제 동결본은 실험 폴더 plan.json).
- record: `artifacts/experiments/20261106T210640-0eb1bdc0/record.json` — **completed / finished / return_code0**.
- 시작/종료(UTC): 2026-11-06T21:06:40.286672+00:00 / 2026-11-06T22:16:29.765400+00:00. KST로 2026-11-07 06:06~07:16. 대화 재개 요청 시 기록에서 완료를 회수했으며 재실행하지 않았다.
- 소요: 4186.7초(약69.8분). MPS 특징 추출+CPU head 적합10회, 모두 수렴(max gradient≤1.862e−6). 수렴은 모델 품질의 증명이 아니다. 예전 속도와 통제 비교하지 않아 속도 개선도 주장하지 않는다.
- 공통 실행: `./experiment --plan artifacts/surface-label-consistency-20261107/plan.json -- .venv/bin/python artifacts/surface-label-consistency-20261107/worker.py`.
- 원 응답: `artifacts/surface-label-audit-20261107/answers-20261107.txt`, 매핑/해석은 같은 폴더 `selection.json`·`answer-intake-20261107.json`.
- `result.json`의 공통 판정 false와 `evaluation.json`의 AUC 판정 false를 각각 검산. record에 등록된 파일 SHA와 계획의 모든 입력 SHA 최종 일치.
- 원래1791구역 파일/기존 답·모델 불변. 새 라벨 뷰와 fold는 별도 artifacts에만 저장. 모델 계수는 실험 폴더 models.json에 보존하며 운영에서 로드하지 않는다.
- development-review.json이 허용한 세션과 이 채팅이 달라 자동 검토 연결은 생성되지 않았다. 계획도 Gemini/Codex 호출0이다. 전역 latest.json은2026-10-24 다른 실행의 낡은 handoff라 이번 결과로 사용하지 않았다. 수동 인계는 `artifacts/surface-label-consistency-20261107/handoff.json`. 하위 모델/CLI를 호출하지 않아 새 next_steps/token_report는 없다. 토큰 절감률은 미측정.

## 변경 파일·핵심 diff

- `tools/experiments/surface-label-consistency-20261107/worker.py` (신규): 같은1776구역 두 팔을5fold로 학습하고 공통 observations/evaluation/diagnostics/models를 생성. 기존 연구 fitter·특징/마스크 재사용. 전부eBay인 학습행의 원래 가중치 식을 그대로 호출 지점에서 계산해 불필요한 호출 계층을 줄였다.
- `tools/experiments/surface-label-consistency-20261107/metrics.py` (신규): 원본 보존 라벨 뷰·불가 제외·동률 가중 AUC·동일 사진 그룹 bootstrap·FN/FP 분모.
- `tools/experiments/surface-label-consistency-20261107/plan.json` (신규): 가설·새 근거1구역·단일 변수·수치 기준·원본 해시·평가 제외 자료·AI 호출0 동결 계약. ignored 입력·원사진·사람 응답은 Git에 포함하지 않는다.
- `tests/test_surface_label_consistency_20261107.py` (신규): 라벨 원본 보존/불가 양쪽 제외/미확인·모르는ID 거절, 동률·가중 AUC 쌍계수 대조, 같은 그룹 재표집과 지표 검산3개 합성 검사.
- `docs/collaboration/tasks/surface-label-consistency-20261107.md`: 범위·소유 파일·구조·실제 결과/검증/인계.
- `docs/collaboration/reports/surface-label-consistency-20261107.md`·`.html`: 실측 보고·진척·한계. Git 추적 HTML은 공개 가능한 요약만 담고 사진은 넣지 않는다.
- ignored `artifacts/surface-label-consistency-20261107/`: 새 라벨 뷰/계획/출처·검사/인계/실사진1776구역 report.html. ignored 실험 폴더는 실행기 증거다.

## 실행한 검사·미검증

합성 unittest3개를 실행 전/후 통과. runner 파일 해시 검증 통과, 입력 해시 변화0,10회 적합에서 실사진 raw/decoded hash·그룹 분리 통과. 계획·reference·observations의1776행 동일성과 원라벨/새라벨의target 외 필드 동일 검증. 사진 위204개 article/1776개 평가 구역과15개 불가 표시를 내용 검사한다. `git diff --check` 통과. 전체 회귀/새 독립 시험/운영 적용/휴대폰 실기기/브라우저 렌더는 수행하지 않았다. 사진 HTML 열기 결과는 checks.json과 최종 task 인계에 기록한다.

함수 수 신규worker0(실행 블록), metrics4, tests메서드3로 각 파일≤7. 새 프로젝트 함수 호출경로 실행블록→fit_detail_head→closure→detail_bag_loss→point_bag_loss는4전이; 수치 경로 paired_bootstrap→auc는1전이. 기존 PyTorch optimizer 동적 callback·라이브러리 내부 전체 호출 깊이를 새로 인증한 결과와 구별하며 그 내부는 수정하지 않았다.

## 리스크·롤백·다음 판단

새 답1구역만 추가된 제한적 반복이고 전수 라벨 일관성/새 독립 성능을 증명하지 못한다. 결과는 누락/오탐의 상충을 보여주지만 어느 사람 답이 틀렸는지 증명하지 않는다. 이 결과를 근거로 사람 정답이나 규약을 바꾸지 않는다. 현재 운영 모델 유지, 추가 재학습/새 모델 호출 없음. 이 요청 범위의 검증은 완료했으며 같은 자료/가설은 새 근거 없이 반복하지 않는다.

운영/기존 소스에 적용한 변경이 없어 모델 복원은 필요 없다. 추적 실험·보고 파일 롤백은 잠금·후속 의존 확인 후 이번 커밋을 `./develop -- git revert <SHA>`로 되돌리고 일반 push한다. 새 ignored 후보/응답은 별도 증거로 보존하며 삭제로 사람 답을 되돌리지 않는다. 원격 동기화 SHA는 최종 인계에 기록한다.

에튜 포인트: 같은 사진의 여러 구역을 서로 다른 fold에 섞으면 사진 무늬를 학습해 평가가 쉬워질 수 있다. 이번에는204사진 그룹을 통째로5fold로 나눠 각 구역의 점수를 그 사진을 학습하지 않은 모델에서 얻었다. 예를 들어 한 카드의9칸은 모두 같은 평가 fold에 들어간다. 다만 이미 개발에 사용한 사진이므로 이 방식도 새 독립 시험을 대신하지 못한다.

HTML 열기: Codex native file open 요청 queued. 실제 표시·렌더 미확인. 기존 CUA file 프로토콜 정책 차단을 우회하지 않았다. 원격 통합 SHA는 최종 인계와 artifacts/surface-label-consistency-20261107/sync.json 참조.
