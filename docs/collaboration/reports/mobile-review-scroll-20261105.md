# 모바일 검토 답 저장·스크롤 구조 수정 — 2026-11-05

진척 78/100(v1.13) 유지. 사용자가 회신한 선택 3구역 답을 정확한 결과 SHA/번호/종류/구역에 연결해 저장했다. 모델/평가 기준 변경이나 새 성능 개선이 아니다.

## 변경 파일·핵심 diff

- `tools/mobile_assisted_review_page.py`: 신규 생성기. 선택 radio를 각 사진/질문의 fieldset 안에 보이는 normal flow로 배치. 기존 페이지 맨 위 offscreen radio로 label 클릭의 포커스가 이동하던 구조 제거. JavaScript 없이 CSS :has로 미리 작성한 64개 응답 중 해당 결과를 표시하며, 미지원 뷰어는 직접 입력 안내를 보여준다. 기존 답은 기본값으로 보존하고 이전 HTML 덮어쓰기를 거부한다.
- `tests/test_mobile_assisted_review_page.py`: 입력이 자기 질문 안에 있는지/보이는 normal flow인지/자동 focus 또는 스크롤 코드가 없는지, 64개 결과/미확인/모르겠음/고정 매핑, 확인 답 기본값 보존/이전 HTML 덮어쓰기 거부/모델 결과 SHA 불일치 거부 검사.
- `F2_PILOT_PREPARATION.md`: 이후 보조 검토 HTML은 이 생성기로 만들도록 실행 경로 명시. 별도 앱/서버 구현 아님.
- `docs/collaboration/tasks/mobile-review-scroll-20261105.md`, 본 보고서: 계약·실제 검사·미검증·리스크·롤백.
- ignored 사용자 자료: 같은 case의 human-response.json/review-map.json/status.json, 새 copy-review-v3.html/report-reviewed.html/scroll-fix-report.html/scroll-fix-checks.json. 원본 사진/추론 결과와 기존 v1/v2 HTML 보존, 답 원문은 Git에 넣지 않는다.

## 근거와 실제 검증

기존 v2는 12개의 radio를 body 맨 앞에 1px/offscreen으로 두고, 뒤쪽 질문의 label이 그 input에 연결됐다. Android가 label 클릭 때 상단 input으로 초점을 옮길 수 있는 구조다. 사용자 보고와 맞는 코드 원인이지만 실폰의 focus/scroll 이벤트를 계측해 재현한 것은 아니다.

검증 소스 커밋 `be35079`. `.venv/bin/python -m unittest discover -s tests -p 'test_mobile_assisted_review_page.py'`: **3개 OK / 0.008초**. CLI로 v3 HTML을 실제 생성했고, 기본값이 이미 회신한 답과 같음·기존 결과 SHA 불변·함수 수(generator 3/test 4)·diff-check를 확인했다. 새 프로젝트 호출은 main→load_review/page이고 모델 호출 경로를 추가/수정하지 않는다. Python stdlib 내부 전체 호출 그래프를 새로 인증한 것은 아니다.

사용자 답은 review_id/result_sha256와 선택 키를 정확히 대조하고 저장했다. 이번 원문 회신은 화면 캡처로 임시 복원했던 선택보다 우선하며, 모델과 다르다는 이유로 바꾸지 않았다. 선택 3구역 외 18구역과 관찰 제한의 사람 정답은 unknown, 학습 사용은 false다. 전체 카드 정상/결함 또는 독립 평가 정답으로 확대하지 않는다. FN/FP/분모/%p 성능 재계산 없음.

## 미실행·리스크

실제 Android에서 새 HTML 선택 시 scrollY/focus 동작과 CSS :has 지원은 재검증하지 않았다. 브라우저 도구의 file URL 정책이 차단돼 있어 같은 동작의 우회/다른 브라우저/서버 개방으로 렌더하지 않았다. 로컬 구조/직렬화 회귀 검사를 실제 기기 통과로 쓰지 않는다. CSS :has를 지원하지 않는 뷰어에서는 직접 입력이 필요하다.

새 모델 추론/학습/외부 AI/설치·복구/전체 테스트 미실행. 기존 모델의 6전이 경로와 F1/F2 미완료를 해소한 변경이 아니다. 현재 input 배치 원인을 제거했지만 모든 모바일 환경에서 스크롤이 절대로 바뀌지 않는다고 인증하지 않는다.

## HTML·롤백

사용자 검토 v3와 결과 반영 보고서는 ignored case 폴더에 둔다. 성과·진척 HTML은 `artifacts/codex-mobile-review-20261105-golem/scroll-fix-report.html`. 생성/정적 내용 대조 완료, file URL 정책 차단으로 열기·렌더 미확인. 사용자 검토는 이미 완료했으므로 답 재요청 없음.

롤백은 잠금/진행 실행 확인 후 `./develop -- git revert be35079`로 생성기/검사를 되돌리고 관련 검사·일반 push. 문서 커밋은 필요 시 별도 revert. 사용자 답 기록은 버그 수정과 별개이며 되돌리거나 삭제하지 않는다. 일반 push 후 원격/local SHA는 최종 인계와 ignored scroll-fix-sync.json에 기록한다.
