# 감사 보고서 저장 실패 안전성

개발 진척 30/100 유지. 감사 내용이나 모델 성능은 변경하지 않았다.

## 재현과 변경

기존 data_coverage는 최종 경로에 open(x) 후 json.dump했다. 합성 writer가 일부 문자열을 쓰고 OSError를 내면 부분 JSON이 최종 경로에 남았고, 다음 호출은 기존 출력으로 거절됐다.

card_condition/data_coverage.py는 동일 디렉터리 NamedTemporaryFile에 쓰기/flush/fsync를 완료한 뒤 os.link로 최종 이름을 공개한다. 기존 출력과 경쟁 출력은 덮어쓰지 않는다. 일반 예외 경로에서 context manager가 임시 파일을 정리한다. 출력 JSON/함수 반환/집계/라벨/호출자 계약은 보존했다. 새 의존성 없음.

tests/test_data_coverage_output_safety.py에 정상 출력·부분 쓰기 오류 후 재시도·sync 오류·link 오류·기존 출력·경쟁 출력 6개 검사를 추가했다. 계약과 실행 기록은 동명 task 문서에 남겼다.

## 검증

기본 checkout에 수정 커밋 48600e6을 41d9295로 통합 후 다음 55개 테스트가 통과했다.

```sh
PYTHONPATH=tests .venv/bin/python -m unittest test_data_coverage test_point_dataset test_region_dataset test_regions test_review test_data_coverage_provenance test_data_coverage_projection_contract test_data_coverage_photo_consistency test_point_comparison test_data_coverage_output_safety -q
```

실제 development/live의 반환 dict와 저장 JSON 모두 이전 artifacts/data-coverage-integration-20261025T010340/{development,live}-v2.json 전체와 동일하다. manifest SHA도 동일하다. 근거: artifacts/data-coverage-output-safety-20261025/tests.log 및 verification.json. unittest는 Ran 55 tests / OK로 완료했다. 이어진 셸 구문의 예약 변수 status 사용 오류는 테스트 실행과 구분해 기록했다.

학습·모델 추론·외부 AI·사람 정답 변경 0회. 모델 정확도·일반화 개선을 평가하지 않았다.

## 리스크와 롤백

hardlink 미지원 파일시스템은 저장이 실패한다. 임시 파일에서 이어받은 출력 권한은 기본 0600으로 제한된다. SIGKILL 시 임시 파일이 남을 수 있으며 디렉터리 fsync까지 수행하지 않으므로 전원 상실 내구성을 보장하지 않는다. 동작 범위는 정상/예외 종료에서 완성된 파일만 공개하고 기존 출력을 보존하는 것이다.

롤백: 진행 중 실행이 없을 때 ./develop -- git revert 41d9295. 문서 기록은 보존할 수 있다. 원본 데이터·라벨·모델 변경 없음.
