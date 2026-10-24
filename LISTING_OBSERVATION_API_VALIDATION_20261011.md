# 0.4.54 독립 매물 API 관찰 모델 연결

## 진척률 산정 기준
개발 기반 4/6단계 완료(67%, 동일 비중 체크리스트 기준). 소요 시간·모델 정확도·호출 절감률을 뜻하지 않으며 범위 변경 시 분모도 갱신한다.

| 단계 | 완료 기준 | 상태 |
|---|---|---|
| 1 | 사람 라벨·사진/실물 식별·분할·입력 버전 관리 도구 | 완료 |
| 2 | 구역 결함 모델 학습/평가/저장/추론 기준선 | 완료 — 현재 선택 모델은 엣지 전용 |
| 3 | 관찰 제한 모델 연구 비교·보류/제약 보존 | 완료 — 일반화 승인 아님 |
| 4 | 독립 Python/CLI 패키지·두 모델 연결·회귀/설치 검증 | 완료 — 수동 카드 영역 입력 |
| 5 | 개발 미사용 실물로 오류 기준 충족 여부 최종평가 | 미완료 — 새 독립 자료 없음 |
| 6 | 소비 서비스 관찰 실행·승인된 제한 적용·실제 절감 측정 | 미완료 — 운영 변경/실제 절감0 |

이 비율은 개발 기반의 기능 체크리스트다. 카드 전체 상태를 안전하게 맡길 수 있다는 뜻이 아니다. 남은 품질 검증 결과에 따라 추가 모델 개선이 필요할 수 있다.

## 변경 파일과 핵심 diff
루트 `.`:
- `card_condition/listing_model.py`: 선택 observation_checkpoint, VisibilityAnalyzer 인스턴스1회 로딩/재사용, evidence 별도 추가. 미검토 사람 제한은 null 보존. 두 모델 실행 이후 원본 SHA 변경 검사.
- `card_condition/listing_observation.py`: 기존 evidence 로직에 선택 analyzer 주입을 추가, 기존 호출 호환. 구역 판단/라우팅은 변경하지 않는다.
- `card_condition/cli.py`: listing-predict의 --observation-checkpoint 선택 옵션.
- `tests/test_listing_model.py`: 낮은 제한 점수로 glare를 해제하지 않음, 높은 점수로 미검토를 손상으로 판정하지 않음, 모델 재사용, 누락, 비유한/범위 밖 점수 거부, 관찰 실행 중 파일 변경 거부.
- `README.md`, `pyproject.toml`: API 계약/한계와0.4.54 버전.
- `AGENTS.md`: 개발 진척률+성과 한 줄 보고 방식 영속 기록.
- 본 문서, `artifacts/listing-observation-api-20261011/`: 실제 검산 스크립트·결과·CLI·wheel 근거.
- 소비 프로젝트 `CONDITION_ANALYSIS_TODO.md`:0.4.54 실행 근거 및 진척 기준 링크.

## 실행 결과
- 전체118테스트 통과(41.591초). 최초 신규 테스트의 box=null/glare_areas 비어 있지 않은 입력이 기존 계약 검증에 막혔고, fixture를 유효하게 수정한 뒤 전체 통과했다. 제품 입력 검증을 완화하지 않았다.
- 실제 MPS15매물/160구역/27면. 새 옵션 전후 구역 점수 및 readiness 완전히 일치. 기존 관찰 모델 보고서 대비 관찰 점수 최대 차이0.0.
- 미검토 면은 관찰 점수가 있어도 구역 score=null / observation_not_reviewed 유지. 사람 visibility_issues는 null로 표시하여 정상 확인으로 둔갑하지 않는다.
- CLI 두 모델 연결 실제 실행과 Python 결과 완전 일치. 모델·source·live 라벨 SHA 불변. 추가 학습·외부 모델 호출 없음.
- 외부 다운로드 없는 wheel 빌드, Python/HTML44파일 소스 byte 일치. /private/tmp/condition-0454-installed 설치본을 저장소 밖에서 실행했다. CPU 대 MPS 최대 구역 차이8.94e-7, 관찰 차이5.96e-8.
- 근거: artifacts/listing-observation-api-20261011/checks.json, verify.py, results.json, unreviewed.json, cli.json, installed-cli.json.

## 리스크와 롤백
옵션 사용 시 관찰 모델의 추가 로딩 메모리/실행 비용이 발생한다. 관찰 점수는 면 전체의 미교정 신호이며 위치별 자동 반사 검출이나 손상 증명이 아니다. 기존 val 재사용은 연결 검산이고 독립 정확도 검증이 아니다. 같은 실물 검증, 전체 등급, Gemini 자동 생략은 제공하지 않는다. 실제 호출 절감0건.

롤백은 `.backups/listing-observation-api-0454`의7파일을 같은 경로로 복원하고0.4.53 wheel을 사용한다. 소비 TODO의0.4.54 항목은 롤백으로 표시한다. artifacts/보고서는 증거로 보존 가능하며 모델·라벨 롤백은 불필요하다.

에튜: 관찰 제한 점수와 카드 손상 점수는 다른 질문에 대한 답이다. 함께 반환해도 서로의 정답을 덮어쓰지 않도록 계약을 분리해야 한다.
