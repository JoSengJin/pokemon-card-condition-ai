# 모바일 전체 답 JSON 한 번 복사 — 2026-11-10

개발 진척78/100(usable-card-analysis-v1.13) 유지. 5건을 선택한 뒤 마지막 JSON 칸 하나만 복사하는 화면으로 개선했다. 스크립트/서버/터널/localStorage 없이 동작하도록 생성했다. 실제 휴대폰 CSS 동작은 미확인이다.

## 변경 파일·핵심 diff

- tools/diagnostics/mobile-point-review-20261110/scriptfree.py: 개별 JSON 칸을 제거하고 combined_outputs를 추가했다. 기본 라디오 버튼은 사진 아래 그대로 둔다. 가능한 4^5=1024가지 전체 선택에 대한 JSON을 미리 만들고 form:has CSS로 현재 선택과 같은 결과 하나를 표시한다. 아래 고정「마치고 JSON 보기」는 일반 앵커로 결과로 이동한다. 복사는 textarea 길게 누르기로 한다. 스크립트가 필요한 복사 버튼은 추가하지 않았다.
- tools/diagnostics/mobile-point-review-20261110/scriptfree_checks.py: 모든 1024조합의 선택→전체JSON 대조,이미지/크기/보호규약 검사.
- docs/collaboration/tasks/mobile-single-copy-20261110.md: 사전 계약·구조·검증.
- 이 보고서: 근거·제한·롤백.

선택 전은 responses에서 제외한다. 모르겠음은 unknown/point:null로 유지한다. 기존 구역 정답은 읽기 전용이고 이미 확인한 위치는 질문에서 빠진다. 출력 kind=surface_point_review_manual_draft는 기존 정밀점 validator에서 거부하므로 설명이나 point:null을 자동 좌표 정답으로 바꾸지 않는다. 자유 설명은 마지막 JSON의 location_description에 한 번 적는다. 사진별 입력을 자동 합친다고 표시하지 않는다.

## 실행 검증

검증 소스 b9e7442fdcf2ef2690d3613f94fa6ed8af34350c. ./develop -- .venv/bin/python tools/diagnostics/mobile-point-review-20261110/scriptfree_checks.py 통과. 1024개 JSON의 ID/사진SHA/기존 구역정답/새 선택/빈 설명/null좌표/선택전 제외를 전부 대조했다. CSS 선택자와 각 결과ID의 대응을 검사했다. 모든 초안은 정밀점 validator에서 거부됐다. 완료 항목 제외/5건 제한/고유ID/기본 라디오20개/지원하지 않는 CSS의 수동 전체JSON fallback도 검사했다. 기존 묶음의 crop/전체사진10개 dataURI가 동일하고 파일 크기는8MiB 미만이다. scriptfree.py 함수1→2,checks2→2;main→render→combined_outputs 또는crop_view 호출전이2다. 최초 검사에서 문자열join 오류를 발견해 수정한 뒤 전체 검사가 통과했다. 실제 모바일 렌더 검사가 아닌 정적 계약 검사다.

./develop -- .venv/bin/python tools/diagnostics/mobile-point-review-20261110/scriptfree.py로 artifacts/mobile-single-copy-20261110/review-02-onecopy.html 생성. 기존 파일/패킷8cca9f9bd206ac1ad04fe0ad395a71cfca47c43db3695ebbddf202979a1fad96 보존. 새학습/추론/사람정답0건,손실가중치/모델/평가기준 변경0. 모델 성능 개선 미평가.

## 리스크·사용법

선택을 마친 뒤 하단「마치고 JSON 보기」→요약 확인→필요한 위치 설명 작성→textarea 길게 눌러 전체선택/복사→채팅에 한 번 붙여넣기. 선택을 다시 바꾸면 다른 미리 만든 초안이 표시되며 기존 설명이 자동 이동하지 않는다. 설명은 선택을 마친 뒤 적는다. 새로고침/닫기 전 복사가 필요하다.

CSS :has 미지원 뷰어는 자동 묶기가 불가능하므로 전체JSON 수동 입력 칸과 경고를 표시한다. 그 칸의 judgment:null을 정상/결함으로 자동 추정하지 않는다. 실제 폰에서 선택 요약과 결과 하나가 표시되는지 아직 확인이 필요하다. 스크립트 없는 화면에서는 클릭 좌표/자동 저장을 제공하지 않는다. 파일 크기 증가는 같은5건의 전체 선택 JSON 사전 생성 때문이다.

## 롤백

./develop -- git revert b9e7442fdcf2ef2690d3613f94fa6ed8af34350c 로 이번 두 소스 변경만 되돌린다. 이전 HTML/사진/사람응답/패킷은 보존한다. 열기 요청 결과와 원격 반영 SHA는 ignored 산출물 opening-status.txt/remote-sync.json에 별도 기록한다.

열기 결과: macOS open exit0. 열기 요청 수락,실제 렌더링/폰 조작 미확인. 실제 생성 파일6,294,974bytes(6.003MiB).
