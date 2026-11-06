# 관제도구 메인 턴 실행 직전 상태 검증

- task_id: pair-control-turn-start-20261106
- owner: Codex
- status: integrated
- base_sha: 9e58aa28d113cc3802484c343f9b39916dcd0f57
- branch: codex/pair-control-turn-start-20261106
- goal: 준비 대기 중 메인 세션/세대/동결/승인/대상 상태가 바뀌면 오래된 메인 턴을 실행하지 않고, 실행하지 않은 독립 작업은 최신 유효 상태에서 이어가게 한다.
- allowed_files: tools/pair-control/src/executor/pipelineTurn.ts, tools/pair-control/src/executor/pipelineEvents.ts, tools/pair-control/src/executor/monitorTick.ts, tools/pair-control/src/executor/verificationStart.ts, tools/pair-control/src/executor/verificationLifecycle.ts, tools/pair-control/src/executor/pipelineSteps.ts, tools/pair-control/src/executor/handoffCreate.ts, tools/pair-control/test/auto-prep-start.test.ts, tools/pair-control/test/verification-stop.test.ts, tools/pair-control/test/pipeline-start.test.ts, tools/pair-control/test/pipeline-launch.test.ts, tools/pair-control/README.md, 이 계약, docs/collaboration/reports/pair-control-turn-start-20261106.html.
- forbidden_files: .claude/·운영 설정/상태/장부·모델/worker·사진/라벨/진척·다른 checkout/서버. 실제 모델 요청·학습·추론 금지.
- contract: 기존 approvalGate/turnHold의 단일 승인 판정과 기존 이벤트 생성 조건을 재사용. 세션/세대 변경은 stale로 보존, 철회/현재 대상 불일치는 해당 이벤트만 보류. 아직 실행하지 않은 유효 이벤트는 같은 세대에서도 최초 실행 가능해야 하며 실제 시작/결과 불명 요청은 재시도하지 않음.
- structure: 시작270파일/781정의/최대7·실제전이4. 함수 추가로 책임 숨기기·예외 경계 추가 금지. 변경 전후 파일별 정의·경로 및 원시 미확인/외부 호출 근거 대조.
- checks: fake CLI probe 대기 재현 → 관련 회귀·typecheck·structure --check → 전체 회귀(임시 bare 포함) → main 관련 검증·일반 push·원격 SHA 대조. HTML 생성·실제 렌더, .claude 해시·worktree 보존 기록.
- experiment: 없음. 실제 모델 호출0 유지.
- rollback: 후속 문서부터 역순 git revert·관련 검사·일반 push. 운영 장부 삭제/결과 불명 재실행 금지.

## 완료 감사 범위
- 메인 턴 준비 중 세션/세대/동결 변경, 승인 철회/조건 변경, 현재 작업 상태/SHA 변경, 혼합 이벤트의 독립 처리, stop/한도/무료 가드, 중복/재시작 결과 불명, 기존 양방향 교대·통합·push 회귀를 차례로 확인한다. UI 표시 보완 한 건이나 작은 커밋 완료를 세션 종료 기준으로 삼지 않는다.

## 실행 안전성 범위 보완
- runChecks는 준비 await 후 stop/guard를 다시 보지 않고 새 검사 기록·감시를 등록한다. startNextCheck와 monitorTick의 다음 검사 분기도 stop을 보지 않아 대기하던 검사를 시작할 수 있다. 검사를 새로 등록/시작하는 경계에 같은 중단 조건을 적용하고, 기존 실행의 종료 관찰·결과 불명 보존은 유지한다. 허용 파일에 이 경로와 합성 반례를 추가한 뒤 수정한다.

- 자동 준비의 runChecks/handoffToMain도 내부 Git await 동안 승인·세션이 바뀔 수 있으므로 호출자가 메인 맥락을 전달하고 저장 직전 기존 whyClosed/PREP로 재검사한다. 수동 호출은 별도 승인 장부를 요구하지 않으며 stop/guard 및 현재 작업 상태는 동일하게 보호한다.

## 완료 감사·인계
- 적용 순서: 9e58aa28d113cc3802484c343f9b39916dcd0f57 → 8c3133a40a65198143263683b3dc399b15ed3150 → 73b5652f77fbbffd8aee003c45224f8729180b73 → 0e7c36793205ad68afed7c3638de6d4b66d81435 → de2b3a90d4edf09d7b16c69a16a2c014590e470a → 후속 문서. 변경 파일7개(src/executor)와 테스트4개·README, 기능은 실행 직전 상태 검증만 보완.
- 새 회귀29개, 단계별 최초 반례 실패8/5/10건. 최종 관련47개 전부 통과. 전체292개 중291통과/실패0/취소0/기존 Playwright 건너뜀1,723012.137167ms. main 관련47개 재실행 전부 통과. main 전체292개 재실행은 하지 않음. 두 위치 typecheck·구조 --check 통과, trace 동일.
- pipelineTurn2→4, pipelineEvents5→5, monitorTick7→7, pipelineSteps4→4, verificationStart4→4, verificationLifecycle7→7, handoffCreate2→2.270파일/783정의/최대7/실제전이4/초과0/순환0. 미확인86개 호출자·대상·이유 불변·발췌 갱신, 바뀐 tried 배열 근거 재대조·mainTypes 인용 추가, 분류 미완료0. 외부2735→2740(표준 startsWith1/filter2/includes1/Error1).
- 기존 운영 spec/log 읽기 전용 감사로 실제 Claude 구현 성공 result9개·Codex 리뷰 정상 종료/판정3건을 확인. 이전의 실제 모델 프롬프트 포괄적 미실행 설명은 정정하고 README에 반영한다. 이번 턴 신규 모델 요청0, 현 버전 메인 교대 실계정 검증/무료 청구 증명은 별도 미확인.
- main .claude 해시 c43a643c3c71c048dc5f8fb30ecfacd53d6b99910eafb48d65376e53fa59e4da 불변, .claude/.gitignore diff 없음. 운영 상태/설정/기존 서버 변경 없음. 제거0/checkout8개 보존. 별도 카드 모델 장부78/100 유지, 성능 평가 없음.
- HTML docs/collaboration/reports/pair-control-turn-start-20261106.html, 증거 artifacts/pair-control-turn-start-20261106/. HTML IAB 열기·실제 렌더 확인 완료, 스크린샷 보존. 전체 기능 완료 조건별 근거와 운영 채택 범위는 HTML 표 참조. 롤백은 후속 문서→코드 역순 git revert·관련 검증·일반 push, 실제 미실행.
