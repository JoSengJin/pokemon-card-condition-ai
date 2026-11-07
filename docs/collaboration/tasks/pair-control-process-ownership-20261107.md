# 프로세스 중단 직전 소유권 재확인

- task_id: pair-control-process-ownership-20261107
- owner: Codex
- status: integrated
- base_sha: f3581e220cb9c5dd227d469103def2a82e2fd6d9
- branch: codex/pair-control-process-ownership-20261107
- dependency: pair-control-stream-boundary-20261107(현재 main 통합 대기) 커밋 전체를 순서대로 반영해야 한다.
- goal: 소유권 불명/다른 감독자·완료된 실행에는 신호를 보내지 않고, 종료 관찰 시에도 남은 그룹 소유를 확인한 뒤 정리한다.
- allowed_files: tools/pair-control/src/executor/processCancel.ts, tools/pair-control/src/executor/monitorRecovery.ts, tools/pair-control/test/process-ownership.test.ts, tools/pair-control/README.md, 이 계약, docs/collaboration/reports/pair-control-process-ownership-20261107.html, ignored artifacts/pair-control-process-ownership-20261107/.
- forbidden: 실제 모델/CLI/API/학습/추론·운영 설정/상태/서버·다른 세션 작업/잠금·.claude/·사진/라벨.
- contract: 신호 직전 소유권을 양성 확인한다(기존 ownsLeader 재사용). unknown은 소유로 간주하지 않음. 예약 콜백은 같은 저장 실행 객체·cancelling·cancelRequested·현재 소유권이 모두 맞을 때만 SIGKILL. 종료 기록 token이 맞아도 남은 그룹 소유가 불명/다르면 unknown 보존·자동 결과 적용 금지. 기존 정상 중단·손자 정리는 핵심 회귀로 검증.
- structure: processCancel/monitorRecovery 함수 수 불변·호출 전이4 이내, 새 승인 판정/추적 경계 없음.
- checks: 가짜 ps + process.kill 기록으로 경합 반례 → 정상 중단·대표 연속 처리만 선별 → 타입/구조 → main이 깨끗해지면 통합·일반 push. 전체 회귀/실제 모델 호출 안 함.
- risks: 감독자 없는 살아 있는 그룹은 자동 신호/해제 대신 unknown/거부로 보존한다. 사람이 소유를 확인해야 한다. PID 확인과 커널 신호 사이의 OS 원자성은 보장하지 않는다.
- rollback: 관련 커밋 역순 git revert·핵심 검사·일반 push. 다른 작업/상태 삭제·force/reset 없음.

## 검증·인계

- 원본 소스 SHA 807e10a291959812b67ee9c8851c8b9e64205f97 / 동일 제품 main 통합 46a8996542edaac864cab3bf1426042735d892f4.
- 가짜 소유권11개 + 정상 중단/대표 연속 처리2개 통과, 타입/구조 통과. 샌드박스 ps 제한 실패2개는 OS 조회 허용 환경에서만 재검증. 전체/실제 모델 호출0.
- processCancel4→4/monitorRecovery3→3. 전체270/786/최대7/전이4/초과0. cancelRunning→setStatus→save2전, observeExit→resume→resumeStep→save3전. 미확인93/외부2747·분류 근거 해시 불변·추가 미분류0.
- 선행 로그 보완12개와 함께 -x 순서 반영. 다른 작업 커밋8e2fb7d 보존, tested tree와 main 제품 소스 동일.
- 보고서 docs/collaboration/reports/pair-control-process-ownership-20261107.html 및 artifacts/pair-control-process-ownership-20261107/ 로그/검증/통합 매핑/SHA256. HTML IAB 열기·실제 렌더 확인 완료. 화면 증거 보존.
- 소유 불명 고아 그룹은 사람 확인 필요, OS 신호 원자성 미보장. 나머지 리스크/미실행/롤백은 보고서 참조.
