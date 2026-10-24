# 확인 불가 영역과 데이터 분할 점검

## 사용자 확인 근거 (2026-10-08)
- i/front: 센터링이 좌측으로 쏠림. 사람 centering_defect=1 유지. 모델0은 누락.
- u/front: 우측 하단 천장 빛 반사로 기스/화이트닝 유무 확인 어려움. gradable=0 유지. 숨겨진 결함이 있다는 확정이 아니라 확인할 수 없다는 뜻.
- u/front의 기존 corner/edge=null, surface=1은 보이는 결함과 가려진 부분의 불확실성이 공존할 수 있으므로 자동 수정하지 않았다. 기존 surface=1의 상세 정답성은 이번 발언만으로 재확정하지 않았다.

## 개발 결과
label-audit inventory reference output 명령 추가. 기존 개발 스냅샷 train/val의 ID에 한해 현재 분할 변경, 면별 주석 변경, gradable=0인데 결함=0인 항목을 검토 대상으로 기록한다. 사람 라벨은 변경하지 않는다. gradable=0의 모든 결함을 null로 바꾸지 않으며, 확인 불가(null)를 정상으로 세지 않는다.

실제 점검: 분할 변경11건, 평가 불가 사진의 정상 라벨 검토3건. 이는 확정 라벨 오류가 아니다. 실험에서는 frozen snapshot을 유지해왔으므로 11건 자체가 과거 실험 누수를 의미하지 않는다. 다음 snapshot도 --reference로 기존 역할을 보존해야 한다. u는 현재 화면 train이나 실험 기준 val이며 train으로 재편입하지 않는다.

## 변경 / 검증
- card_condition/label_audit.py 신규: 읽기 전용 감사 및 해시 기록, 출력 덮어쓰기 금지.
- card_condition/cli.py: label-audit 명령 추가.
- tests/test_label_audit.py 신규: null/양성 보존, 음성 검토, 분할 변경, 원본 보존, test 이미지 미사용 검증.
- 이 문서 및 PokeCollector CONDITION_ANALYSIS_TODO.md 갱신.
- 23개 unittest 통과. 실제 결과 artifacts/label-audit-20261008.json. 모델 재학습 및 운영 변경 없음, 정확도 개선 측정 없음.

## 기술 검토 시점
반사 사례가 확인되어 사진의 영역별 관찰 가능성 기준을 구체화할 시점이다. 하지만 밝은 픽셀만으로 반사를 판별하면 흰 인쇄도 오탐할 수 있어 OpenCV 추가만으로 해결된다고 보지 않는다. 원근/카드 경계 오류의 반복 근거는 아직 없으며 OpenCV·timm 도입은 보류. 보이는 결함과 보이지 않는 영역을 구별하는 사람 라벨 기준 확인 후 PyTorch 부분 미세조정 여부를 검토한다.

## 리스크 / 롤백
전체 사진이 평가 불가여도 보이는 영역은 정상으로 라벨링할 수 있으므로 감사 경고를 자동 교정에 사용하면 안 된다. 같은 카드의 다른 ID는 이 도구만으로 추적하지 않는다(기존 snapshot의 group/해시 보호 사용). 롤백: .backups/step12/cli.py를 card_condition/cli.py에 복원하고 label_audit.py/test_label_audit.py 제거. 새 감사 JSON은 별도 보관/삭제. 원본 라벨·사진·DB 복원 불필요.
