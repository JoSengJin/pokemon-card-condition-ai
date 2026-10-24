# 실행 흐름 재정리와 다음 사람 확인

실험 하나가 끝날 때마다 재개 명령을 요구한 것은 합의한 휴먼인루프 진행 방식과 맞지 않았다. 마스터 TODO 상단을 현재 실행 순서로 분리하고, 기존 날짜별 미완료 항목은 이력으로 표시했다. 현재 목표는 독립 상태 분석 모델이며 운영 가능 후보와 Gemini 절감은 아직 확보하지 못했다.

최근 실제 개발은 정상/결함 학습 자료 보강, 동일 val 비교, 학습 클래스 보정에 해당한다. 검증 명령은 이 비교를 재현하는 도구이며 자체로 모델 정확도나 Gemini 절감을 달성한 것이 아니다.

최신 data/learn-review.jsonl에서 기존 region-review-plan을 실행했다. 원본 해시 b5f505a241f16b077b70bf7ae671dd284e6c682c0628f9704b9a8467a3427546. train 정상 뒷면 실물 모서리1·엣지0·표면1, 정상 앞면은4·4·5다. val/test 사진·정답은 보강 후보 선정에 사용하지 않았다.

산출물 artifacts/region-review-plan-20261010-live-next-human.json의 첫 후보 ebay-50f5e8124d55bb/back/upper_right/edge_defect를 사람에게 연다. 기존 b/s는 저장 완료 이력을 존중해 이번 요청에서 제외했다. 새 사진이나 전체 재라벨링 대신 미완료 엣지 한 구역만 확인한다. 현재 면 엣지0은 후보 조건일 뿐 구역 정답이 아니다. 확인 불가이면 null+검토 완료로 끝낼 수 있으며, 모델 출력0.495는 정답이나 확신도가 아니다.

변경 파일:
- card_condition/region_review_plan.py: 전체 gradable null로 최신 위치 자료 목록 전체가 거부되는 문제 수정. load_manifest의 선택적 require_gradable=False를 후보 계획에만 사용. 면 gradable1·명시적 면 정상0·관찰 제한·완료 제외 검사는 유지.
- tests/test_region_review_plan.py: 전체 gradable null과 관찰 가능한 면을 분리해 기존 후보3개/중복/완료 제외 검증.
- pyproject.toml0.4.18 및 마스터 TODO의 현재 실행 순서, 이 문서.

검증: 전체 테스트57개 통과(/private/tmp/condition-human-loop-tests.log), 0.4.18 wheel 빌드 성공(/private/tmp/condition-human-loop-wheel.log), 실제 최신 원본 계획 생성 성공(/private/tmp/condition-live-next-human-plan.log). 브라우저에서 해당 사진 묶음·뒷면 우측 상단 확대·엣지 항목 강조와 검토 완료 체크박스를 확인했다. 화면 증거 /private/tmp/condition-next-human-edge.png. 원본 라벨·모델 변경 없음. 이 단계에서는 새 정답이 아직 없으므로 재학습하지 않는다.

롤백: region_review_plan.py의 선택 인자·테스트 추가행과 버전/문서 변경을 되돌린다. 라벨 복원은 필요 없다. 정상 판정은 사람 확인 전까지 생성하지 않으며 후보 선택이 모델 개선을 보장하지 않는다.
