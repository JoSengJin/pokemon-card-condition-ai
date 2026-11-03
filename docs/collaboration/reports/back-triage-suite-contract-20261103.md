# 후면 점검 우선순위 묶음(엣지·모서리·표면·관찰 제한) 동결본과 사용 계약 (2026-11-03)

결함·제한 판정기가 아니다. 사람이 확인한 카드 상자가 있는 후면 사진에만 점검 우선순위/재촬영 권고 점수를 낸다. 앞면·센터링은 `unsupported_human_review`로만 표시하고 정상으로 판정하지 않는다. `complete`는 항상 false.

## 동결 head (재현 기록 `20261103T140659-9eacc492`, completed, 같은 장치 mps·같은 코드 재현만 확인)
| 항목 | 파일 | SHA-256 | 저장된 독립 보류 점수 대비 최대 절대차 |
|---|---|---|---|
| 엣지(§41) | `artifacts/triage-edge-back-candidate-20261101/head.pt` | 4b0412c4…(기존) | 기존 재현 0.0 |
| 모서리 후보 E | `artifacts/triage-back-candidates-20261103/corner-head.pt` | `3dafe055…ab50187` | 5.96e-8(232구역·58사진) |
| 표면 후보 B | `artifacts/triage-back-candidates-20261103/surface-head.pt` | `cb862aa6…29ca787b` | 1.19e-7(531구역·59사진) |
| 관찰 제한 후보 F | `artifacts/triage-back-candidates-20261103/observation_limit-head.pt` | `e28e655e…86491b8` | 1.19e-7(101면) |
임계: 엣지 0.31/0.54, 모서리 0.2808/0.5093, 표면 0.2129/0.4682. 백본 DINOv2 ViT-S/14는 head와 별도 보관.

## 호출
`card_condition/back_triage_suite.py`의 `BackTriageSuite(heads, body, device).analyze(request)`; request는 `dict(id, side='back', image, box, box_reviewed=True)`. 부분 모듈: `back_zone_triage.py`(모서리·표면), `back_obs_limit.py`, 기존 `back_edge_triage.py`. 앞면·상자 미확인·읽기 불가·비유한 점수는 부분별 `held`.

## 상태·한계
- D2 독립 시험 결과(§80~§81): 엣지·모서리·관찰 제한 충족, 표면 미충족(격차 0.140). 표면 head는 릴리스 후보가 아니다.
- 표면 head 파일의 SHA는 재현 확인용이며 품질 통과를 뜻하지 않는다.
- 검증: 합성 단위 테스트 9개(가짜 백본, `tests/test_back_triage_suite.py` 4개 포함) 통과 + 위 재현 기록. 실제 사진 end-to-end 묶음 호출(`BackTriageSuite`) 실행은 하지 않았다(모서리·표면·관찰 제한은 개별 모듈 경로로만 재현).
- 구조: `back_zone_triage.py` 함수 3개(`zone_scores`, `__init__`, `analyze`), `back_obs_limit.py` 4개, `back_triage_suite.py` 2개. 최대 호출 경로 `analyze → analyze → zone_scores`(2회).
- 소비 서비스 연결·운영 배포는 별도 승인 대상(승인 아님).

## 롤백
새 파일 삭제(`card_condition/back_zone_triage.py`, `back_obs_limit.py`, `back_triage_suite.py`, `tests/test_back_triage_suite.py`, head 3개). 기존 모듈 변경 없음.
