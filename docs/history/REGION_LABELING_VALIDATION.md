# 면별 라벨 및 카드 영역 지정

- 변경: card_condition/review.py, review.html, README.md.
- 추가: card_condition/regions.py, tests/test_regions.py.
- side_annotations.front/back: image 경로, 정규화 box [left,top,right,bottom], 5개 0/1/null labels.
- 기존 전체 카드 라벨 보존, 새 면별 라벨 자동 생성/복제 없음. 사진 선택 변경 시 UI에서 관련 면별 정보 초기화. API에서 다른 사진에 붙은 라벨 거부.
- 좌표 범위/순서/NaN/bool 및 label 검증. 영역은 카드 전체의 직사각형이며 원근 보정이나 개별 결함 위치를 뜻하지 않음.
- 테스트 14개 통과. 합성 사진 UI에서 좌표 10/10/90/90 및 앞면 모서리1 저장 후 새로고침과 파일 값 확인. 기존 전체 모서리 null 유지 확인.
- 현재 학습기는 새 면별 라벨과 box를 사용하지 않는다. 사람의 면별 관찰/영역 데이터 확보 후 crop/타일 학습 계약을 추가해야 함. 정확도 개선 주장 없음.
- 실데이터 라벨 파일은 개발 중 수정하지 않음. 저장할 때 기존 백업 동작 유지.
- 롤백: .backups/step5의 review.py, review.html, README.md를 원위치에 복원하고 서버 재시작. 추가 regions.py/tests는 제거 가능. 이미 저장한 side_annotations는 파일에 남겨도 기존 모델에 영향 없음.
