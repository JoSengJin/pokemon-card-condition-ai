# 실제 수집 계약 초안 권장안 반영

task_id: collection-contract-update-20261117
owner: Codex
status: implementing
base_sha: ea7b7f8aac774be041ab0c54a9b89bf99bdef6fe
branch: codex/collection-contract-update-20261117
goal: 권장 절차·합성 검증 근거와 실제 수집 미구현 경계를 일관된 초안으로 반영하고 사용자 결정 항목은 답변 또는 미정 상태로 한 곳에 기록한다.

## 소유 파일
- docs/collaboration/reports/new-observation-independent-evaluation-contract-20261117.md
- docs/collaboration/tasks/collection-contract-update-20261117.md
그 외 추적 파일·실제 자료·라벨·모델·worker·선택기·운영 fallback·고정 진척/평가 기준은 변경하지 않는다.

## 계약·실행 계획
- [x] 현재 문서/코드·브라우저 검증 보고서 대조. 사용자 결정5묶음(기기, 사진 출처/권한, H/A 사람 배정, 보관/평가 역할, 오류 중요도)을 한 번에 질문했다. 응답 전에는 미정이며 한 사람 배정을 가정하지 않는다.
- [ ] 권장안 문서 반영: 단일 실제 사용 프로파일, 출처/모집단 범위, H/A 배정 분리 우선·한 사람이면 A봉인후H, 자동 조정 없이 미확정 종료, 새 사람A 보수적 카드 요약, 대표 후면 사진 선정, 그룹 균등 가중, 사고 영향범위/범위불명 session 격리.
- [ ] 구체 기기/사진 출처/담당자/오류 비용은 사용자 응답만 반영. 표본수/개선폭/통계설정/허용률은 미정 유지. 기존 고정 기준과 최초 원응답 보존.
- [ ] 합성33개와 Chrome 검증은 과거 근거로 링크만 연결하고 새 테스트/모델 검증 성과로 보고하지 않는다. 현재 synthetic 전용 API의 실제 human 거부 및 H확대/접근통제 등 별도 준비 필요를 명시한다.
- [ ] 문서 diff/로컬 링크/필수 상태와 수치 미정/보호 절 불변/허용 파일만 변경 확인. 로컬 커밋만 수행. main 통합·push 금지.

structure: 문서만 변경, 함수 정의/호출 전이 변화 없음.
checks: git diff --check, 상대 링크 대상 확인, 기존 §2·§7·§8.3 수치/게이트 보존 및 새 문구 정합성 대조. 실제 자료/수집/사람 판정/모델 실행/외부 AI 호출/실기기 시험 없음. 문서 준비만이므로 HTML_REPORTING.md에 따라 성과 HTML 생성/열기 없음.
experiment: 없음. 표본 산정·수치 승인·수집/모델 실행 권한으로 확대하지 않는다.

## 리스크·롤백
새 A 요약은 기존 보조 규칙보다 미확정 카드가 늘 수 있으므로 기존 결과와 직접 비교/소급 적용하지 않는다. 단일 사람 순차 H/A는 완전 독립이 아니다. 권장안 문서 반영과 사용자 응답은 실행 승인이 아니다. 합성 guard를 제거하거나 실제 자료를 synthetic_fixture로 위장하지 않는다. 롤백은 이번 결과 문서 커밋을 revert; 계약까지 철회하면 선행 계약 커밋도 역순 revert. 이전 브라우저 검증/원자료/다른 worktree 보존.
