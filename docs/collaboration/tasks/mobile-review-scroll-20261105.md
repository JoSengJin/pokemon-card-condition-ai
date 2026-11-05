task_id: mobile-review-scroll-20261105
owner: Codex
status: implementing
base_sha: 8bfb16050989668ad4ebd3f8d299a156368c8aa9
branch: main (직렬 구현/통합; 다른 task 소유 파일 수정 없음)
goal: 다음 보조 검토 HTML의 선택 input을 실제 질문 위치에 두어, 페이지 위쪽 숨김 input으로 포커스가 이동하는 구조를 없앤다.
allowed_files: tools/mobile_assisted_review_page.py, tests/test_mobile_assisted_review_page.py, 이 계약, docs/collaboration/reports/mobile-review-scroll-20261105.md. ignored artifacts/codex-mobile-review-20261105-golem/ 아래 사용자 답/지도/상태/새 v3 HTML/검증 기록.
forbidden_files: 다른 task 소유 소스/문서, 모델·worker·평가 기준·진척 점수·기존 라벨/사진 원본·실험·PokeCollector. 기존 v1/v2 HTML은 증거로 보존.
contract: 사용자 JSON은 review_id·result_sha256·번호/종류/구역 키를 정확히 대조해 한 번 저장. 모델과 다른 사람 답 그대로 유지. 현재 선택 3개 외의 구역은 unknown. 새 학습/추론/분류 성능 계산 없음. 다음 HTML은 JavaScript 없이 동작하고 실제 질문 안의 보이는 native radio 사용. 자동 focus/scrollIntoView/선택으로 hash 이동 없음. CSS :has 미지원이면 직접 입력용 fallback이 보이며 틀린 답을 자동 생성하지 않음.
structure: generator 신규 함수 3개(load_review/page/main), tests 신규 메서드 최대4개. main→load_review/page 이후 표준 라이브러리 호출뿐, 새 프로젝트 호출 계층 최대1전이(표준 직렬화/해시까지2), model inference 경로 변경 없음.
checks: 선택 input의 질문별 위치/보이는 normal flow, 64개 CSS 출력 조합/미확인·모르겠음·고정 metadata, 원본 결과 SHA 불일치 거부/기존 HTML 덮어쓰기 거부. 실제 폰 스크롤 재검증은 별개이며 미실행 시 명시. git diff --check, 관련 합성 테스트. 사용자 답/기존 모델 결과 SHA 보존.
HTML: 새 artifacts/codex-mobile-review-20261105-golem/copy-review-v3.html (이미 입력한 답을 기본값으로, 재요청 없음). 기존 report.html은 선택3개만 사람 답을 표시하고 미확인18개 유지. 성과/진척/검증 근거는 ignored scroll-fix-report.html. 내장 브라우저 file URL 정책 차단으로 렌더/실폰 검증은 주장하지 않음; 우회/서버 개방 없음.
experiment: 없음. ground truth 저장은 사용자 명시 답의 기록이며 학습/독립 평가/전체 카드 정상 판정 아님.
risks: CSS :has가 미지원이면 fallback 직접 입력 필요. 폰 브라우저의 실제 스크롤 동작은 구조/회귀 검사만으로 완전 인증하지 않음.
rollback: 이번 소스 커밋만 ./develop -- git revert <SHA> 후 관련 검사/일반 push. 사용자 답은 버그 수정과 독립해 보존하고 되돌리지 않음.
