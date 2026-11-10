# 모바일 클릭 보완 — 2026-11-10

개발 진척 78/100(usable-card-analysis-v1.13) 유지. 모바일 포인터 터치와 스크립트 준비 상태 표시를 보완했다. 실제 휴대폰 문제 재현·해결은 미확인이다.

## 변경 파일과 핵심 diff

- tools/diagnostics/mobile-point-review-20261110/review.js: 짧은 포인터 터치로 좌표 선택, 드래그·취소·긴 누름 제외, 뒤따르는 click 중복 방지, click 전용 입력 유지. 초기화 성공 뒤에만 입력을 활성화하고 실패 시 오류를 표시한다.
- tools/diagnostics/mobile-point-review-20261110/review.py: 상단 준비 상태, 초기 disabled 입력, 사진 스크롤/확대 허용 CSS.
- tools/diagnostics/mobile-point-review-20261110/build.py: 별도 출력 경로 지원. 이전 HTML은 보존한다.
- tools/diagnostics/mobile-point-review-20261110/checks.py: 새 회귀 검사 연결 및 정적 초기 상태 검사.
- tools/diagnostics/mobile-point-review-20261110/touch_checks.cjs: 실제 production JS를 NodeVM 합성 DOM에서 시작해 버튼→터치→기록→JSON 흐름 검사.
- docs/collaboration/tasks/mobile-point-touch-fix-20261110.md: 작업 범위·검사·미확인 사항.
- 이 보고서: 실행 결과·위험·롤백 기록.

## 실행 근거

검증 소스 2d34c61457fc2817028f20a83469e0197408bf3d. artifacts/mobile-point-touch-fix-20261110/checks.log의 Python/Node 합성 검사는 통과했다. 정상 초기화·오류 초기화, 선택→좌표→기록→JSON, 스크롤/드래그·취소·긴 누름·중복 click·click 전용·TextNode 입력을 검사했다. production JS 함수 7개, 신규 합성 fixture 6개다. 이는 브라우저나 실제 폰 검사와 다르다.

./develop -- .venv/bin/python tools/diagnostics/mobile-point-review-20261110/build.py artifacts/mobile-point-touch-fix-20261110 실행 완료. 63파일/313건, 파일당 최대 5건. postflight.json과 추가 정적 대조에서 모든 이미지 태그와 packet.json 바이트가 이전 버전과 동일했다. 새 파일 review-02-touch-fixed.html은 review-02의 동일 내용 사본이며 이전 파일과 혼동을 줄이기 위한 이름이다.

새 학습·추론·사람 정답 생성·손실 가중치 변경은 0건이다. 패킷 8cca9f9bd206ac1ad04fe0ad395a71cfca47c43db3695ebbddf202979a1fad96과 JSON 규약, 미확인/완료 라벨 보호는 유지된다. 성능 개선은 평가하지 않았다.

## 리스크·남은 의존

사용자의 무반응이 사진에만 발생했는지 모든 버튼에 발생했는지 아직 답을 받지 못했다. 기존 click만 처리하던 코드와 준비 상태 부재를 확인했지만 실제 원인은 확정하지 않았다. 상단이 ‘입력 준비 전’에 머물면 스크립트가 시작되지 않았거나 초기화하지 못한 상태다. 해당 뷰어의 스크립트 실행 여부는 이 HTML만으로 보장할 수 없다. 보안 설정·외부 서버·터널 우회는 하지 않았다. 실제 폰에서 준비 표시와 터치/기록 확인이 필요하다. 드래그 8px/800ms 기준 때문에 길게 누르거나 많이 움직인 터치는 점으로 기록되지 않는다.

## 롤백

./develop -- git revert 2d34c61457fc2817028f20a83469e0197408bf3d 로 UI 소스 변경만 되돌린다. 사람 응답과 이전 HTML·패킷은 삭제/변경하지 않는다. 새 파일을 열기 전 기존 입력이 있으면 JSON으로 보관한다.

열기 결과: macOS open으로 새 검토 파일과 status.html 열기 요청 exit 0. 실제 렌더링·폰 동작은 미확인. artifacts/mobile-point-touch-fix-20261110/opening-status.txt에 기록했다.
