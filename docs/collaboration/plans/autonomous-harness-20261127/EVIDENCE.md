# 자율 개발 하네스 — 원자료 분석 결과와 근거 경로

작성 2026-11-27(KST), Claude. **"직접 확인"은 이 설계 대화에서 명령으로 확인한 것, "인용"은 다른 문서의 수치를 옮긴 것(이번에 재집계하지 않음)이다.** 새 세션은 인용 수치를 사용하기 전에 원문으로 다시 확인한다.

## 1. 근본 원인 판정 (요약)

정확도 개선의 첫 병목은 모델이 아니라 **사람 정답과 독립 평가 자료**다. 근거는 아래 2절. 개발 자료(942구역)에서는 모델 개선을 라벨 흔들림과 구분해 증명할 수 없다.

## 2. 데이터·라벨·평가 (인용)

출처: [08-lead-roadmap.md](../accuracy-expert-chain-20261126/08-lead-roadmap.md)와 같은 폴더 01~07.

| 항목 | 수치 | 원문 위치 |
|---|---|---|
| 모델 탓 오류 vs 라벨 흔들림 | 6/178구역 vs 결함 33·정상 44구역 | 08 결론 1, 04 2-1, 05 4-3 |
| 같은 개발 자료 모서리 비교 | 12회 중 2회 통과 | 06 2-2, 08 C4 |
| 옛 정상 → 현행 기준 결함 | 약 37%(35/94) | 02 2-5, 06 M3 |
| 판단 불가 상태 | 0/9,017 | 01 G1, 08 R9 |
| 배경별 누락 | 밝음 52/185(28.1%), 어두움 28/187(15.0%) | 03, 04 |
| 라벨 화면 vs 모델 입력 해상도 | 7.7 px/mm vs 14.7 px/mm | 03 2-5 |
| 구역 구간 과소 추정 | 설계 효과 1.2~1.9배 | 05 2-2 |
| 판정 주체 대조 | A2·B2 "사람" 답과 AI final 64/64 일치(pass1 56/64·50/64), 350 중 131, 468 중 416 | 02 2-3, 08 V1 |
| 독립 측정 장수 | 층별 ±0.08 측정에 400장 | 05, 08 C2 |

라벨 출처 사고 기록: `docs/collaboration/reports/label-provenance-correction-20261122.md`(다른 세션 AI 판정을 사람 재판정으로 붙여넣음), `artifacts/cohort2-retest-20261125/`(CORRECTION-2·3). 2026-11-26 정정 보고서 `label-provenance-correction-20261126.md`는 커밋 fccfbe5·aafedfb로 추가됐다가 94d1e74·8c6a23b로 **되돌려져 현재 main에 없다**. 내용은 `git show fccfbe5`로만 볼 수 있으며, 되돌린 이유는 이 문서 작성 시 확인하지 않았다.

판정자 1명 환경의 근거 방법: `docs/knowledge/accuracy-evidence-methods-20261125.md`.

## 3. 프로젝트 상태 (직접 확인, 2026-11-26)

| 항목 | 결과 | 확인 방법 |
|---|---|---|
| 진척 정본 | 78/100, `production_ready=false`, 기준 `usable-card-analysis-v1.14` | `development-progress.json` |
| 실험 기록 | 272건: completed 222, failed 48, interrupted 2 | `artifacts/experiments/*/record.json` 집계 |
| 실험 소요 시간 | 중앙값 0.5분, 90% 24.6분 이하, 최대 113.1분 | `record.json`의 started_at·finished_at |
| 실험 판정 형식 | `evaluation.json` 판정 필드가 통일되어 있지 않음 | 같은 폴더 집계 |
| 학습 코드 저장 | `dino_wear_lora.py`에 `torch.save`·epoch 저장 없음 | grep |
| 코드 규모 | `card_condition/` 162개 파일(약 15.5k줄), `tools/` 61, `tests/` 256 | ls·wc |
| 산출물 규모 | `artifacts/` 21GB, 1,207개 항목 | du·ls |
| 자동 개발 최신 상태 | `artifacts/development-cycle/latest.json` status `ai_calls_forbidden`(2026-10-24 기록) | 파일 읽기 |
| `intent.md` | 저장소에 없음 → AGENTS.md를 운영 규칙으로 사용 | find |

## 4. 보호 장치 현황 (직접 확인)

