# 면별 관찰 제한 사유

## 구현 결과

앞면·뒷면 각각에 `visibility_issues`를 선택적으로 저장한다. 허용 값은 `glare`, `blur`, `obstruction`, `cropped`, `low_resolution`이다. 기존 JSONL은 필드가 없어도 그대로 읽으며 모델의 기존 결함 라벨과 입력은 바꾸지 않는다.

라벨 화면에서 다섯 사유를 복수 선택할 수 있다. 보이는 결함과 가려진 영역이 함께 존재할 수 있으므로 `gradable=0`이어도 결함 양성은 유지하고, 가려진 항목만 `null`로 남긴다. 이 메타데이터는 현재 모델의 학습 목표로 사용하지 않는다. 충분한 사람이 확인한 사례가 쌓인 뒤 평가 가능성 분류의 근거로 검토한다.

`label-audit`는 평가 불가인데 사유가 없는 면을 `ungradable_reason_missing`으로 기록한다. 최초 감사에서는 11면이 해당했고, 평가 불가이면서 결함 없음 라벨이 있는 기존 검토 대상은 3건이었다. 이는 자동 오류 판정이 아니라 사람 검토 목록이다. 분할 변경 11건도 계속 보고하며 새 snapshot에서 기존 역할을 보존해야 한다.

사용자가 확인한 `i/front`의 좌측 센터링 쏠림과 `u/front`의 우측 하단 조명 반사 근거는 기존 `docs/history/VISIBILITY_AUDIT_VALIDATION.md`에 보존돼 있다. 사용자 근거에 따라 새 UI에서 `u/front`에 `빛 반사`를 저장했고 자동 백업이 생성됐다. 재감사 결과 사유 누락은 10면으로 줄었으며 `u/front`의 결함 라벨은 변경하지 않았다.

## 변경 파일

- `card_condition/regions.py`: 선택 필드와 허용 값 검증.
- `card_condition/review.html`: 면별 관찰 제한 체크박스.
- `card_condition/side_experiment.py`: 학습 행에 사유 메타데이터 보존. 현재 loss에는 사용하지 않음.
- `card_condition/label_audit.py`: 평가 불가 사유 누락과 사유 변경 감사.
- `card_condition/error_review.py`: 이후 생성할 오류 화면에 기록된 사유 표시.
- `tests/test_regions.py`, `tests/test_label_audit.py`: 저장·내보내기·잘못된 값·누락 감사 검증.
- `README.md`, PokeCollector `CONDITION_ANALYSIS_TODO.md`: 작업 방법과 다음 단계.

## 검증

- Python unittest 23개 통과.
- `review.html` JavaScript 문법 검사 통과.
- 실제 읽기 전용 감사 결과: 도입 전 `artifacts/visibility-reasons-audit-20261009.json`, `u/front` 저장 후 `artifacts/visibility-reasons-after-u-20261009.json`.
- `data/learn-review.jsonl`의 `u/front.visibility_issues=["glare"]`만 추가. 기존 결함 라벨, 실험 snapshot, 모델, PokeCollector 운영 코드와 DB 변경 없음.

## 기술 선택 판단

반사는 평가 가능성을 가리는 실제 원인으로 확인됐지만, 흰색 인쇄·홀로그램과 단순 밝기 반사를 구분할 데이터는 아직 없다. 현재는 OpenCV를 추가하지 않는다. 남은 10면에 사람이 사유를 기록한 뒤 반사가 반복적인 주원인인지 확인한다. 원근·경계 실패가 반복되면 OpenCV, 라벨 정리와 torchvision 부분 미세조정 후에도 특징 한계가 남으면 timm을 검토한다.

## 리스크와 롤백

사유 체크는 사람이 관찰한 메타데이터일 뿐 결함이나 진위를 증명하지 않는다. 기존 레코드에 필드가 없으므로 감사에서 누락으로 보일 수 있지만 학습은 계속 가능하다. 코드 롤백은 `visibility_issues` 관련 변경을 위 파일들에서 제거한다. 데이터 롤백은 `data/learn-review.jsonl.1791496712719388000.bak`에서 복원할 수 있으며 운영 DB 복구는 필요 없다.
