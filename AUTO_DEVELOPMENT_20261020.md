# 자동 검토 실행 안내

기존 승인 범위에서만 자동 검토를 실행한다. [AGENTS.md](AGENTS.md), [공통 실험 계약](COMMON_EXPERIMENT_RECORDS.md), [현재 입력·호출 계약](docs/agent/AUTO_REVIEW_CONTRACT.md#현재-입력호출-계약)을 포함한 상세 계약 전체를 먼저 읽는다. 입력 상한·단계별 호출 수·전송/격리 방식의 정본은 해당 현재 계약이며 이 안내에 다른 수치를 복사하지 않는다. 이 문서는 새 개발·학습·외부 호출 승인이 아니다.

## 실행과 근거

프로젝트 루트에서 실행하며 실제 학습·모델 비교·사진 추론·자동 검토는 기본 checkout의 현재 메인 한 곳에서 직렬로 수행한다. 구현 worktree에서 실제 호출을 시작하지 않는다.

```sh
./review --auto
```

기존 `./review`는 기본 1회 검토·다음 할 일 정리를 유지한다. `./review --interactive`의 수동 경로도 유지한다. 자동화는 해당 프로세스가 실행되는 동안만 진행하며 현재 채팅 자체가 LangGraph 안에서 실행되는 것은 아니다.

실행 전 표시되는 모델·전달 근거·최대 호출과 실제 journal을 확인한다. 현재 전송·심판·격리 학습/별도 평가·소스 채택/폐기·중단/재개 조건은 [상세 계약](docs/agent/AUTO_REVIEW_CONTRACT.md) 전체와 AGENTS.md를 따른다. 과거 초기 연결 순서나 생성 worker의 직접 평가 설명으로 현재 격리를 대체하지 않는다.

## 저장·재개

`artifacts/manual-cross-review/<검토 ID>/`:

- `packet.json`, `state.sqlite`, `result.json`: 기존 증거·LangGraph 체크포인트·반론과 채택 실험.
- `automation.json`: 자동 개발 상태, 채택 근거, 공통 실험 위치, 복원 여부.
- `codex/*/input.json`, `call.json`, `answer.json`: 단계별 입력·요청 상태·응답·실제 usage. `answer.json`은 실제 CLI 실행 시 생성됩니다.
- `implementation/plan.json`, `apply.json`, `*-before.py`, `worker.py`: 사전 기준·적용 트랜잭션·원본·실행 코드.
- `token_report.json`, `next_steps.md`: 제공자별 사용량과 다음 할 일.

공통 실험 폴더에는 plan/result/record, 원본·변경 diff와 `comparison.html`이 남습니다. HTML은 사진 식별 해시가 맞는 경우 사진과 구역을 함께 표시합니다. 사진이 없거나 불일치하면 그 제한을 표시합니다.

같은 명령을 다시 실행하면 완료된 Gemini/Codex 요청을 반복하지 않습니다. 완료 전 중단된 요청은 결과 불명으로 보존하여 자동 재시도하지 않습니다. 학습 시작 여부가 불명확한 경우도 학습을 다시 시작하지 않습니다. 사람 라벨·새 근거·사용자 코드 충돌이 필요하면 기록을 확인한 뒤 해결해야 합니다. 강제 종료 후 코드가 남아 있으면 원본 snapshot과 현재 변경을 비교하세요.

동일 증거+모델+프롬프트의 응답을 재사용하며 Codex 단계도 입력 해시로 재사용합니다. 자료가 바뀌면 새 검토입니다. 실험 결과가 나왔다고 새 토론을 자동 시작하지 않습니다.

## 사용량과 현재/과거 구분

Codex와 Gemini usage는 별도로 기록하며 미확인은 0이 아니라 null이다. 캐시 입력은 전체 입력의 일부이고 reasoning도 이중 합산하지 않는다. 현재 채팅의 사용량은 별도 CLI 기록과 구분한다. 토큰 절감이나 합의는 모델 성능 개선의 근거가 아니다.

[정리 전 안내 전체](docs/history/AUTO_DEVELOPMENT_BEFORE_LIMIT_CLARITY_20261118.md)는 당시 수치·연결 방식·실측 이력의 보존본이다. 현재 실행 계약을 대신하지 않는다. 과거 API 입력·실패 기록·체크포인트는 덮어쓰지 않는다.
