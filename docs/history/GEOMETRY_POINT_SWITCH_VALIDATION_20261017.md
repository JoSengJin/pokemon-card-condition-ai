# 영역 모드에서 결함 입력 전환

사용자 고우스트 결함 클릭 비활성화 제보. geometry=back 딥링크가 geometryClickActive=true로 유지돼 toggle을 잠그는 상태가 원인이다. 영역이 있는데도 결함 표시로 수동 전환하는 길이 없어 작업이 막혔다.

변경: card_condition/review.html에 현재 영역으로 결함 표시하기 버튼과 enablePointInput(side) 추가. geometry query/round만 종료하고 points query로 전환해 패널을 연다. dirty 상태·행·좌표·영역확인false·test split·라벨은 바꾸지 않는다. 영역확인을 자동 승인하지 않는다. 기존 영역확인 완료 후 자동전환 동작은 그대로 유지했다.

tests/review_validation.test.cjs에 실제 전환함수 VM 실행 테스트 추가. geometryCurrent/round 종료·points URL·dirty/annotation 불변·패널 펼침과 안내를 확인. JS전체검사 및 test_review/test_geometry_review Python10개 통과. 실제새브라우저탭의 points 링크에서 뒷면 클릭모드 checkbox Value1/활성·종류미선택·아직라벨저장disabled(변경없음) 확인. 결함은 대신 찍지 않았고 검토자/확인체크도 대신 입력하지 않았다. 새탭을 열어 기존탭의 미저장입력은 보존했다. screenshot /private/tmp/haunter-points-enabled.png.

모델추론/재학습0·정확도변화없음·기반4/6유지. frozen-plan의 모델/사진/정답 파일은 변경하지 않았다. 사용자가 새탭에서 종류를 선택해 결함을 찍고 영역확인도 함께 저장하면 다음 평가를 진행한다.

리스크: 모드 전환은 영역확인 완료가 아니며 해당확인 전 학습/평가는 계속 보류한다. 새탭은 이전탭의 미저장draft를 공유하지 않는다. 소스/테스트 롤백은 artifacts/geometry-point-switch-20261017/review.before.html과 review_validation.before.cjs를 원래파일로 복원하되 이후수정이 있으면 해당diff만 되돌린다. 사용자 라벨파일에는 변경0.
