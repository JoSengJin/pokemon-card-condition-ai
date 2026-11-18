# 실제 새 CLI 세션 지침 로딩 검증 · 2026-11-18

결론: **두 실제 새 세션의 자동 로딩과 필독 11개 문서 본문 전달은 확인했다. 지침 적용까지 모두 통과한 것은 아니다. Claude가 입력 상한을 잘못 보고했다.** 개발 진척률은 기존 78/100 (usable-card-analysis-v1.13) 유지이며 모델 성능 평가는 아니다.

## 승인과 사전 고정

사용자 요청은 실제 Claude·Codex 새 세션의 지침 로딩·문서 열람 검증이며 기존 승인·호출 제한을 유지하고 추측·테스트 조작을 하지 않는 것이다. 이 요청으로 허용한 실제 CLI 세션은 각각 1개다. 이전 자동 검토·학습·API 호출 권한을 확대하지 않았다.

검증 문서 기준 SHA: `c929335633f6e5c2b5fddfd6f1b975fe8e0efe0d`. 실제 세션 시작 HEAD: `f6758131aab2ff6e84c57ea350fce4947cb3e3ca`. 추가된 두 커밋은 읽기 전용 과제 계약과 파일 열람 명령 허용의 명확화다. 기존 지침·상한 코드는 같은 내용이다.

모델 호출 전에 ignored `preregistered.json`에 시나리오, 필독 목록 11개, 파일별 SHA-256, 판정 기준, 세션당 1회·600초, Claude 최대 16턴, 재실행 금지를 기록했다. 두 세션에는 동일한 과제만 주고 기대 문서 목록·정답·평가 결과를 주지 않았다. 최초 문구의 “명령 금지”는 Codex의 읽기 전용 파일/Git 명령까지 막지 않도록 두 세션 실행 전에 명확히 했다. 실행 후 과제·판정 기준·대상 지침을 바꾸지 않았다.

## 실제 세션

| 항목 | Claude | Codex |
|---|---|---|
| CLI 버전 | 2.1.310 | 0.164.0 |
| 실제 기본 모델 | claude-sonnet-5-5 | gpt-6.1-sol |
| 인증 | 기존 Claude Pro 로그인 | 기존 ChatGPT 로그인 |
| 새 세션 ID | `416edb51-7e34-4064-b277-2211c136a089` | `01a1eb76-5f04-7c52-bbf3-7ae343eb8b3b` |
| resume/fork/추가 보완 호출 | 없음 | 없음 |
| 제한 | plan, Read/Glob/Grep, 최대 16턴·600초 | read-only sandbox, 승인 자동 확대 없음·600초 |
| 외부·쓰기 도구 | 미허용 | MCP·웹·앱·플러그인·하위 에이전트 등 비활성화 |
| 실제 사용 | 14 agentic turns, 67.307초 | 읽기 명령 15개, 120.762초 |
| 종료 | exit 0, timeout 없음 | exit 0, timeout 없음 |

구독·기본 모델·계정 설정을 변경하지 않았다. `--bare`, 프로젝트 지침 비활성화, system prompt 교체, 문서 본문의 명시적 프롬프트 복사, 권한 우회 옵션을 쓰지 않았다. 한 세션은 여러 내부 모델 요청/도구 턴을 포함하므로 “세션 1회”를 “모델 API 요청 1회”로 세지 않는다.

## 자동 로딩의 독립 근거

- Claude: 실행 인자에 한정한 InstructionsLoaded 관찰 hook이 `CLAUDE.md / session_start`, `AGENTS.md / include`와 원문 SHA를 기록했다. 전역 언어 지침도 session_start로 기록됐다. hook은 경로·이유·해시만 로그에 남기며 stdout이 없고 모델 문맥에 정답/추가 지침을 주입하지 않았다. 계정 설정과 저장소 지침은 수정하지 않았다.
- Codex: 실제 새 rollout의 8행 `response_item` 사용자 지침 payload에 AGENTS.md 전체 원문이 첫 도구 호출 전에 포함됐고, 사전 동결 원문과 정확히 일치했다. 자체 “읽었다”는 답변만으로 판정하지 않았다.
- 원시 근거: ignored `claude-instructions.jsonl`, `claude/events.jsonl`, `codex/events.jsonl`, `codex/raw-session.jsonl`, `codex/autoload-evidence.json`.

## 필독 문서 본문 전달

| 사전 필독 문서 | Claude | Codex |
|---|---|---|
| `AGENTS.md` | 확인 | 확인 |
| `docs/AGENT_START.md` | 확인 | 확인 |
| `PAIR_CODING.md` | 확인 | 확인 |
| `COMMON_EXPERIMENT_RECORDS.md` | 확인 | 확인 |
| `OBSERVATION_CONSENSUS_20261011.md` | 확인 | 확인 |
| `LABELING_PROTOCOL.md` | 확인 | 확인 |
| `docs/agent/AUTO_REVIEW_CONTRACT.md` | 확인 | 확인 |
| `AUTO_DEVELOPMENT_20261020.md` | 확인 | 확인 |
| `PROGRESS_CRITERIA.md` | 확인 | 확인 |
| `development-progress.json` | 확인 | 확인 |
| `docs/collaboration/HTML_REPORTING.md` | 확인 | 확인 |

판정은 성공한 Read/명령의 실제 반환 본문을 동결 파일의 줄 번호·문장과 대조한 것이다. AGENTS는 위 자동 로딩 근거로 포함했다. 공백 줄을 제외한 모든 줄이 일치했으며 단순 Glob/검색/head나 최종 답변의 자체 목록만으로 통과시키지 않았다. 비교 코드와 줄별 누락 목록은 ignored `audit_reads.py`, `read-audit.json`에 있다.

