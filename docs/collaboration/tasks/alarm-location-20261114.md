# D-LOC 저장 점수 진단

Codex · codex/alarm-location-20261114 · 기준 3cbf778 · 로컬 전용.
소유 파일은 이 계약, tools/diagnostics/alarm-location-20261114/{prereg.json,analyze.py,inputs.py}, docs/collaboration/reports/alarm-location-result-20261114.md이다.
기본 checkout의 무시된 산출물은 artifacts/alarm-location-20261114/{results.json,report.html}이다.
사전등록 커밋 뒤 저장 자료만 한 번 연결한다. 분모·ID·점수를 대조하고 통과 시 집계, 결정표 적용, HTML 대조와 열기까지 수행한다. 사용 입력과 중단 조건은 prereg.json에 고정한다.
구조는 새 Python 파일별 0 → 최대 7개 함수, 호출 전이 최대 4회. 실제 개수·검사·한계는 결과 보고서에 기록한다.
학습·외부 호출·모델/worker·금지 자료·기타 작업 소유 파일은 범위 밖이다. 롤백은 결과 커밋, 사전등록 커밋 순으로 revert한다.
