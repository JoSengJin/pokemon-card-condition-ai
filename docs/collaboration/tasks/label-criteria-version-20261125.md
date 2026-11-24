# 라벨·판정에 기준 문구 버전과 사진 조각 해시 기록 (`label-provenance`) — task 계약 초안

```text
task_id: label-criteria-version-20261125
owner: 미배정
status: blocked (사용자 진행 결정 전. 초안이며 구현하지 않았다)
base_sha: 배정 시점의 검증된 origin/main
branch: 미정
goal: 새로 저장하는 사람 라벨·AI 판정마다 기준 문구 버전과 그때 보여 준 사진 조각의 SHA-256이 함께 남고, 기존 라벨은 그대로 읽힌다
allowed_files: 배정 때 아래 "영향 범위"를 다시 조사해 정확히 고정
forbidden_files: data/, artifacts/, 사람 라벨·정답·평가 자료, 과거 HTML, 학습·추론 코드
experiment: 없음
```

## 왜 바로 구현하지 않았나
- `card_condition/regions.py`의 `validate_annotations`는 면별 라벨의 키를 정해진 목록으로 막는다. 새 칸을 넣으면 이 검사와 저장·표시·학습 입력 조립 코드가 모두 영향을 받는다.
- 전화 화면의 답 문자열(`ID/면=상태;box:…;구역:상태`)에는 버전·해시 칸이 없다. 형식을 바꾸면 이미 받은 답과 가져오기 도구가 어긋난다.
- 과거 라벨 파일은 바꿀 수 없다(소급 금지). 새 칸은 선택 칸이어야 한다.

## 계약 초안
- 버전 = 화면이나 지시서에 실제로 들어간 기준 문구의 SHA-256. 사람이 붙이는 이름은 쓰지 않는다(문구가 같으면 같은 버전, 한 글자라도 다르면 다른 버전).
- 사진 조각 해시 = 화면에 넣은 이미지 바이트(모서리 화면은 base64로 넣은 JPEG)의 SHA-256. 원본 사진 해시는 기존 `image_sha256`을 그대로 쓴다.
- 저장 위치 두 안:
  - **안 A(권장)**: 라벨 파일을 건드리지 않고, 화면을 만들 때 `<화면>.criteria.json`(화면 SHA, 문구 SHA, 대상 ID→사진 조각 SHA)을 새로 만든다. 가져오기는 답과 이 파일을 대조해 ID가 다르면 거절하고, 결과 옆에 "ID→버전" 표를 새 파일로 쓴다. 라벨 저장 형식·기존 호환 영향이 없다.
  - 안 B: 면별 라벨에 선택 칸 `criteria`를 추가. `validate_annotations`와 모든 호출자를 바꿔야 한다.
- 과거 판정은 "버전 미상"이다. 추정해 채우지 않는다. 일치율·누락·오탐 보고는 버전별 분모를 나눠 적고, 버전이 다르다는 이유로 정답을 바꾸지 않는다.

## 영향 범위 (2026-11-25 코드에서 확인, 배정 때 재조사)
- 만들기: `tools/*label*_pages*.py`, `tools/relabel_*_page*.py`, `tools/ebay_back_label_pages.py`
- 가져오기: `tools/mobile_*_label_import.py`
- 검사(안 B만): `card_condition/regions.py` `validate_annotations`와 그 호출자
- AI 판정 저장 형식은 저장소에 추적 코드가 없어 조사하지 못했다(미확인).

## checks (초안)
- 새 화면 → 답 → 가져오기 왕복에서 버전·해시가 보존된다(`tests/test_corner_label_round_trip.py` 방식).
- 문구 한 글자 변경 시 버전이 달라진다. 다른 화면의 답을 넣으면 거절한다.
- 버전 파일이 없는 과거 답은 지금과 똑같이 가져오고 "버전 미상"으로 표시한다.

## 사용자가 정할 것
1. 진행 여부. 2. 안 A/안 B. 3. 사람 라벨부터 할지 AI 판정까지 함께 할지.

## 롤백
안 A는 새 파일만 추가하므로 커밋 revert로 끝난다. 안 B는 새 칸이 들어간 라벨이 저장된 뒤에는 revert만으로 읽히지 않을 수 있다.
