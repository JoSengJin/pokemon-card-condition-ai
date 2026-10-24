# 신규 앞면 두 실물 독립 시험 준비 — 0.4.81

개발 기반4/6(약67%). 새 독립 시험 점수는 사람 카드 영역 확인 전이라 미측정. 운영 Gemini 절감0건. 고정 후보와 기존 운영 모델은 변경하지 않았다.

## 입력과 사람 확인 범위

- ㅊ/light/img_3.png: 잉어킹 앞면440×580. 사용자 확인한 강한 중앙 하단 빛 반사, 해당 면 gradable0·glare·lower_center. 결함 종류는 미확인.
- ㅊ/img.png: 리자몽 앞면298×405. 요청한 새 정상 비교 사진에 대한 사용자 답변으로 해당 면 gradable1·관찰 제한 없음. 종류별 결함0은 추정하지 않는다.
- 서로 다른 신규 실물2장 요청에 대한 제공 자료. 기존69·독립2·최근4행의 모든 images 대비 픽셀 중복0. 별도 data/chieut-independent-review-20261012.jsonl/test에 등록. 이전 라벨 파일 불변.
- 지금 필요한 입력은 두 사진의 box_reviewed=true 카드 영역 확인뿐이다. 결함 위치·완료 라벨 재작성은 요청하지 않는다.
- http://127.0.0.1:8769/?card=%E3%85%8A-front-clear-test-2&geometry=front
- http://127.0.0.1:8769/?card=%E3%85%8A-front-glare-test-2&geometry=front
- 한 화면에서 저장한 뒤 다음 링크를 열어 최신 revision을 읽는다. 여러 탭의 오래된 상태로 저장하지 않는다.

## 변경 파일과 핵심 diff

- card_condition/review.html: 기본 train 영역 큐는 유지. 명시적으로 선택한 val/test의 미확인 해당 면은 관찰 제한 유무와 관계없이 영역 확인 허용. 라벨·분할 자동 변경 없음.
- tests/review_validation.test.cjs: 기본 시험 배제·명시적 시험 정상 면 허용·다른 면 거부·검토 완료 재요청 없음·입력 불변 검증.
- pyproject.toml0.4.81, README.md.
- data/chieut-independent-review-20261012.jsonl: 신규2행만 별도 등록.
- artifacts/chieut-independent-20261012/: registration.json·preflight.json·evaluate_after_review.py·차단 및 테스트 로그.
- CHIEUT_GLARE_TRAIN_VALIDATION_20261011.md: 이전 전체 테스트6오류와 수동 fixture 수정 후156통과를 정확하게 기록. tests/test_finite_logits.py 수정은0.4.80 fixture 호환 보완.
- 소비 프로젝트 CONDITION_ANALYSIS_TODO.md 상단에 완료·현 사람 의존 기록. 소비 운영 코드 변경 없음.

## 검증

- JS 회귀 검사 통과, 실제 브라우저 두 geometry 링크에서 해당 면 사진·영역 확인 체크·기존 면 라벨 표시 확인. 초기 저장 버튼 비활성은 수정사항이 없기 때문이며 영역 지정/확인 체크 뒤 활성화되는 기존 계약 유지.
- Python 전체156테스트45.875초 통과: artifacts/chieut-independent-20261012/tests.log.
- 원본 파서로 명시적 관찰 정답2면/두 클래스 검산, 등록 픽셀 해시 일치. 검토 전 실행기는 Human card geometry review pending으로 거부했고 test-source/evaluation 생성 없음.
- 후보 SHA72bfb760b1e01bb951966d0bc44535fa35c4af631c64f316a1e749fe3d4b307b 고정. 이전 학습·val·시험 이력 제외 검사와0.5 경계를 그대로 사용.
- 사용자 영역 저장 이후 PYTHONPATH=. OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TORCH_HOME=artifacts/torch-cache .venv/bin/python artifacts/chieut-independent-20261012/evaluate_after_review.py 실행. 두 영역 미확인/보호 원본 변경/사진 교체/시험 재실행 차단. 출력은 한 번만 생성하고 이 시험에 맞춰 후보·임계값을 다시 선택하지 않는다.

## 리스크·롤백

두 실물만으로 일반화를 주장할 수 없다. 정상 사진도 촬영 해상도 한계가 있으며 종류별 결함 정답과 관찰 가능 여부는 별개다. 이번 독립 정확도 상승은 미측정. wheel 설치 및 운영 채택은 수행하지 않음.

UI 롤백은 후속 변경 확인 후 .backups/independent-0481/review.html·review_validation.test.cjs·pyproject.toml 복원. 0.4.80 모델 지원면 변경은 .backups/prototype-0480/ 근거 참조. 신규 사진·사람 저장 라벨·실험 증거는 삭제하지 않는다. 운영 모델은 교체하지 않아 운영 복구 필요 없음.

에튜: test는 모델을 가르치는 자료가 아니라 처음 보는 입력에 대한 시험이다. 명시적인 시험 화면 열기와 train 자동 큐를 분리해, 시험 영역을 수정하려고 학습 분할로 옮기는 데이터 누수를 방지했다.

## 저장 확인 후 평가 연결 보완

사용자 저장본에서 리자몽 box_reviewed=true, 잉어킹은 좌표 변경·box_reviewed=false로 확인했다. 사용자가 잉어킹 영역을 다시 확인하겠다고 답했으므로 자동 확인 완료 처리하지 않는다.

두 사진에 추가한 전체 결함 라벨은 그대로 보존했다. 리자몽 전체 gradable1은 앞면 단독 입력에 대한 전체 앞뒤 검증 계약과 충돌한다. 원본 계약을 약화시키거나 사용자 저장을 고치지 않고, 연구용 face_projection에서 전체 labels만 null로 제외한다. side_annotations의 앞면 정답·좌표·관찰 제한·실물 ID·분할은 그대로 유지하며, raw-review-source와 투영본을 별도 동결한다. 이 원본 보존형 면별 입력 방식은 기존 면별 실험 계약을 재사용한다.

실제 저장본으로 projection-check.json 생성: 원본·면 주석 불변, 명시적 앞면 정답2/두 클래스, 확인 전 main 차단·시험 출력 없음. 변경은 artifacts의 실행기뿐이며 패키지 모델 추론 로직은 변경하지 않았다. 현재 독립 평가 및 정확도 변화는 미측정. 롤백은 실행기 face_projection과 투영/원본 보존 부분을 수정 전으로 되돌릴 수 있으나, 원본 전체 라벨 계약 충돌 해결 전 실행은 금지한다. 사용자 저장 라벨 삭제·복원은 하지 않는다.

## 독립 시험 완료

사용자가 잉어킹 재확인 후 저장 완료를 알려준 답변을 근거로 box_reviewed 한 필드만 반영하고 시험했다. 고정 후보 TP0/TN1/FP0/FN1·누락100%(1/1)·오탐0%(0/1), 채택 보류. 실제API 사람 반사 마스킹·Gemini검토 유지. 후속 train-only 공간 풀링도 누락4/4로 미채택. 상세는 CHIEUT_INDEPENDENT_VALIDATION_20261012.md. 다음은 새 실물의 반사 유무 비교 자료 제공 가능 여부의 사람 답변 의존이며 완료 라벨 재요청 없음.
