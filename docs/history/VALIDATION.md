# 실행 검증 — 2026-10-07

- Python 3.12.14, torch 2.14.1, torchvision 0.29.1, Pillow 12.3.0. 전체 버전은 requirements-tested.txt.
- `python -m unittest discover -s tests -v`: 6개 통과.
- 누락 면, 잘못된 라벨, group/이미지 split 누출, 미학습 head의 null, backbone 고정, checkpoint 왕복, 가상 호출 절감의 결함 누락 검증 포함.
- `pip check`: No broken requirements found.
- editable 설치 및 wheel 빌드 통과. dist/pokemon_card_condition-0.1.0-py3-none-any.whl.
- 공식 MobileNetV3 Small 가중치 다운로드 후 합성 데이터 1 epoch CPU 학습·test 평가·MPS 추론 성공. 임시 실험 가중치는 삭제됨.
- 사용자 learn 폴더 PNG 6장 모두 이미지 로딩·224px 전처리 성공.
- data/learn-review.jsonl: 3개 그룹, 6장. 사람 라벨/면/분할은 미지정, 학습용으로 아직 유효하지 않음.
- 실제 카드 상태 정확도/실매물 학습/Gemini 비교/운영 연동은 미실행. Gemini 호출 및 실제 호출 절감 모두 0.
- 모델 입력 224px와 전체 이미지 특징의 한계로 미세 결함 정확도는 별도 검증 필요.

변경 파일: pyproject.toml, .gitignore, card_condition/{__init__,data,model,cli}.py,
tests/test_pipeline.py, labels.example.jsonl, README.md, requirements-tested.txt, VALIDATION.md.
런타임 산출물: .venv/, artifacts/torch-cache/, data/learn-review.jsonl, dist/.
기존 PokeCollector는 CONDITION_ANALYSIS_TODO.md에 위치/진행상황만 추가했으며 운영 코드·DB는 수정하지 않음.
롤백: 독립 폴더를 보관/삭제하고 PokeCollector TODO의 2026-10-07 진행상황 블록만 제거.

## 0.2 실행 검증 — 2026-10-08

- `unittest discover`: 10개 통과. 실제 HTTP GET/POST, 이미지 제공, 외부 origin 차단, 경로 제한, 저장/백업, revision 충돌, export, 준비상태 검증 포함.
- 처음 발견한 /tmp→/private/tmp 경로 정규화 차이를 로더에서 수정한 뒤 전부 통과.
- 실제 learn 사진으로 localhost:8766 화면 로딩 및 a→b 이동·사진 표시·라벨 선택 UI 확인. 실제 사진의 사람 라벨은 변경하지 않음.
- 신규: card_condition/review.py, card_condition/review.html, tests/test_review.py.
- 수정: card_condition/data.py (공통 학습 준비 검사), model.py (검사 재사용), cli.py (review/check), pyproject.toml (0.2 및 HTML 포함), README.md, VALIDATION.md, .gitignore.
- 위험/한계: 모델 정확도 검증은 여전히 미완료. 원본 사진 경로가 이동되면 인벤토리 경로 수정 필요. 로컬 화면은 단일 사용자용.
- 기존 코드 백업: .backups/step2/. 라벨 데이터 복원은 원본 JSONL 옆의 시각별 .bak 사용.
