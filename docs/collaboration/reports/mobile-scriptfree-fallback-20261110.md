# 스크립트 없는 모바일 대체본 — 2026-11-10

개발 진척78/100(usable-card-analysis-v1.13) 유지. 실제 폰 문제 해결은 미확인. 스크립트 초기화를 기다리지 않는 5건 대체본을 만들었다.

사용자 원문: “입력준비전 노출됨”. 입력 준비 완료 상태에 도달하지 않은 것은 확인됐다. 스크립트가 차단됐는지, 실행 전 구문 오류인지 원인은 확정하지 않았다. 사람 판정/새 라벨로 저장하지 않았다.

## 변경 파일·핵심 diff

- tools/diagnostics/mobile-point-review-20261110/scriptfree.py: 추가한 단일 render 함수. 기존 crop_view를 재사용하고 기본 라디오 버튼과 CSS 형제 선택자로 선택한 수동 JSON 초안만 표시한다. JS·SVG·외부 이미지·서버·터널·localStorage 없음. 정밀 클릭 좌표/자동 기록/다운로드는 제공하지 않으며 제한을 화면에 명시했다. 이전 interactive 화면은 그대로 보존했다.
- tools/diagnostics/mobile-point-review-20261110/scriptfree_checks.py: 정적 HTML·이미지·라벨 보호 검사. 2개 메서드.
- docs/collaboration/tasks/mobile-scriptfree-fallback-20261110.md: 사전 범위와 체크포인트.
- 이 보고서: 결과·제한·롤백.

기존 구역 정답은 읽기 전용이다. 새 선택은 사용자가 직접 설명할 위치에만 해당하며 미확인/모르겠음을 이진 정답으로 추정하지 않는다. kind=surface_point_review_manual_draft는 기존 surface_point_review_answers와 구분되고, 기존 정밀점 validate 함수에서 거부된다. point:null인 설명 초안을 실제 손상 좌표로 자동 승격하지 않는다. 채팅으로 준 설명도 원문으로 보존하고 위치가 모호하면 필요한 부분만 확인한다.

## 실제 실행 검증

검증 소스 61c6a7ba374ca9818e6260ae5d786d4a0839ccf1. ./develop -- .venv/bin/python tools/diagnostics/mobile-point-review-20261110/scriptfree_checks.py 통과: 5건/10개 내장 이미지가 이전 review-02의 crop/전체 이미지와 동일;script/SVG/iframe/form0;라디오20개,초기선택5개 모두null;JSON초안20개 모두 정밀점 validator에서 거부;이미 끝난 위치 제외;5건 초과 거절;CSS sibling selector 규칙·고유ID 확인. 함수수1/2, main→render→crop_view 호출 전이2. CSS 실제 기기 동작은 미확인이다. 이는 모델 성능 검사나 실제 브라우저 렌더 검사가 아니다.

./develop -- .venv/bin/python tools/diagnostics/mobile-point-review-20261110/scriptfree.py 로 artifacts/mobile-scriptfree-fallback-20261110/review-02-scriptfree.html 생성. 같은5건만 제공한다. 사용자 폰 확인 전 다른63묶음을 다시 생성하지 않는다. 모델/손실/기준/원래 라벨 변경0,새학습·추론0. 기존 미판정은 그대로 유지한다.

## 리스크·전달

폰 뷰어가 기본 HTML 입력까지 막는지는 아직 모른다. CSS가 제거되면 초안이 모두 보일 수 있으므로 각 초안에 선택 상태를 적었다. 이때는 번호와 문장으로 채팅에 답해도 된다. 수동 설명은 JSON의 location_description에 직접 적어야 하며 선택 변경 시 다른 초안에 자동 복사되지 않는다. 새로고침/닫기 전 채팅에 전달해야 한다. 자동 기록 버튼·동적 좌표 계산을 지원한다고 주장하지 않는다. 서버/보안 우회도 없다.

## 롤백

./develop -- git revert 61c6a7ba374ca9818e6260ae5d786d4a0839ccf1 로 두 도구 추가만 되돌린다. 기존 사진/HTML/사람 응답/평가 기록은 보존한다. 이전 interactive 화면과 JSON 규약에는 변경이 없다.

산출물 postflight.json/checks.log/status.html. macOS open의 결과는 opening-status.txt에 별도 기록하며 실제 폰 렌더와 구분한다.

열기 결과: macOS open exit0,요청 수락. 실제 렌더링/폰 조작은 미확인.
