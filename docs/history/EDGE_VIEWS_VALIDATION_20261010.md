# 테두리 확대 입력 비교 — 2026-10-10

## 문제·가설·수용 기준

ㅅ 정상 뒷면 테두리를 기존 모델이7~8/8구역 오탐했다. 현재 특징 추출 입력은 바깥 테두리와 카드 내부가 함께 있는3×3구역이다. 내부 그림 영향은 가능한 가설이며 확정 원인은 아니다. 사람이 확인한 정상 정답은 그대로 보존한다.

외곽을 확대해서 함께 보면 결함 단서가 더 잘 보이는지 시험한다. 동일 학습119구역/기존 검증50구역·동일 엣지 출력·seed42·20epoch·클래스 및 실물 보정으로 비교한다. 오탐/누락을 함께 확인하고, 새 정상 카드 ㅅ은 학습과 epoch선택에서 제외한다. ㅅ은 이미 이전 모델로 확인한 개발검증 카드이며 최종시험이 아니다.

## 구현

- card_condition/edge_views.py: 원래 구역 특징을 보존하고, 해당 구역이 닿는 외곽 띠의 특징 평균을 연결한다. 띠 폭은 카드 가로/세로의1/12(3×3셀의1/4)로 검증 전에 고정. 모서리 구역은 두 띠, 변 중앙은 한 띠. 중앙은 엣지 정답이 없으며 입력/보고 동일성 유지를 위해 원래 특징을 사용한다.
- region_experiment.py: 선택적 edge_input=context/views. 엣지 전용 head만 학습, labels/box/그룹/기존 split 불변. backbone은 고정 ImageNet MobileNet, 선형 head만 학습한다. 기존 기본 경로는 유지한다.
- cli.py: point-experiment --edge-input context 또는 views. --balance --epochs20 사용. 새 의존성 없음.
- point_probe.py: 별도 *_point_edge_views_v1 체크포인트만 확대 입력으로 추론. views정책/edge전용 supported 검증, 학습과 같은 patch_features 재사용. 기존 checkpoint 호환과 누수 검사 유지. 운영 RegionAnalyzer에 새 모델을 연결하지 않았다.
- tests/test_edge_views.py: 띠 좌표/원구역 보존, 실제 fixture 학습·추론 확률 일치, test사진 미열람, 개발자료 재검증 차단, 잘못된 checkpoint정책 거부.
- pyproject.toml0.4.24. 마스터TODO와 본 문서 갱신. 사람 라벨/운영 모델 변경 없음.

## 실제 실행 결과

학습 입력: artifacts/point-evidence-20261010-round17.jsonl. train119/val50, ㅅ 없음.

| 실험 | 기존val 엣지 오탐/누락 | 별도ㅅ 정상8구역 오탐 |
| --- | --- | --- |
| 엣지전용 원래구역 | 5/4 | 8 |
| 엣지전용 원래구역+외곽확대 | 9/1 | 7 |

검증BCE로 선택된 epoch은 기준선20, 확대5. 엣지 전용 손실이라 기존3종류 공동 head의 epoch/수치와 혼동하지 않는다. 모든 구역은 같은 실물 내에서 상관되므로8독립카드로 세지 않는다. 확대는 누락 감소와 오탐 증가의 교환이며 정상 구별 문제 해결 증거가 부족해 채택 보류한다. ㅅ 결과를 보고 임계값/띠폭을 조정하지 않았다. 실제 Gemini 절감0건.

근거 산출물:

- artifacts/point-edge-{context,views}-20261010-epochs20/{inputs.jsonl,report.json,model.pt}
- artifacts/point-edge-input-comparison-20261010.json: 입력/정답/이미지/영역 동일성과 보고 수치 재계산 검산.
- artifacts/point-edge-s-probe-20261010.json: ㅅ 1실물/8구역, 완전한 round17개발이력과 checkpoint ID/그룹/해시 중복 차단, 입력/모델 SHA불변 확인.
- 라이브 라벨 SHA256은 실험 전후10f42fb3b40799c3041dcef4380d7f8146277e9444813cbfbf81809ee3995e74로 유지.
- Python전체59개 통과(/private/tmp/condition-edge-all-tests.log), 추가 추론 확률 검사 별도 실행. wheel빌드(/private/tmp/condition-edge-wheel.log), 소스 포함 일치 검산.

## 리스크·다음 의존성·롤백

추가 띠 입력은 특징추출 비용을 늘린다. 이번 MPS특징추출+head학습 시간은5.39초→12.22초이며 운영 요청 지연 측정이 아니다. 카드box가 부정확하거나 원근 왜곡이 있으면 외곽 띠가 틀릴 수 있다. 저해상도 확대는 없는 정보를 복원하지 않는다.

정상 뒷면 학습은 여전히 ㅂ1실물로 부족하다. 남은 신규 정상 실물1장을 확보해 학습 다양성을 보강한다. ㅅ과 기존 검증은 학습으로 옮기지 않는다. 새 프레임워크/전체 미세조정 확대는 보류한다. 기존 사람 정답을 모델에 맞게 수정하지 않는다.

롤백은 edge_views.py와 관련 테스트를 제거하고 region_experiment/point_probe/cli의 선택적 연결 및 버전을 함께 복구한다. 독립 경로의 새 실험 모델은 운영에서 참조하지 않으므로 운영 모델 복구는 필요 없다. 원본 라벨을 되돌릴 이유도 없다.
