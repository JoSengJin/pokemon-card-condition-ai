# 구역 특징 추출 모델 비교 및 검토 우선순위 — 2026-10-09

## 변경 파일과 핵심 diff

- `card_condition/region_experiment.py`: 기존 backbone helper를 재사용해 MobileNet/ResNet18 선택. 기본은 기존 MobileNet. 보고서와 체크포인트에 모델 종류 기록.
- `card_condition/region_model.py`: 두 종류 독립 추론 및 종류/구조 일치 검사. backbone_name 없는 구형 MobileNet 체크포인트도 호환.
- `card_condition/comparison.py`, `card_condition/cli.py`: `region-compare` 명령 추가. 같은 snapshot·val ID·사진 픽셀 해시·실물 그룹·구역 좌표·사람 정답·지원 출력인지 검증. 예측에서 혼동행렬을 재계산해 보고서 수치도 검산. 비교/오류 위치를 JSON으로 저장.
- `card_condition/review.html`: 정상 보강 순위에 train 앞면/뒷면별 정상 실물 그룹 수를 반영. 기존 최대3실물·건너뛰기·완료 처리 유지. 부족한 쪽을 우선하지만 정상/결함을 추정하지 않는다.
- `tests/test_region_experiment.py`: ResNet18 학습-독립추론 일치, 구형 호환, 구조 불일치 차단, 비교 결과 검산, 변조된 사진/영역/정답/그룹/확률/지표 차단.
- `tests/review_validation.test.cjs`: 정상 앞면만 충분한 경우 뒷면 우선, val이 우선순위 학습 통계에 섞이지 않음 검증.
- `README.md`, `pyproject.toml`: 명령/범위 문서와 0.4.3 패키지 버전.
- PokeCollector의 `CONDITION_ANALYSIS_TODO.md`: 진행 기록만 갱신. 소비 앱 코드/DB 변경 없음.

## 고정 실험 조건과 결과

입력: `artifacts/regions-labeled-20261009-efficient-round1.jsonl`, SHA256 `ac7d184aab66a83dc836dcc54c0eb43c7e7641413680365b50050ab8006639b7`.

seed42, 224픽셀 구역, 공식 torchvision ImageNet 사전학습 고정 특징, head만 학습, 최대20회, unweighted val BCE로 회차 선택, 임계값0.5. ResNet 실험은 그룹 보정 끔. val은38구역/7실물 그룹이며 독립 최종시험이 아니다.

|실험|모서리 오탐/누락|엣지 오탐/누락|표면 오탐/누락|선택 회차|
|---|---:|---:|---:|---:|
|MobileNet 기본|2 / 1|4 / 5|9 / 2|20|
|MobileNet 그룹 보정|6 / 0|9 / 0|12 / 1|3|
|ResNet18 기본|3 / 2|4 / 2|11 / 1|20|

ResNet은 엣지 누락이 줄었지만 모서리와 표면 오탐이 악화. 전체 모델 교체 보류. 이 결과로 결함 종류마다 모델을 골라 조합하면 같은 작은 val에 맞추는 추가 모델선택이 되므로 자동 혼합하지 않았다.

전체 실험 시간은 MobileNet 약3.82초, ResNet 약3.82초. 이는 특징 추출과20회 head 실험 시간이며 모델 생성/가중치 다운로드는 제외된다. 운영 추론 속도 비교나 메모리 측정으로 해석하지 않는다.

산출물:

- `artifacts/region-baseline-20261009-resnet18-epochs20/model.pt`
- 같은 디렉터리의 `report.json`
- `artifacts/region-backbone-comparison-20261009.json`: 세 모델 검산 결과, 그룹/면별 혼동행렬, 구역별 오류 위치.

## 검증

전체 Python37개 및 JavaScript 리뷰 회귀검사 통과. MobileNet 구형 추론과 ResNet 독립 추론을 검사했고, 실제 고정 snapshot에서 세 보고서를 새 비교 명령으로 검산했다. 실제 라벨 자동 저장·정답 수정·서버 재시작은 하지 않았다. UI 우선순위는 JS 로직 검사이며 현재 열린 화면을 새로고침해 동작을 확인하지 않았다.

## 다음 진행과 사람 개입

배포 검증: `dist/pokemon_card_condition-0.4.3-py3-none-any.whl` 생성 완료. wheel 내부 region_experiment/region_model/comparison/cli/review.html 5개 파일이 소스와 바이트 단위로 일치함을 확인했다. wheel SHA256 `e5edd30ae84039f924bcf0417293c0809330aa44d0d38f06b7999f5bb08eb1c1`. 새 가상환경에 설치한 실행 검증은 아직 하지 않았다.

사용자에게 전체 재라벨링을 요청하지 않는다. 기존 정답은 유효하며 모델 오답은 모델 개선 근거다. 정상 보강 후보를 요청할 때는 앞뒷면/종류 다양성과 최대3실물 제한을 유지한다. 현재 val 정상 모서리는1실물뿐이므로 새 실물 검증 데이터가 필요하다. 기존 val을 train으로 옮기거나 시험 결과에 맞춰 정답을 바꾸지 않는다. 신규 독립 최종평가 확보 전 운영 통합과 Gemini 생략은 보류한다.

원근 보정/더 세밀한 결함 박스/미세조정은 다음 후보지만 지금 실험으로 필요성이 입증된 것으로 보지 않는다. 먼저 그룹/면별 오류 목록으로 같은 디자인·촬영 조건에 오류가 집중되는지 확인하고 별도 검증 사진으로 재현해야 한다.

## 리스크와 롤백

ResNet 체크포인트는 기존 MobileNet보다 커진다. 모델 출력은 보정된 확률이 아니며 반사와 미확인을 정상/결함으로 바꾸지 않는다. 실제 Gemini 절감0건, production_ready=false 유지.

`--backbone`과 `--group-balance`를 빼면 기존 모델/학습 방식이다. 완전 롤백은 위 변경 파일에서 이번 기능 diff만 되돌리고0.4.2 패키지를 사용한다. 원본 라벨/사진/기존 모델은 변경하지 않았다. 새 실험 파일은 비교용으로 보관 가능하다.
