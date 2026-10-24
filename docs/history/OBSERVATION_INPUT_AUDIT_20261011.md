# OBSERVATION_CONSENSUS 재개: train-only 입력 근거 진단

2026-10-11 / 0.4.43

## 완료 결과

새 모델을 반복 학습하는 대신 학습 사진 원본 crop과 실제224px 입력의 신호를 대조하는 visibility-input-audit 명령을 추가하고 실행했다. 고정 source의 train46면/25실물(관찰 제한 없음32면, 제한14면)만 사용했다. val/test 사진·라벨은 로딩하지 않았다. 사용자 라벨·모델·Gemini 경로는 변경하지 않았다.

주요 결과는 같은 앞/뒷면 내에서 비교한 학습 기술 통계다.

| 224px 신호 | 반사 라벨8면 중 관찰 제한 없음 범위와 겹친 면 |
|---|---:|
| 전체 평균 밝기 |7 / 8|
| 전체 밝기 표준편차 |8 / 8|
| 인접 픽셀 밝기 차이 |6 / 8|
| 3x3 구역 평균 밝기의 최대-최소 차이 |6 / 8|

앞면/뒷면의 정상 디자인이 다르므로 비교 범위는 각각 앞면20개, 뒷면12개의 명시적 관찰 제한 없음 자료로 나눴다. ‘관찰 제한 없음’은 카드 손상이 없다는 뜻이 아니다. 위 겹침 수는 학습 자료의 min/max 범위 안에 놓인 수이며 오탐률·분류 정확도·가설 반증이 아니다. 사진 수 기준 통계이고 실물별 균등 추정량도 아니다.

‘밝으면 반사’, ‘명암이 크면 제한’이라는 단일 신호를 곧바로 운영 필터로 쓰지 않는다. 구역별 밝기 차이도 반사8면 중6면이 관찰 제한 없음 범위와 겹친다. 그늘 앞뒤2면의 구역 밝기 차이는 해당 면의 관찰 제한 없음 범위를 벗어났으나 동일 실물1장뿐이다. 이 한 장으로 그늘 일반화 규칙을 만들지 않는다. 흐림 학습 사례는0면이다.

실제 반사 뒷면224px 예시(43-224.png)를 열어 반사 자체가 남아 있는 것을 확인했다. 따라서 이번 진단은 모든 제한이 축소에서 사라졌다고 주장하지 않는다. 밝은 반사는 순백 픽셀과 같지 않으며 카드 인쇄색/질감/원본 해상도/패딩이 지표에 영향을 준다.

## 개발 범위와 안전 조건

- card_condition/observation_audit.py: Pillow로 원본/224px 밝기·표준편차·인접 픽셀 차이·밝은/어두운 픽셀 비율, 3x3구역 신호를 기술 통계로 저장. 밝음>=245/어두움<=25는 사전 고정된 픽셀 구간이며 학습/최적화한 판정 임계값이 아니다.
- grid는 관측 위치를 보존하기 위한 진단이다. 각 셀에 부모 사진의 제한 정답을 복제하지 않는다. 분류기·SPP·새 정상/결함 라벨을 만들지 않는다.
- card_condition/visibility_model.py: visibility_rows에 선택 splits를 추가. 기존 학습 default train/val은 유지하고 audit만 train을 요청한다.
- card_condition/cli.py: visibility-input-audit 명령 연결.
- tests/test_observation_audit.py: 국소 신호 산술, 1px 경계, val/test의 존재하지 않는 사진/잘못된 라벨을 읽지 않음, manifest 불변, JSON roundtrip, 기존 출력 덮어쓰기 거부 검증.
- pyproject.toml0.4.43, README.md, 본 문서와 소비 프로젝트 CONDITION_ANALYSIS_TODO.md.

새 필수 의존성은 없다. 모델 재학습·새 백본 다운로드·서버 재시작·사용자 재라벨링은 없다. OBSERVATION_CONSENSUS 원문은 그대로 유지했다.

## 실행 결과와 재현

최종 산출물은 artifacts/observation-input-audit-0443-20261011/report.json 및 index.html, 46개의 원본 crop 미리보기(max448px), 46개의 실제224px 이미지다. 원본 통계는 축소 전 native crop에서 계산한다. 224px는 기존 side_image와 동일한 회색 padding/BILINEAR 전처리를 사용한다. 구역 통계의 padding 영향도 한계에 기록했다. 초기 생성본 observation-input-audit-20261011은 요약표 추가 전 개발 산출물이며 성능 실험의 별도 후보가 아니다.

```sh
.venv/bin/card-condition visibility-input-audit artifacts/observation-geometry-20261011-source.jsonl artifacts/NEW-AUDIT-DIRECTORY
```

전체91테스트 통과(27.058초). 이후 HTML 요약표 추가에 대한 관련2테스트 재검증 통과. wheel0.4.43 빌드, Python/HTML37파일 source byte 일치. 실제 CLI46면 실행 및 46개224px 이미지 크기 확인, 모든 manifest/사진 해시와 live의 기존 복귀 audit SHA 불변 확인.

## 다음 개발 기준

OBSERVATION_CONSENSUS의 독립 입력 가설 원칙을 유지한다. 전역 밝기 임계값·한 장의 그늘 규칙·기존 재학습 반복은 다음 실험으로 선택하지 않는다. 다음 입력 가설은 국소 색/질감 신호가 인쇄 무늬와 관찰 제한을 구별할 근거를 먼저 명시하고, 전처리 한 요소만 바꾸는 별도 계획으로 사전 고정한다. 진단 통계만으로 성공을 선언하거나 없는 고해상도 원본/깨끗한 비교 사진을 재요청하지 않는다. 종류별 독립 일반화 근거가 없으면 계속 보류한다.

## 리스크와 롤백

이 도구의 픽셀 값은 제한이나 손상 정답이 아니다. 같은 실물 앞뒤는 독립 표본이 아니며 해상도·인쇄색·패딩의 영향이 남는다. 연구 분석 자료를 운영 자동 제외나 정상 통과로 연결하지 않는다. 실제 Gemini 절감은0건이다.

코드 롤백은 .backups/observation-audit-0443/의 visibility_model.py·cli.py·pyproject.toml·README.md를 복원하고 신규 observation_audit.py·test_observation_audit.py를 제거한다. 이후 변경이 있으면 해당 diff만 복원한다. 신규 artifact는 보존 가능하며 사용자 라벨/원본/모델 파일을 되돌리지 않는다.
