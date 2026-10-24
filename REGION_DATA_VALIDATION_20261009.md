# 구역별 결함 라벨 준비 — 2026-10-09

## 결과
TODO의 결함 위치 자료 확보를 위한 라벨 UI, 스키마 검사, region-audit를 구현했다. 기존 면별 모델과 원본 사람 라벨은 수정하지 않았다. 재학습이나 Gemini 호출 절감은 아직 없다.

## 핵심 변경
- 카드 영역의 3×3 구역에서 모서리/엣지/표면을 각각 1/0/null로 사람이 명시한다.
- 반사로 안 보이는 항목은 null로 유지한다. 반사 자체를 결함이나 구매 제외로 변환하지 않는다.
- 해당 면이 결함 있음인데 위치가 없으면 검토 목록으로 남긴다. 없는 위치 라벨을 정상 자료로 채우지 않는다.
- 구역의 결함 있음은 면의 같은 결함 있음과 일치해야 한다. 기존 저장 파일은 region_labels 없이 계속 읽힌다.
- region-audit는 train/val만 처리하며 test의 이미지/라벨을 읽지 않는다. 출력 덮어쓰기를 막는다.

## 실제 자료
artifacts/visibility-complete-20261009.jsonl을 읽기 전용 감사했다. artifacts/region-readiness-20261009.json에 구역 자료0개, ready_for_experiment=false, 결함 위치가 필요한 면/항목38건이 기록됐다. 같은 면의 다른 결함이 중복 집계되므로 38장이 아니다. 사람이 관찰한 정상·결함 구역을 저장한 뒤 새 snapshot으로 재감사해야 한다.

## 검증
- 전체34개 unittest 통과: 구역 좌표 계산, null 보존, 클래스 준비 여부, test 격리, 모순 라벨/적용 불가 위치/boolean 값 거부, 저장·내보내기 및 기존 회귀.
- review.html JavaScript node --check 통과.
- 0.3.1 wheel을 no-index/no-deps/no-build-isolation으로 빌드하고 region_dataset.py 및 새 review.html 포함을 검사했다. 산출물: artifacts/dist-regions-20261009/pokemon_card_condition-0.3.1-py3-none-any.whl. 기존 0.3.0은 보존했다.
- 별도 합성 fixture localhost:8767에서 브라우저로 좌측 상단 모서리 정상(0) 저장, 저장 완료 확인, 화면 재생성 후 0 복원 확인. 엣지·표면은 미확인으로 유지됐다. 실제 사용자 라벨을 이 검증에 사용하거나 수정하지 않았다.
- 사용자 localhost:8766 서버 재시작은 최초 자동 승인 검토에서 미저장 입력 위험으로 거절됐다. 사용자에게 저장 완료·재시작 허용을 확인받은 뒤 새 서버로 재시작했다. 기존 라벨은 유지한다. HTTP 테스트는 제한된 sandbox에서 소켓 bind 권한으로 1건 실패했지만 localhost 허용 후 전체34개 통과했다.

## 변경 파일
card_condition/regions.py, card_condition/review.html, card_condition/region_dataset.py(신규), card_condition/cli.py, tests/test_regions.py, tests/test_region_dataset.py(신규), pyproject.toml, README.md, 이 문서, PokeCollector CONDITION_ANALYSIS_TODO.md. PokeCollector 런타임/DB 변경은 없다.

## 리스크와 롤백
3×3는 거친 위치 표기이며 원근 보정을 하지 않는다. 영역을 바꾸면 위치 라벨 의미가 달라져 사람 재확인이 필요하다. 선택지는 해당 항목의 구역을 충분히 봤을 때만 정상으로 기록해야 한다. 현 단계는 학습 자료 준비이며 모델 성능 개선을 입증하지 않는다.

원본 라벨·가중치는 그대로다. UI의 구역별 입력과 region-audit를 제거하면 기능을 중단할 수 있다. 이미 저장한 region_labels를 보존하려면 regions.py의 선택 필드 읽기 지원은 유지한다. 모델 소비 앱은 바꾸지 않아 운영 롤백은 필요 없다. 기존 0.3.0 wheel도 보존한다.
