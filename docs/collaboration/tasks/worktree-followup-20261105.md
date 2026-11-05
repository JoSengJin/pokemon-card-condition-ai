# 보류 worktree 19개 확인과 조건부 통합

task_id: worktree-followup-20261105
owner: Codex
status: integrated (32KB 수정 통합·207개 mock 회귀 완료; 나머지 항목은 보고서의 보류/사용자 결정으로 인계)
base_sha: 0082ca9e0b58126aa0bb64b42cd4662843cf7926
branch: main (기존 전달 브랜치의 검토·직렬 통합)
approval: 사용자 2026-11-05 요청. pair-control worktree 두 곳은 읽기·수정·정리 금지. 나머지 19개 확인 후 항목별 검증된 변경만 통합. worktree remove/prune·브랜치 삭제·서버 조작·실험·학습·외부 AI 호출 금지.
goal: 19개 각각의 main 대응·통합 판단·보류 이유·사용자 결정·미검증을 남기고, 현재도 재현되는 32KB 중복 입력 수정만 회귀 검증 후 통합한다.

allowed_files: card_condition/cross_review_auto_context.py, tests/test_cross_review_correct_input.py, docs/collaboration/tasks/review-correct-input-20261025.md, docs/collaboration/tasks/adopt-train-batches-20261031.md, 이 계약, docs/collaboration/reports/worktree-followup-20261105.md. ignored artifacts/worktree-followup-20261105/ 아래 감사 JSON·diff·검사 로그·index.html.
forbidden_files: 제외된 두 worktree 전체, 다른 worktree 편집, 기존 사진·라벨·manifest·모델·실험·review 설정·진척 기준·점수·PokeCollector.

contract: 원본 0ce69d886576927264b3bcb1bbafcfa4cae46098의 +7줄과 테스트·인계 문서를 검토한다. 현재 함수에 동일 cohort의 id/acceptance 집합만 결과 표 참조로 대체하며 기준이 다르면 유지한다. 32000바이트 상한·차단·기록·모델 호출 정책은 그대로다. 과거 응답 재사용 프롬프트 구성은 교정 오류만 합성이므로 과거 정확한 호출 replay나 실제 correct 응답으로 주장하지 않는다.

structure: cross_review_auto_context.py 함수 1→1, 신규 최상위 함수 없음. 신규 테스트 3개 메서드(context helper와 테스트 2개). 새 호출은 같은 함수 안의 json.dumps/sorted에 한정하며 기존 동적 경로의 구조 준수 전체를 새로 인증하지 않는다. 다른 후보의 monolithic review.html과 10개 함수 테스트는 구조 제한을 통과한 것으로 보지 않는다.

checks: 기본 checkout tracked/index 변경 없음·기존 .claude/ 미추적 상태 보존, main/origin 기준, 잠금 안 cherry-pick -x. 새 2개 테스트 및 관련 cross_review mock 회귀. 기본 checkout 합성 프롬프트 크기 재측정, git diff --check, 19개 HEAD/porcelain 전후 대조, worktree 삭제 없음. 소스 수정 전후 SHA·실행 로그 보존.
HTML: artifacts/worktree-followup-20261105/index.html 생성·내용/JSON 대조·사용자 열기 요청. 열기 성공과 렌더를 구분한다.
experiment: 없음. 실제 Codex/Gemini 요청·학습·사진 추론 금지.
handoff: 항목별 판정은 reports/worktree-followup-20261105.md와 ignored 감사에 기록한다. 검증된 통합은 일반 push 및 원격 SHA 확인까지 진행한다.
risks: 32KB 여유는 해당 고정 입력에만 해당. 다른 입력도 통과하거나 실제 correct 응답이 유효함을 보장하지 않는다. 데이터 편입 과거 결과는 코드 통합 완료와 구분한다. 앱 채팅 archive는 삭제로 이어질 수 있어 수행하지 않는다.
rollback: 통합 SHA를 ./develop -- git revert <SHA> 후 관련 회귀와 일반 push. 문서 정정은 별도 문서 커밋 revert. 원래 worktree·브랜치·초안은 모두 보존한다.