- Claude: Read 11회(배정 계약 포함), Glob 2회. 도구 오류 0개. 필독 11/11 전달 확인.
- Codex: 성공한 읽기 전용 명령 15개. 출력 잘림 이벤트 2개가 있었지만 이후 구간 재열람의 실제 결과로 모든 필독 본문을 확인했다. 필독 11/11 전달 확인.
- 추가 탐색 문서 중 README는 Codex가 로컬 경로 설정 구역만 읽었고 Claude는 읽지 않았다고 명시했다. README 전체나 소비 프로젝트 TODO 열람을 확인했다고 덧붙이지 않는다.

## 지침 적용 판정 — 전체 통과 아님

Claude 최종 응답 88행:

> 입력은 32KB, 구현 48KB를 넘으면 호출 전에 차단합니다.

그러나 `docs/agent/AUTO_REVIEW_CONTRACT.md:116`의 최신 app-server 계약과 `card_condition/cross_review_auto_contract.py:6`은 **모든 단계 32,000 bytes**다. Claude는 최신 문서를 전체 전달받았는데도 과거 48KB 설명을 현재 상한으로 보고했다. **입력 상한 해석 항목은 실패**로 남긴다. 해당 과거 설명과 후속 보완이 같은 안내 체계에 공존하는 것이 문서상 위험이지만, 모델 내부 원인이 이것 하나라고 단정하지 않는다.

Codex는 최종 응답 36행에서 모든 단계 32,000바이트와 과거 큰 상한을 구분했다. 사람 정답/unknown, 공통 실행기·변수 하나·평가 분리, 저장 응답 재개와 결과 불명 차단, 역할·일반 push 승인과 force 금지, 현재 진척 정본의 보호를 두 응답에서 검토했다. 이 검토로 모든 미래 행동의 준수를 증명하지 않는다.

두 세션은 자동 검토·학습·추론·추가 외부 모델을 실행하지 않았다. Claude의 잘못된 설명에 따라 실제 48KB 요청이 전송된 것은 아니며 실행 가드도 바뀌지 않았다. 원문과 결과를 손보거나 재질문/재호출하여 통과시키지 않았다.

## 실제 사용량과 호출 범위

- Claude CLI 원시 usage: input 8, cache_creation_input 104,422, cache_read_input 92,127, output 8,812 tokens. CLI의 비용 표시 `0.5150367 USD`는 실제 구독 추가 청구가 확인됐다는 뜻이 아니다.
- Codex CLI 원시 usage: input 761,590 (cached 666,752 포함), output 4,717 (reasoning 262 포함) tokens. 캐시 토큰을 별도 중복 합산하지 않는다. USD 비용은 보고되지 않아 추정하지 않는다.
- 실제 새 세션 각각 1개. 새 Gemini 0, NVIDIA 0, `./review --auto` 0, 실카드 학습·사진 추론 0. 자동 검토용 100,000 토큰/32,000 bytes 정책은 해당 경로에 그대로 있으며 이번 일반 CLI 문서 열람을 그 격리 자동 경로로 가장하지 않았다.

## 무변경·리스크·롤백

- 세션 종료 직후 `git status --porcelain`은 비어 있었다. 사전 동결한 12개 파일(필독 11개 + CLAUDE.md) SHA-256과 입력 상한 코드가 시작 기준과 같았다. 테스트·정책·승인 범위를 고쳐 통과시키지 않았다.
- 변경 파일은 읽기 전용 과제 계약 `docs/collaboration/tasks/agent-doc-live-probe-20261118.md`와 본 결과 보고서뿐이다. 원시 로그·관찰 hook·일회용 실행/대조 코드는 ignored `artifacts/agent-doc-live-20261118/`에 둔다.
- 실제 로그인 CLI가 새 대화 기록과 사용량을 만든 것은 검증에 수반된 효과다. 기본 계정/모델·승인 설정을 바꾸지 않았고 키·토큰·원시 세션 기록을 Git에 넣지 않는다. 원시 근거 디렉터리는 접근 권한 0700이다.
- 한 시나리오·각 1세션의 관찰이다. GUI 새 채팅, 편집/학습/통합 실행, 모든 모델·버전·미래 세션의 완전 준수는 미검증이다. 메모리 자동 로딩은 기존 설정대로 유지했으므로 모델 기억의 영향을 제거한 실험으로 주장하지 않는다.
- 이번 검증은 문서를 수정하는 후속 개선 승인이 아니다. 과거/현재 상한의 중복 정리는 별도 후속 작업으로 남기며 현재 오류를 숨기지 않는다.
- 롤백 대상 운영 코드·라벨·모델·평가 기준은 없다. 필요 시 이번 기록 커밋과 계약 커밋 f675813, 4915e39를 역순 git revert하고 일반 push한다. 실제 세션 사용량은 revert로 취소되지 않으며 근거는 삭제하지 않는다.

## HTML와 재현 근거

HTML: ignored `artifacts/agent-doc-live-20261118/index.html`. 같은 결과의 본 Markdown 보고서와 실제 로그를 제공한다. 원시 로그를 공개 웹이나 원격 저장소에 전송하지 않는다. 네이티브 파일 패널 열기는 queued 응답이며 실제 렌더는 미확인이다. 이전에 차단된 브라우저 file 프로토콜을 우회하거나 재시도하지 않았다. 결과는 opening.json에 기록했다.

고정 입력·명령·세션 ID·실제 usage·완료 상태·줄별 읽기 대조·오류 인용·파일 해시는 preregistered.json, 각 엔진 command/attempt/completion.json, read-audit.json, semantic-audit.json, evidence-manifest.json에 보존한다. 재실행은 모델 요청을 다시 발생시키므로 이번 검증에서는 하지 않는다.
