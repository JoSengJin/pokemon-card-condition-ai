# 후딘 저장 라벨 반영과 프로젝트 경로 정리

수집기는 처음부터 tools/collect_ebay_dataset.py에 위치했다. 소비 프로젝트 learn에 저장됐던 이번 후딘 사진을 독립 프로젝트 data/ebay-learn/ebay-pair-9f1ce9c8ad88f2에 원본 그대로 복사했다. 사용자 검토 manifest와 사진 inventory·면별 image 참조, 미라벨 수집 manifest, catalog의 learn 대상도 이 경로로 변경했다. 원본은 삭제하지 않았다. 사진 SHA 동일·라벨/좌표/영역/승인 기록을 원래 경로로 환원한 값이 이전 JSON과 완전히 같음을 검증했다. 기존 검토 서버는 매 GET에서 파일을 다시 읽으므로 같은8794 주소를 유지한다. 파일 경로 변경으로 학습 성능이 바뀐 것은 아니다.

## 저장 상태와 비교 범위
앞면 영역 확인 true·표면 결함2점 저장. 뒷면 표면17점·모서리2점은 보존했으나 영역 확인 false라 이번 학습에는 넣지 않았다. 정상 후보 승인0·구역별 정상0으로 미확인을 정상으로 채우지 않았다. 현재 사용자가 저장했다고 알린 앞면만 train에 추가했고 원본145구역을 그대로 유지했다. 새2구역은 전후 분모에 섞지 않았다.

## 성과
같은145구역 개발 실물제외 평가: 누락17→15/93(18.28→16.13%, -2.15%p), 오탐17→19/52(32.69→36.54%, +3.85%p). 정확도111/145(76.55%) 그대로. 새누락0·새오탐3·회복3(결함2/정상1). 새 후딘 자체는 같은 실물을 학습에서 제외했을 때 누락2/2. 기존 개발 데이터 반복사용 결과로 독립 일반화 성능이 아니다. 오탐 증가로 후보 미채택·운영 모델 변경0·기반4/6 유지.

## 검증
계획을 실행 전에 저장, 고정 frozen MobileNet gray앞면/RGB뒷면 mean224 앞뒤head logistic L2=1·임계값.5 유지. 새 실물 전체 제외·학습/제외 사진 SHA 분리·수렴 확인. compare_runs로 기존145구역 ID·사진·정답·영역·group·split 불변 검증. 이전 manifest 바이트 불변 확인. 전후변화6구역과 새2구역 사진을 index.html에 표시.

## 변경 파일
- data/ebay-learn/ebay-pair-9f1ce9c8ad88f2/front.jpg, back.jpg, source.json: 이번 신규 사진·출처만 프로젝트 내부에 추가.
- artifacts/ebay-mixed-surface-20261017/labels-review.jsonl, codex-selected.jsonl, catalog.json, pending-human.json: 경로 정리·저장상태 기록. 사용자 라벨 불변.
- artifacts/alakazam-local-surface-20261017: 실행 계획·합친train·결과·실행script·사진HTML·경로변경기록·복원본.
- README.md 실행 예제와 소비 CONDITION_ANALYSIS_TODO.md 상태 기록. 패키지/운영 코드 변경 없음.

## 리스크와 롤백
원본 사본을 보존해 사진이 두 경로에 있다. 하나의 manifest에서는 동일 실물을 한 번만 포함하며, 이후 수집시 프로젝트 data/ebay-learn 경로를 사용한다. 오래된 전체 데이터는 이번에 일괄 이동하지 않았다. eBay 인증 provider는 기존 소비 모듈을 재사용하지만 기본 수집은 Gemini 호출0이다.
롤백은 out 폴더의 labels-review.before-path-migration.jsonl, codex-selected.before-path.jsonl, catalog.before-learn-path.json을 해당 입력 파일로 복원한다. 원본 사진은 그대로 남아 있다. 이번 비교용 combined-reviewed.jsonl을 운영에 적용하지 않았으므로 모델 롤백 불필요. 사용자 추가 저장 후에는 옛 복원본으로 덮어쓰지 말고 현재 라벨을 보존하며 경로만 되돌린다.
