# 현재 자동 검토 계약과 과거 안내 분리

task_id: agent-input-limit-clarity-20261118
owner: Codex
status: integrated
base_sha: 67941ff7e6141d0d849911870cc3c89df757b7de
branch: codex/agent-input-limit-clarity-20261118

## 승인·목표·가설

사용자가 과거·현재 지침의 중복 정리와 이전 실패 로그 보존, 실제 새 세션 재검증을 요청했다. 문서·관련 회귀 검증과 Claude 새 읽기 전용 세션 1개만 실행한다. 기존 승인·실제 호출 제한·런타임 가드는 바꾸지 않는다. 추가 Gemini/NVIDIA/Codex CLI·학습·사진 추론·자동 검토는 실행하지 않는다.

초기 AUTO_DEVELOPMENT 안내의 낡은 수치/연결 설명과 후속 계약이 함께 읽혀 잘못된 상한 해석을 유발할 수 있다는 가설이다. 모델 내부 원인은 확인하지 못했으므로 문서 분리가 유일 원인 또는 일반적 해결이라고 단정하지 않는다.

## 설계와 순서

1. 기존 지침·런타임·이전 raw 로그 해시를 동결한다. 현재 안내와 runtime 사이 정합성 테스트를 추가해 기존 문서에서 실패하는지 확인한다.
2. 초기 AUTO_DEVELOPMENT 원문을 history에 보존하고 root에는 현재 사용 진입점만 둔다. 상세 계약의 현재 상한/전송 정책을 상단의 한 구역으로 옮기고 과거 보완 중 중복 수치는 그 구역을 참조한다. 활성 안내에 과거 수치가 현재 규칙으로 남지 않도록 한다. 승인·호출 수·예산·무료 가드·재개/차단은 기존 계약과 코드 그대로다.
3. mock/문서 회귀 검증 후 이전과 byte-identical한 과제·계약, 같은 도구/로그인/기본 모델·16턴/600초·1회 제한으로 Claude 새 UUID 세션을 실행한다. 기대 문서 목록·숫자·오류 내용은 프롬프트에 넣지 않는다. 정답은 고친 실제 프로젝트 문서에만 있으며 과거 실패 로그와 평가 파일은 읽지 못하게 기존 과제를 유지한다.
4. 호출 전 새 기준·prompt hash·문서 hash를 고정하고 이전과 같은 필독 11개·기존 의미 점검 기준으로 첫 결과를 판정한다. 실패해도 추가 질문·resume·재실행 없이 그대로 남긴다.
5. 변경·검사·실제 결과·리스크·롤백·HTML 열기 상태를 보고하고 main 통합 검증·일반 push한다.

## allowed_files

- AUTO_DEVELOPMENT_20261020.md
- docs/agent/AUTO_REVIEW_CONTRACT.md
- docs/history/AUTO_DEVELOPMENT_BEFORE_LIMIT_CLARITY_20261118.md
- docs/history/README.md
- tests/test_agent_input_limit_docs.py
- docs/collaboration/tasks/agent-input-limit-clarity-20261118.md
- docs/collaboration/reports/agent-input-limit-clarity-20261118.md
- ignored artifacts/agent-input-limit-clarity-20261118/ (사전 고정·테스트·새 세션 원문·해시·HTML)

## 보호·checks·handoff

AGENTS·CLAUDE·공통 입구·공통 실험 계약·PAIR_CODING·라벨 규약·진척 기준/JSON·자동 검토 코드는 byte 불변. 이전 artifacts/agent-doc-live-20261118/ 전체 manifest 해시 불변. 기존 테스트의 기대값을 완화하거나 모델 결과를 수정하지 않는다. 새 테스트 파일 함수 정의 최대 7개, 런타임 호출 경로 변경 없음.

HTML: artifacts/agent-input-limit-clarity-20261118/index.html. 실제 열기 응답과 렌더 확인을 구분한다. 롤백은 이번 변경 커밋들을 역순 git revert 후 검사·일반 push이며 과거/새 실패 근거와 세션 사용량은 되돌리거나 삭제하지 않는다.

## 완료 인계

- 소스 8896305, main 후보 tree 동등성 확인 후 전체 unittest 1,036 tests / OK.
- 이전 실패 28개 파일·보호 지침/가드·이번 재개 이후 테스트 파일의 불변성 확인.
- Claude 판정은 partial_confirmation_not_full_pass 그대로다. 추가 모델 호출이나 통과를 위한 기대값 수정 없음.
- 변경·검증·리스크·롤백: docs/collaboration/reports/agent-input-limit-clarity-20261118.md.
- HTML: artifacts/agent-input-limit-clarity-20261118/index.html. 열기/렌더 상태는 opening.json과 최종 보고에 기록.
