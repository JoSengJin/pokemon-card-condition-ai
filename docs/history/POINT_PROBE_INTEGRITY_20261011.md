# point-probe 입력 무결성 수정（0.4.71）

## 결과

새 검증 카드 진단에서 사진이 실행 중 바뀌어도 성공 보고서가 저장되던 오류를 수정했다. 이 문서는 모델 정확도 개선 실험이 아니다. 개발 기반4/6=67%, 실제 Gemini 절감0건 유지.

## 변경 파일과 핵심 diff

- `card_condition/point_probe.py`: 기존 evaluation_inputs의 track_photos/unchanged_inputs를 재사용해 개발 manifest와 history의 사진 SHA를 검사한다. 파일이 달라지면 보고서를 저장하지 않는다. development_sets로 공통 provenance 검사를 적용하며, 모델이 지원하는 정답의 채점 수가0이면 성공 보고서를 거부한다.
- `tests/test_point_probe.py`: 선택 사진·history 사진 변경2사례, provenance17종, 지원 정답0건 회귀. 실제 추론을 사용하는 정상 입력 보존 검사 유지.
- `tests/test_listing_inference.py`: 기존 가짜 hash문자열을 유효한64자리 테스트값으로 바꿈. 실제 데이터/라벨 변경 아님.
- `pyproject.toml`, `README.md`: 버전·계약 설명.
- 소비 프로젝트 `CONDITION_ANALYSIS_TODO.md`: 완료 근거 기록만 추가. 운영 코드 변경 없음.

## 검증 근거

`artifacts/probe-integrity-20261011/reproduce.py`는 합성 사진·미학습 체크포인트로 실제 추론한다. 수정 전 선택 사진/history 사진 변경 모두 성공 저장, 수정 후 둘 다 거부. 깨끗한 동일 입력의 전체 보고서는 전후 정확 일치. 실제 선택 타일 모델도 로딩되며 SHA가 유지된다. 합성 사례로 일반화 성능을 주장하지 않는다.

전체145테스트44.656초·저장소 밖 설치본13테스트17.661초 통과. wheel의Python/HTML52파일이 소스와 일치. checks.json에 wheel SHA와 기존4개 입력 SHA 보존 기록.

정확도 상승 미측정. 학습/정답/임계값/운영 분기 변경 없음. 독립 test 자료가 없어 누락률·오탐률의 새 일반화 개선을 주장하지 않는다.

## 리스크와 롤백

입력 사진 해시를 읽으므로 파일I/O가 추가된다. 빈값/비정상 hash의 과거 수동 체크포인트와 지원 정답이0건인 진단은 이제 거부된다. 정상 선택 모델은 호환된다. 실패 뒤 변경된 사진을 자동 복원하거나 인간 라벨을 덮어쓰지 않는다.

`.backups/probe-integrity-0471/`의 같은 이름 파일을 원래 card_condition/tests/프로젝트 루트로 복원하면 이전0.4.70으로 되돌릴 수 있다. 새 문서/진단 artifacts는 필요시 보관 후 제거하며 실제 모델·라벨은 복구 대상이 아니다.

에튜: SHA-256은 파일내용 지문이다. 검증 시작/끝의 사진 지문이 다르면 동일 입력 실험이 아니므로 저장을 거부한다. 라벨 파일만 고정해도 사진이 바뀌면 재현성을 잃는다.