| 항목 | 결과 |
|---|---|
| 프로젝트 PreToolUse 훅 | `.claude/settings.local.json`이 `pokemon-card-condition-claude-rule-guard-20261124/tools/rule_guard/hook.py`를 호출하고 `>/dev/null 2>&1 \|\| true`로 끝남 → **차단하지 못함**. 다른 worktree 경로에 의존 |
| 봉인 자료 권한 | `artifacts/d1-*`, `*-seal-*` 등은 사용자 `jueun` 소유 `drwxr-xr-x` → 에이전트와 같은 권한으로 읽기·쓰기 가능 |
| 봉인 무결성 | `card_condition/frozen_test.py`의 해시 장부(코드상 경로 `artifacts/frozen-test-usage`, 2026-11-27 기준 폴더 없음)는 사후 감지만 하고 열람을 막지 않음 |
| 잠금·실행기 | `./experiment` → `card_condition.experiment_record`, `./develop` → `card_condition.workspace_lock`, `./review` → `card_condition.cross_review_manual` |

## 5. AGENTS.md 충돌 문장 (직접 확인)

무인 운영과 충돌해 D-1 개정이 필요한 문장:
- "실패/결과 불명 Codex 요청·학습은 자동 재시도하지 않는다"
- "세션을 상시 깨우거나 무한 재토론하지 않는다"
- "최종 응답 이후 자동 실행이 이어지는 것으로 약속하지 않는다"
- "실제 학습·모델 비교·사진 추론·라벨 수정·자동 검토는 기본 checkout의 단일 담당자에게 모으고" (하네스를 그 담당자로 지정 필요)
- `docs/AGENT_START.md`: "병렬·하위 에이전트는 사용자가 승인한 분업이 있을 때만 별도 계약으로 다룬다"

## 6. 설치 환경 (직접 확인, macOS 27.2, Claude Code 2.1.310)

| 기능 | 결과 | 근거 |
|---|---|---|
| 비대화형 실행 | `claude -p`, `--resume`, `--continue`, `--model`, `--effort`, `--output-format stream-json`, `--max-budget-usd`, `--fallback-model` | `claude --help` |
| 백그라운드 세션 | `--bg`, `claude attach/logs/stop`, `claude agents` | `claude --help` |
| Remote Control | `claude remote-control`, `--session-id` 재연결, `--continue`는 약 4시간 이내 기록만, `--spawn same-dir/worktree/session` | `claude remote-control --help` |
| 한도 정보 | `rate_limit_event`, `resetsAt`, `resetsAtSeconds` 문자열이 바이너리에 존재 | `strings` (실제 출력 형태는 미확인) |
| `/goal` | "Set a goal — keep working until the condition is met", 비대화형 지원 표시 | 명령 정의 |
| `/loop` | 세션 안 재호출, 간격 60~3600초 | 스킬·도구 설명 |
| `/low-priority` | "Continue now at lower priority after reaching your session limit" | 명령 정의(과금 미확인) |
| `/rate-limit-options` | "Manage usage limits and upgrade options" | 명령 정의 |
| 앱 예약 작업 | 앱이 열려 있을 때만 실행, 닫혀 있으면 다음 실행 때, 실패한 실행은 자동 재시도, 매 실행 새 세션 | 도구 설명 |
| 앱 예약 작업 상태 | `list_scheduled_tasks`는 "없음"인데 `~/.claude/scheduled-tasks/`에 폴더 7개(`self-agreement-round2-send` 등) | 2026-11-27 확인. **자기 일치도 2차 예약의 실행 여부 미확인** |
| 앱 푸시 설정 | `agentPushNotifEnabled=true`, `inputNeededNotifEnabled=true` | `~/.claude/settings.json` |
| 격리 도구 | `/usr/bin/sandbox-exec` 존재 | which |
| 전원 | sleep 0(Claude·powerd·Chrome이 막음), autorestart 설정 없음 | `pmset -g` |
| Telegram | claude-mem 설정에 Telegram 활성 항목 존재(값은 열람하지 않음) | `~/.claude-mem/settings.json` 키 이름 |
| 라우팅 정책 문서 | 저장소·`~/.claude`에서 찾지 못함. `docs/history/ROUTING_AUDIT_20261009.md`는 다른 주제(과거 기록) | grep·find |

## 7. 구현 단계 검증 항목 (미확인)

1. 비대화형 출력의 `rate_limit_event.resetsAt` 실제 형태와 발생 시점
2. LaunchAgent에서 실행한 `claude -p`가 구독 로그인(키체인)으로 인증되는지
3. 한도 상태에서 `UserPromptSubmit` 훅이 실행되는지
4. 한도 상태에서 앱 푸시가 휴대폰에 도착하는지
5. 비대화형 실행과 한도 상태에서 `/goal`의 동작
6. `--resume` 실패 조건과 새 세션 재개
7. `sandbox-exec`로 네트워크·파일 쓰기 차단이 실제로 되는지
8. `/low-priority`의 과금 여부(자동 사용 금지는 유지)
9. 현재 채택된 후면 점검 모델의 정확한 SHA
10. 라벨 대상 사진 풀 규모(이전 조사: 후보 583장, `artifacts/independent-card-count-20261125/`)
11. 앱 예약 작업 목록과 파일 불일치의 원인
12. 재부팅·로그아웃 뒤 동작 범위
