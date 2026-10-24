# Round16 — ㄷ·ㄹ·ㅁ 엣지 위치 반영

## 결과

새 라벨로 두 로컬 모델을 실제 재학습했다. train105→111구역, val50구역/8실물 동일. 두 모델 모두 round15와 같은 오탐/누락 수로 운영 채택을 보류한다. Gemini 실제 절감0건이며 운영 모델 변경 없음.

| 모델 | 모서리 FP/FN | 엣지 FP/FN | 표면 FP/FN |
| --- | --- | --- | --- |
| 기본 | 6/0 | 12/0 | 19/0 |
| 클래스 보정 | 2/1 | 5/5 | 11/9 |

근거: artifacts/point-grid-{augmented,balanced}-round16-comparison-20261010.json. 반복 사용한 모델선택 val이므로 최종 시험 성능은 아니다.

## 사람 확인과 데이터 보존

- ㄷ5점은 처음 surface_defect로 저장됐으나 사용자 '5개 모두 엣지 결함' 확인을 받아 edge_defect로 정정했다. 좌표와 다른 카드 내용은 불변이다. 표면 null을 정상0으로 바꾸지 않았다.
- ㄹ1점·ㅁ2점은 엣지로 저장되어 있었다. ㄷ5점→4구역, ㄹ1점→1구역, ㅁ2점→1구역으로 중복 제거되어 신규6구역이다.
- 확인 전 ㄹ·ㅁ만 사용한 round16-partial 실험은 이력으로 보존하고 최종 round16과 구별한다.
- data/learn-review-before-d-kind-confirmation-20261010.jsonl.bak는 종류 정정 직전 전체 원본이다. data/learn-review.jsonl의 ㄷ 지점 종류와 확인 메모만 수정했다.
- 최종 동결 입력: artifacts/point-evidence-20261010-round16.jsonl. SHA256: 38056989036fa975c608655c9012daa3277b2ac14e87e777bdc5d9a47adaa565.
- artifacts/point-evidence-round16-receipt.json에서 기존 학습 입력·검증 입력 불변과 좌표 불변을 검산했다.

## UI 수정과 검사

변경 파일: card_condition/review.html, tests/review_validation.test.cjs, pyproject.toml(0.4.22), 본 문서, PokeCollector의 CONDITION_ANALYSIS_TODO.md, 라벨 원본과 분리된 실험 산출물.

카드 영역을 편집하면 도구를 다시 그리며 선택 종류를 표면으로 초기화하던 원인을 수정했다. 이미지별 종류 선택을 페이지 메모리에 유지하고, 미선택 이미지에 양성 종류가 하나뿐이면 그 종류를 기본 선택한다. 선택 도구만 변경하며 기존 점의 종류는 자동으로 변경하지 않는다. 페이지 새로고침 시 선택 메모리는 초기화되지만 저장된 점은 보존된다.

- Python57개 통과: /private/tmp/condition-drm-kind-python-tests.log.
- Node UI 회귀검사 통과: /private/tmp/condition-drm-kind-tests.log.
- wheel0.4.22 빌드 성공: /private/tmp/condition-drm-kind-wheel.log. wheel의 review.html과 작업 소스 바이트 일치 확인.
- 최종 기본/보정 학습20epoch 완료. /private/tmp/condition-round16-final-{train,balanced}.log.
- 최종 두 비교 명령 정상 종료. /private/tmp/condition-round16-{augmented,balanced}-compare.log.

## 남은 의존성·리스크·롤백

정상 뒷면 엣지 학습 실물0개가 남아 있다. 완료 카드 재요청 없이 정상 관찰이 가능한 신규 실물1~3장이 다음 데이터 보강 대상이다. 반사/가림/null은 정상으로 바꾸지 않는다. 손상 사례 추가만으로 성능 개선을 보장할 수 없다.

운영 연동과 자동 Gemini 생략은 하지 않았다. 코드 롤백은 UI의 pointKinds/pointKind와 onchange 연결 및 관련 테스트·버전 변경만 되돌린다. 라벨은 코드 롤백과 별도로 보존한다. 종류 정정만 복구하려면 백업의 ㄷ 행만 확인 후 반영한다. 전체 백업을 덮어쓰면 이후 사용자 저장을 잃을 수 있다. 실험 모델은 별도 경로이므로 운영 체크포인트 복구는 불필요하다.
