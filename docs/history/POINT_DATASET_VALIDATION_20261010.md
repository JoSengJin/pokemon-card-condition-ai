# 사람 지점 기반 실험 입력 생성 — 2026-10-10

## 결과

사람이 s/back에 저장한 표면 결함4지점을 사용하는 별도 입력 생성 CLI를 추가했다. 기존 구역 학습기나 원본 라벨·분할은 변경하지 않았다.

```sh
.venv/bin/card-condition point-dataset artifacts/regions-labeled-20261010-round7.jsonl artifacts/point-crops-20261010-round7
```

출력은53개 이미지 crop 명세(patches.jsonl)와 준비 상태(report.json)다. 이미지를 복제하지 않고 EXIF 방향에 맞춘 원본의 정규화 좌표를 기록한다. 기존 side_tensor로224px 입력 생성이 가능함을 테스트했다.

| 표면 | 정상 구역 | 사람 결함 지점 | 정상 실물 | 결함 실물 |
|---|---:|---:|---:|---:|
| train |29|4|4|1|
| val |10|0|2|0|

결함 점4개는 실물1개다. val 결함 지점이 없어 ready_for_experiment=false이며 새 모델을 학습하지 않았다. e/back 관찰 제한 정상2구역은 제외됐다. 기존 val을 train으로 이동하지 않았으며 test는 읽지 않았다. 이 val은 개발 모델선택 자료이며 미사용 최종평가를 대체하지 않는다.

## 규칙 및 한계

- 사람 지점 + 면 결함1이 있어야 해당 종류만1로 사용. 나머지 종류는 null.
- 카드 경계를 넘지 않도록 가로·세로 각1/3 crop을 안쪽으로 이동. 점은 결함 크기·심각도·segmentation mask가 아니다.
- 정상은 구역에 명시한0만 사용. 면0이나 미확인으로 정상 생성 금지. 관찰 제한 구역과 같은 종류의 사람 지점이 있는 정상 구역은 제외.
- train/val마다 대상 종류의 정상·결함 실물 존재 여부를 확인. 존재만으로 충분한 성능이나 독립 표본 수를 보장하지 않는다.
- 현재 crop 선택은 양성=지점 중심, 음성=고정 구역이어서 위치 편향 가능. 향후 학습은 실물 가중치와 동일 crop 정책의 비교 검증이 필요하다. 기존 학습기에 이 파일을 직접 전달하지 않는다.
- 다음 사람 작업은 기존 val 중 표면 결함1이지만 지점 없는 w/front의 실제 결함 위치 지정. 이미 완료한 s의 좌표 재확인 요청이 아니다. 원래 분할을 유지하며 학습용에 넣지 않는다. 더 다양한 정상/결함 뒷면과 미사용 최종평가는 여전히 필요하다.

## 변경·검증·롤백

변경: card_condition/point_dataset.py, card_condition/cli.py, tests/test_point_dataset.py, README.md, pyproject.toml(0.4.12), 이 기록과 마스터 TODO.

테스트: 지점/정상 타깃, null 유지, 같은 실물 중복 집계 방지, 반사·모순 입력 제외, 카드 가장자리 crop,224px 전처리, test 격리, 원본 불변, 출력 덮어쓰기 거부. Python 전체48개 통과(로그 /private/tmp/condition-point-dataset-tests-final.log). 최초 제한 환경에서는 HTTP 서버 bind2개가 권한 오류였고, 임시 localhost 서버 실행이 허용된 재검사에서 전체 통과했다. 0.4.12 wheel 빌드 및 point_dataset.py/cli.py 소스 일치 확인. 신규 환경 설치와 새 모델 학습은 미실행.

운영 모델 변경 없음, production_ready=false, Gemini fallback 유지, 실제 절감0건. 롤백은 point-dataset CLI 분기와 신규 모듈/테스트/문서/버전 변경만 제거한다. 사람 좌표와 기존 모델·라벨 원본은 유지한다.
