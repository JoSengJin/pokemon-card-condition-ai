# 반사 앞면 추가 학습 자료 준비

사용자 learn/ㅊ/light/img_2.png(406×560) 제공. 기존 live69행·독립eBay2행·ㅊ3행 이미지 decoded RGB 비교 중복0. 신규 학습 실물ㅊ-light-train-2를 train으로 예측 전에 지정. 사용자 확인 센터링 우상 쏠림1/앞면 엣지0/모서리0, 중앙 glare/표면 미확인만 반영. 뒷면·구역별 정답은 추정하지 않음.

변경: data/chieut-review-20261011.jsonl 신규1행(3→4), artifacts/chieut-glare-train-20261011/{before.jsonl,registration.json,plan.json,run_after_geometry.py}, 본 문서, 소비 TODO상단. 기존3행 정확히 보존·live/독립/시험보고 해시 불변·ReviewStore 및 train manifest 로드 통과. 코드 버전/모델 변경 없음.

학습 계획은 이전 고정 특징/클래스실물 가중/고정0.5 및 nested 경계 알고리즘 그대로 새 train실물1개만 추가. 비교는 동일 기존23학습면을 대상으로 두 알고리즘의 FP/FN과 %p를 각각 계산한다. 새24면 총합은 보강 전23면과 직접 개선 비교하지 않음. test·val로 기준/후보 선택하지 않으며 체크포인트 저장/운영 채택 없음.

카드 box는 임시 전체 사진, box_reviewed=false. 사람 영역 확인 전 재현 스크립트 학습 거부 실제 확인(exit1). 현재 최초 학습/성능 비교는 아직 실행하지 않았다. 8768서버는 이미 실행중이어서 두번째 시작은 address in use로 종료, 기존 서버를 그대로 재사용해 브라우저 신규카드·정답·train·영역입력 확인. 임의 서버 중단 없음.

리스크: 중앙 반사는 카드 불량이 아니라 관찰 제한. 기존 학습묶음 재사용 연구라 일반화 주장 불가. 롤백은 before.jsonl과 현재 비교 후 신규행만 격리하고 후속 사용자 저장 보존. 전체 파일 덮어쓰기 금지. 원본 사진·모델·소비 운영 수정 없음. 개발기반4/6, 정확도 변화 측정 전·Gemini절감0.

## 저장 후 실행 기록

사용자 영역 저장(box_reviewed=true)을 확인해 예정 실험을 실행했다. 당시 glare_areas는 빈 목록으로 저장됐으며 수정하지 않았다. 이번은 면 단위 반사 분류이므로 위치 라벨을 요구하지 않는다. 현재 결과는 CHIEUT_GLARE_TRAIN_VALIDATION_20261011.md를 따른다.
