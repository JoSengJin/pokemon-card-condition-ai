# 자율 개발 하네스 설계 묶음 (2026-11-27)

상태: **설계 확정(사용자 동의 2026-11-27), 구현 미승인.** 구현 착수 조건은 [DECISIONS.md](DECISIONS.md) D-1~D-4 확정이다. 이 묶음은 권한을 새로 주지 않으며 AGENTS.md가 우선한다.

## 읽는 순서

1. `AGENTS.md` 전체, `docs/AGENT_START.md`
2. 이 README
3. [DESIGN.md](DESIGN.md) — 최종 설계(구조, 자율 루프, 라벨링·교차 검증, 평가, 보안, Champion, 재개, 라우팅 연계)
4. [DECISIONS.md](DECISIONS.md) — 사용자 승인 원문, 미결정 사항, 채택·기각 근거
5. [EVIDENCE.md](EVIDENCE.md) — 원자료 분석 결과, 파일 경로, 설치 환경 확인, 미확인 검증 항목
6. [IMPLEMENTATION.md](IMPLEMENTATION.md) — 구현 순서, 단계별 완료 기준, 최종 완료 증명 T1~T7
7. 구현 단계에 따라: `PAIR_CODING.md`, `COMMON_EXPERIMENT_RECORDS.md`, `LABELING_PROTOCOL.md`, `docs/agent/QUALITY_RULES.md`, `docs/collaboration/HTML_REPORTING.md`
8. 배경(필요할 때): `docs/collaboration/plans/accuracy-expert-chain-20261126/08-lead-roadmap.md`, `docs/knowledge/accuracy-evidence-methods-20261125.md`

## 최초 요구사항 대조

2026-11-26 최초 요청("포켓몬카드 상태분석 AI — 자율 개발 하네스 설계")의 항목이 어디에 반영됐는지 확인한 표다. 새 요구를 더하지 않았다.

| 최초 요구 | 반영 위치 |
|---|---|
| 오분석·근본 원인 분석, 가설·구현 | DESIGN 4, EVIDENCE 1~2 |
| 필요한 학습 데이터 식별 | DESIGN 5-5 능동 학습 |
| 에이전트 자동 라벨링과 검증 | DESIGN 5-3, 5-4 |
| 모델 학습·독립 성능 평가 | DESIGN 6, 7 |
| 성공·실패 실험 기록, 반복 실패 방지 | DESIGN 9, 11 |
| 사용량 한도·세션 중단 뒤 재개 | DESIGN 12, IMPLEMENTATION T2~T4 |
| 목표 달성 또는 종료 조건까지 반복 | DESIGN 10, 11 |
| Gold/Silver/Pending 라벨 신뢰성 | DESIGN 5-1 |
| 라벨 JSON 재활용과 출처 필드 | DESIGN 5-2, 5-6 |
| 사용자 개입 최소화(필요한 경우만) | DESIGN 4, 5-4, IMPLEMENTATION 4 |
| 평가 지표 선택 근거, A/B/C 실험 | DESIGN 6-1~6-4 |
| 평가 무결성(중복 금지, 정답 보호, 기준 변경 금지, 기술적 강제) | DESIGN 6-5, 7 |
| Claude Code 기능 검증(`/goal`, `/loop`, `/compact`, `/resume`, `/effort`, `/rate-limit-options`, AskUserQuestion, Skills, Hooks, Push, Headless, RC) | EVIDENCE 6, DESIGN 15. AskUserQuestion의 RC 표시는 미확인 |
| 모바일 RC 운영(상태, 라벨링, 이미지 검토, 승인, 중단·재개, 알림) | DESIGN 5-2, 13 |
| 장애 상황별 복구(한도, 컨텍스트, 프로세스, RC, 네트워크, 인증, 학습, 라벨링, 사용자 대기, 재부팅) | DESIGN 9, 12 |
| 상태 영속화 항목 | DESIGN 3, 8, 9 |
| 토큰·리소스 최적화 | DESIGN 16 |
| 종료·중단 조건(수치는 사용자 승인) | DESIGN 10~12, DECISIONS D-2·D-5 |
| 거버넌스(승인 없이 구현 금지, Gold 변경 금지, 실패 은폐 금지, 기술적 강제) | DESIGN 2, 7, IMPLEMENTATION 0 |
| 최소 구성 vs 확장 구성 비교 | DECISIONS 3 "재개 경로", DESIGN 15 |
| 비판적 검토와 외부 기준 | DECISIONS 3·4, EVIDENCE 1 |

## 새 세션 개발 시작 프롬프트

아래를 새 세션에 그대로 붙여넣는다. D-1~D-4가 확정되지 않았으면 결정 요청까지만 한다.

```
pokemon-card-condition 저장소에서 자율 개발 하네스 구현을 시작한다.

1. AGENTS.md 전체와 docs/AGENT_START.md를 읽고, docs/collaboration/plans/autonomous-harness-20261127/README.md의 읽는 순서대로 DESIGN·DECISIONS·EVIDENCE·IMPLEMENTATION을 끝까지 읽어라. 출력이 잘리면 나눠 다시 읽는다.
2. 시작 한 줄로 목표 / 하지 않을 것 / 완료 기준 / 확인 방법을 적어라.
3. DECISIONS.md 2-1의 D-1~D-4가 사용자 원문으로 확정됐는지 확인하라. 미확정이면 추천안과 이유를 짧게 제시하고 확정을 요청한 뒤, 결정이 필요 없는 읽기 전용 확인(EVIDENCE 7절의 검증 항목 중 실행 없이 가능한 것)만 한다.
4. 확정됐으면 IMPLEMENTATION.md 2절 순서대로 구현한다. 단계마다 완료 기준을 실제로 검증하고, 명령·종료 코드·대상 SHA·미검증 항목을 기록한다. 설계에 없는 기능은 추가하지 않는다. 설계와 실제 환경이 다르면 그 차이만 보고하고 승인 범위 안에서 진행한다.
5. 모델·worker 수정은 ./develop, 새 실험은 ./experiment로만 한다. 실제 학습·추론·라벨 수정은 기본 checkout 단일 담당자만 한다. 사람 라벨 재요청, 완료 라벨 변경, 봉인 자료 열람, 외부 AI 호출은 설계와 승인 범위 밖에서 하지 않는다.
6. 로컬 커밋은 검증 뒤 기능별로 한다. main 통합·push는 고지 후 승인을 받는다.
7. 보고는 결론 → 근거 → 쉬운 설명 순서로, 한국어로 한다.
8. 개발 모델 배정은 IMPLEMENTATION.md 5절을 따른다. 배정은 시작점일 뿐 작업 제한이 아니다. 하위 에이전트에 모델·effort를 지정해 위임하고, 보안·상태 일관성·자동 재개 핵심 구현은 Opus 독립 검증을 거친다. 모델이 다르다는 이유로 멈추거나 세션 전환을 요구하지 않는다.
```
