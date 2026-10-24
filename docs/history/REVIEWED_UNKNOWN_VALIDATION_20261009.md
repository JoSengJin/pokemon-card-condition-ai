# 미확인도 검토 완료로 저장 — 2026-10-09

## 저장 확인 결과와 재학습 결정

사용자 저장 후 `data/learn-review.jsonl`을 확인했다. v의 앞뒷면 관찰 정보가 변경됐고 back에는 glare/perspective가 기록됐다. 요청한 v/back lower_right surface_defect는 null 유지. y/back lower_left surface_defect와 ebay-50f5e8124d55bb/back upper_right edge_defect도 null이며 별도의 검토 완료 표시는 없었다. null만으로 검토를 안 했다고 판단하지 않는다.

`region_rows`로 최신 저장 파일과 이전 `regions-labeled-20261009-efficient-round1.jsonl`의 모든 train/val 구역을 비교했다. id·group·split·box·labels·image_sha256가 같고 양쪽123구역이었다. 따라서 새 결함/정상 학습 정답이나 학습 입력 변화가 없어 동일 재학습은 수행하지 않았다. 기존 모델 성능을 새로운 개선 결과로 주장하지 않는다. t의 split 미지정도 유지했다.

## 변경 파일 / 핵심 diff

- `card_condition/regions.py`: 선택 주석 `region_reviews` 추가. 3×3 위치→검토한 결함 종류 목록. 유효한 카드 영역·위치·종류·중복 여부를 검증한다. 기존 region_labels와 독립이며 null/0/1 정답은 그대로다.
- `card_condition/review.html`: 후보 확대 화면에 검토 완료 체크 추가. 미확인 상태도 완료로 저장 가능. 완료 기록은 정상 후보 선정에서 제외하며 카드 영역 변경 시 초기화한다. 사진 변경 시에는 기존 주석 초기화 경로를 따른다.
- `card_condition/region_review_plan.py`: 완료한 면/종류는 다른 위치로 바꿔 반복 요청하지 않는다. 이미 기록한 관찰 제한 v는 기존 제외 규칙으로 처리한다.
- `tests/test_regions.py`: 주석 저장·내보내기 영속성, null 불변, 불가능한 위치/종류/중복 차단.
- `tests/test_region_review_plan.py`, `tests/review_validation.test.cjs`: 완료한 미확인이 후보에 다시 나타나지 않고 정답0을 만들지 않는지 검증.
- `README.md`, `pyproject.toml`: 기능 설명과0.4.5 버전. 소비 프로젝트 TODO는 진행 기록만 변경.

## 실행 검증

Python 전체39개 및 JS 회귀검사 통과. 라벨 저장 버튼 비활성으로 미저장 입력이 없음을 확인한 후 기존 서버 실행 명령을 확인하고 같은 파일/포트로 재시작했다. 새 서버는 localhost:8766. 실제 y/back lower_left 표면 확대·초점·검토 완료 체크 표시를 확인했다. 실제 사용자 정답/검토 완료 기록을 에이전트가 대신 저장하지 않았다.

사람 확인이 남은 것은 y와 ebay-50f5e8124d55bb 두 후보의 완료 여부다. 이미 확인했지만 미확인으로 남긴 경우 새 체크만 하고 라벨 저장하면 된다. 상태를 다시 정상/결함으로 강제 판정할 필요가 없다. v는 다시 확인 요청하지 않는다. 저장 후 새 정답이 생긴 경우에만 동결 snapshot과 같은 조건 재실험을 진행한다.

## 리스크 / 롤백

0.4.5 wheel 빌드 및 regions/region_review_plan/review.html의 소스 일치 확인 완료. SHA256 `57160c04659323195b90e0c1c4ae151a426f561cbea9d2013af453af4107ecb3`. 새 가상환경 설치 검증은 미실행.

완료는 작업 상태이며 학습 정답/평가 가능성/정상 보증이 아니다. 완료한 종류를 재보강할 필요가 생기면 기존 후보 바로가기에서 체크를 해제하고 저장할 수 있다. 카드 영역 변경은 완료 기록을 초기화하므로 새 위치에서 재확인이 필요할 수 있다. 기존 정상0/결함1 라벨은 자동 변경하지 않는다.

이 필드를 모르는 구버전은 새로운 주석을 거부한다. 안전한 UI 롤백은 region_reviews 허용 검증을 유지한 채 확대 화면의 완료 체크 및 후보 제외 로직만 되돌리는 방식이다. 구버전 wheel로 완전히 돌아가야 한다면 최신 라벨 원본을 보관하고 별도 복사본에서 region_reviews만 제거해야 한다. 원본 전체를 이전 백업으로 덮어쓰면 이후 사람이 입력한 정답을 잃을 수 있으므로 하지 않는다. 운영 모델·Gemini 호출 경로는 변경하지 않았고 실제 호출 절감0건이다.
