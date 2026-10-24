# 0.4.53 독립 매물 사진 API 검증

## 결과와 범위
독립 `pokemon-card-condition` 프로젝트에 `ListingAnalyzer` / `listing-predict`를 추가했다. 학습 manifest·split·결함 정답 없이 앞뒤 이미지·정규화 카드 영역·사람 관찰 제한만 전달한다. 현재 고정 모델은 엣지 전용이며 다른 결함은 미지원으로 남는다. 기존 PokeCollector 운영 호출 경로는 변경하지 않았다. 실제 Gemini 절감0건.

## 변경 파일 / 핵심 diff
프로젝트 루트: `.`
- `card_condition/listing_model.py` 신규: 한 번 로딩한 RegionAnalyzer 재사용, 엄격한 입력 계약, 이미지 SHA 기록/실행 중 변경 거부, 관찰 제한/미검토 구역 생략, 기존 completeness 계산 재사용.
- `card_condition/listing_readiness.py`: 선택 `unreviewed_sides`와 `observation_not_reviewed` 사유 추가. 기존 호출의 기본 동작 유지, 설명문을 데이터셋에 종속되지 않게 정정.
- `card_condition/cli.py`: `listing-predict CHECKPOINT REQUEST.json`과 선택 `--batch-views`, `--device` 추가. 기존 공통 오류 JSON / exit1 유지.
- `tests/test_listing_model.py`: 누락/미검토/부분 반사/흐림/카드 영역 누락, 입력 계약, 파일 변경, 재사용과 입력 불변 회귀2개.
- `README.md`, `pyproject.toml`: 호출 계약·한계 문서화, 버전0.4.53.
- 이 검증 문서 및 `artifacts/listing-api-20261011/`: 실제 실행 스크립트, 요청 예시, 결과, 배포 wheel, 검증 근거.
- 소비 프로젝트 `${POKECOLLECTOR_ROOT}/CONDITION_ANALYSIS_TODO.md`: 상단 실행 목록에 이번 계획/완료 근거만 추가.

## 수용 기준과 실행 증거
- 라벨과 split 없는 요청 처리. API 내부 null labels는 기존 annotation validator의 구조 재사용에만 사용하며 파일 저장·학습·정답 선택에 사용하지 않는다.
- `visibility_issues` 누락은 면 전체 미검토 unknown, 명시적 `[]`만 호출자의 제한 없음 주장으로 수용한다. 이것이 모델의 정상 인증을 뜻하지 않는다.
- 부분 glare는 지정 영역만 보류. 위치 없는 glare 또는 다른 제한은 전체 면 보류. 사진/box 누락은 unknown이고 손상 판정으로 바꾸지 않는다.
- 전체117테스트 통과: `TORCH_HOME=artifacts/torch-cache .venv/bin/python -m unittest discover -s tests` (40.102초). 해당 listing 테스트9개도 별도 통과.
- 실제 MPS: 기존 고정 val15매물/160구역을 배치 추론. 기준 대비 최대 점수 차이1.4901161193847656e-7, 모든 구역 state/reason 일치. 정답 라벨은 추론 요청에 포함하지 않았다. 기존 자료 재사용 통합 검산이며 새 정확도 평가가 아니다.
- 실제 CLI 성공 JSON, 잘못된 split 포함 요청의 exit1/오류 JSON/Gemini fallback 확인.
- 모델·source snapshot·live 라벨 SHA 불변. 각 호출은 사진 SHA를 실행 전후 대조했다.
- 외부 다운로드 없이 wheel0.4.53 빌드. Python/HTML44파일이 현재 소스와 byte 일치.
- wheel을 `/private/tmp/condition-0453-installed`에 no-index/no-deps 설치, `/private/tmp`에서 설치본 module path 확인 후 CLI CPU 실제 추론 성공. MPS 기준 최대 차이8.940696716308594e-7.
- 상세: `artifacts/listing-api-20261011/checks.json`, `verify.py`, `results.json`, `cli.json`, `installed-cli.json`.

## 리스크 / 제외한 작업
호출자가 카드 영역과 관찰 제한을 제공해야 한다. 임의 사진의 자동 카드 검출·관찰 제한 판독·같은 실물 연결을 제공하지 않는다. normal/defect는 기존 탐색 임계값 .3/.7이며 미교정이다. 현재 엣지 모델만으로 전체 상태 분석 완료나 점수·구매 판단·Gemini 생략을 확정할 수 없다. 독립 test 자료가 없어 일반화 검증은 미실행이다. 기존 학습 데이터/모델/완료 라벨을 변경하거나 재라벨링하지 않았다. 추가 의존성·서버·프레임워크·자동 재학습은 넣지 않았다.

## 롤백
`.backups/listing-api-0453`의 cli.py, listing_readiness.py, pyproject.toml, README.md를 원래 위치로 복원한다. 신규 listing_model.py / test_listing_model.py만 제거하고0.4.52 wheel을 사용한다. 보고서·실험 결과는 증거로 보존해도 동작에 영향을 주지 않는다. 소비 TODO의0.4.53 항목은 롤백 상태로 표시한다. 학습 라벨과 모델을 되돌릴 필요는 없다.

에튜: 추론 API는 학습 데이터셋과 분리한다. ‘입력이 없다’와 ‘모델이 정상이라고 판단했다’를 구분해야 나중에 소비 서비스가 unknown을 결함 없음으로 잘못 취급하지 않는다.
