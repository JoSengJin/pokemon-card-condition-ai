# Pokemon Card Condition — experimental

독립 카드 상태 분석 모델 연구 프로젝트입니다. 구현·개발 평가·독립 검증·운영 채택은 구분합니다. 현재 점수와 기준 버전은 [개발 진척 JSON](development-progress.json), 완료 조건·배점·근거는 [고정 진척 기준](PROGRESS_CRITERIA.md)이 정본입니다. 이 문서에는 과거 진척 수치를 복사하지 않습니다.

## 에이전트 작업 시작

Codex와 Claude 모두 [AGENTS.md](AGENTS.md)를 읽고 [작업별 필독 경로](docs/AGENT_START.md)에서 이번 작업의 문서를 확인합니다. Claude용 [CLAUDE.md](CLAUDE.md)는 동일한 AGENTS.md만 가져옵니다. 현재 배정 계약과 실제 Git·잠금·실행 기록이 날짜별 인계보다 우선합니다. 문서를 읽었다는 사실은 새 작업·실험·외부 AI 호출 승인이 아닙니다.

| 작업 | 필독 문서 |
|---|---|
| 구현·페어코딩·통합·역할 교대 | [PAIR_CODING.md](PAIR_CODING.md), 현재 배정 task |
| 모델·worker 수정 및 실험 | [공통 실험 계약](COMMON_EXPERIMENT_RECORDS.md), 승인된 계획, [설계 원칙](OBSERVATION_CONSENSUS_20261011.md) |
| 사람 라벨·모호한 흔적 | [라벨 규약](LABELING_PROTOCOL.md), 해당 사람 응답·사진 근거 |
| 자동 교차 검토·재개 | [자동 검토 상세 계약](docs/agent/AUTO_REVIEW_CONTRACT.md), [자동 개발 안내](AUTO_DEVELOPMENT_20261020.md) |
| 성과·진척 보고 | [HTML 보고 계약](docs/collaboration/HTML_REPORTING.md), 진척 JSON·고정 기준 |

각 행은 AGENTS.md의 공통 제한에 추가됩니다. 한 작업이 여러 행에 해당하면 관련 문서를 모두 읽습니다. 상세 계약의 일부만 발췌해 보호 조건을 생략하지 않습니다.

## 설치 및 코드 검사

Python 3.11+와 checkout별 독립 가상환경을 사용합니다. [검증된 의존성 목록](requirements-tested.txt)과 [프로젝트 의존성](pyproject.toml)을 먼저 확인합니다.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[cross-review]'
.venv/bin/python -m unittest discover -s tests -v
```

이 명령은 설치와 코드 검사입니다. 실제 학습·사진 추론·외부 AI 호출은 각 작업의 기존 승인·사전 계획·잠금·호출 제한에 따라 별도로 수행합니다. 모델·worker 소스 편집은 `./develop -- <수정 명령>`, 새 실험은 `./experiment --plan <계획.json> -- <실행 명령>`을 사용합니다. 과거 문서의 직접 학습 명령으로 공통 실행기를 우회하지 않습니다.

## 로컬 경로 설정

명령은 저장소 루트에서 실행합니다. 외부 PokeCollector 수집 연동을 승인받은 작업에서만 실제 로컬 경로를 지정합니다.

```sh
export POKECOLLECTOR_ROOT="/path/to/pokecollector"
```

이 값은 셸에서 기존 `--consumer-root "$POKECOLLECTOR_ROOT"` 인자로 전달합니다. 프로그램이 자동으로 읽는 새 설정은 아닙니다. 기본 사진 수집에는 DB가 필요하지 않습니다. 승인된 외부 비전 선별에서만 실제 쿼터 SQLite 경로를 `POKECOLLECTOR_QUOTA_DB`로 설정하고 `--quota-db "$POKECOLLECTOR_QUOTA_DB"`로 전달합니다. 개인 경로·키를 커밋하지 않습니다.

## 사용 안내·과거 기록

- [기존 전체 사용 안내와 변경 이력](docs/history/README_BEFORE_AGENT_GUIDE_20261118.md): 정리 전 README의 전체 내용을 보존했습니다. 버전별 설명·수치·명령은 당시 기록이며 현재 동작·승인·모델 성능을 보장하지 않습니다. 현재 CLI 도움말·구현·배정 계약과 대조합니다.
- [문서 보관함](docs/history/README.md): 루트에서 이동한 보고서와 경로 대응표입니다.
- [실험 기록](COMMON_EXPERIMENT_RECORDS.md): 계획·관측·상태·동일 평가·필수 회귀 계약입니다.
- [검토 화면](REVIEW_CHAT.md), [교차 검토 사용 안내](LANGGRAPH_USAGE_GUIDE_KO.md): 실행 전에 현재 승인·설정·기록을 확인합니다.
- [페어코딩 관제 안내](tools/pair-control/README.md): 표시·배정·실행 권한의 차이는 PAIR_CODING.md를 따릅니다.
