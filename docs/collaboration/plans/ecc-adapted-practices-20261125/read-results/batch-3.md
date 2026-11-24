# batch-3 결과 (37개)

## A. 전체 판정표

| 스킬 | 한 줄 요지 | 판정 | 끝까지 읽음 |
|---|---|---|---|
| deep-research | firecrawl/exa로 하위 질문별 웹 조사 후 출처 인용 보고서 작성 | 참고만 (사실/추정 분리·단일 출처 표시 규칙은 이미 "가정 금지·근거 인용"과 겹침) | 예 |
| deepseek-harness-setup | DeepSeek Harness에 ECC 스킬·훅 연결 설치법 | 무관 | 예 |
| defi-amm-security | Solidity AMM 보안 점검표 | 무관 | 예 |
| delivery-gate | Stop 훅으로 학습 기록·디스크 확인 전 종료 차단 | 무관 (훅 설치형) | 예 |
| deployment-patterns | 배포 전략·Docker·CI/CD·헬스체크·롤백 점검표 | 무관 | 예 |
| design-system | UI 디자인 토큰 추출·시각 감사 | 무관 | 예 |
| dev-team | PM/설계/개발/QA 4역할 병렬 의견 + 종합 | 참고만 ("갈등을 평균내지 말고 명시" 규칙은 AI 판정 병합에도 통하나 기존 병합 절차와 겹침) | 예 |
| devfleet | DevFleet MCP로 다중 에이전트 worktree 배정 | 무관 (자동 오케스트레이션) | 예 |
| django-celery | Django+Celery 비동기 작업 패턴 | 무관 | 예 |
| django-patterns | Django/DRF 구조·ORM 패턴 | 무관 | 예 |
| django-security | Django 보안 설정 | 무관 | 예 |
| django-tdd | pytest-django TDD·factory_boy | 무관 | 예 |
| django-verification | Django 출시 전 12단계 검증 보고 | 무관 | 예 |
| dmux-workflows | tmux 기반 다중 에이전트 병렬 실행 | 무관 (페어코딩 계약이 이미 있음) | 예 |
| docker-patterns | Docker Compose·컨테이너 보안·설치 시험 하네스 | 무관 | 예 |
| docs-governance | 문서 역할·링크·ADR 읽기 전용 감사 라우터 | 무관 | 예 |
| documentation-lookup | Context7 MCP로 최신 라이브러리 문서 조회 | 무관 | 예 |
| dotnet-patterns | C#/.NET 관용 패턴 | 무관 | 예 |
| dynamic-workflow-mode | 작업별 임시 하네스 계약(목표/하지 않을 것/입력/평가/인계) | 참고만 (요청 명세 틀로 쓸 수 있으나 기존 사전 등록 실험 계획·writing-plans와 대부분 겹침) | 예 |
| e2e-testing | Playwright E2E·불안정 테스트 격리 | 참고만 (반복 실행으로 불안정 판별 = 이미 갖춘 우연 판별 진단과 같은 생각) | 예 |
| ecc-contribution-review | ECC 스킬 기여 검토 묶음 작성 | 무관 | 예 |
| ecc-guide | ECC 저장소 안내 | 무관 | 예 |
| ecc-recipes | ECC 명령 묶음 실행 순서 안내 | 무관 | 예 |
| ecc-tools-cost-audit | ECC Tools 앱 비용 폭주 감사 | 참고만 (변경/검증/푸시 상태를 구분하는 보고 규칙은 이미 있음) | 예 |
| email-ops | 메일함 분류·초안·발송 확인 | 무관 | 예 |
| energy-procurement | 기업 전력·가스 조달 전문 지식 | 무관 | 예 |
| enterprise-agent-ops | 상시 실행 에이전트 운영 통제 | 무관 | 예 |
| error-handling | TS/Python/Go 오류 처리 패턴 | 무관 | 예 |
| esign-field-placement | 전자서명 필드 좌표 보정·발송 차단 절차 | 참고만 (좌표 보정을 독립 기준점으로 검증하는 생각은 크롭 좌표에 비유 가능하나 직접 정체 항목과 무관) | 예 |
| eval-harness | 평가 주도 개발, pass@k / pass^k 신뢰도 지표, 채점자 종류 | **후보** | 예 |
| evm-token-decimals | EVM 토큰 소수점 불일치 방지 | 무관 | 예 |
| exa-search | Exa MCP 신경망 검색 | 무관 | 예 |
| fal-ai-media | fal.ai 이미지·영상·음성 생성 | 무관 | 예 |
| fastapi-patterns | FastAPI 구조·Pydantic·테스트 | 무관 | 예 |
| finance-billing-ops | 매출·과금 사실과 코드 동작 분리 보고 | 참고만 | 예 |
| flox-environments | Flox(Nix) 재현 개발 환경 | 무관 | 예 |
| flutter-dart-code-review | Flutter/Dart 코드 리뷰 점검표 | 무관 | 예 |

## B. 후보 상세

### 1. eval-harness
- origin: ECC (metadata.origin), license: 표기 없음
- 관점: 1(AI 판정자 일관성 정체), 3(라벨 잡음·판정 보류·작은 자료 평가 통계)
- 근거 구간: 95~105줄(pass@k, pass^k 정의), 284~299줄(권장 기준·평가 안티패턴). 인용: "pass^k — All k trials succeed — Higher bar for reliability"
- 채우는 빈자리: AI 판정자는 이미 "2회 독립 판정 + 병합"을 하지만, 병합 규칙이 "한 번이라도 결함이면 결함"(OR) 쪽이면 이는 pass@k 방식이라 반복 횟수가 늘수록 결함 판정이 부풀어 오른다. 반대로 pass^k(k회 모두 같은 판정)는 안정성 기준이다. 둘을 구분해 쓰는 규칙과, 크롭별 k회 일치율을 판정자 신뢰도 숫자로 기록하는 틀은 "이미 갖춘 것"에 없다. 진행 중인 판정 일관성 확인에 바로 쓸 수 있는 정의다. 291~299줄의 "알려진 평가 예시에 프롬프트를 과적합하지 말 것"도 같은 크롭으로 판정 프롬프트를 계속 고치는 위험에 맞는다.
- 각색 방법: AI 판정 규칙에 "보조 라벨로 채택하려면 k회(예: 3회) 독립 판정이 모두 같아야 한다(pass^k). 엇갈린 크롭은 'AI 불확실'로 따로 두고, 학습 라벨에도 사람 라벨에도 섞지 않는다"를 넣는다. 판정 일관성 보고에는 크롭별 k회 일치율과, OR 병합을 썼다면 그 결함 비율을 단일 판정 결함 비율과 나란히 적는다.
- 확신도: 중간. 반대 근거: 실제 병합 규칙이 OR인지 이 묶음에서는 확인하지 못했다. 이미 만장일치를 요구한다면 새로 더해지는 것은 일치율 지표뿐이다. k회 반복에는 모델 호출 비용도 든다.

## C. 묶음 메모
- origin이 ECC가 아닌 스킬: deepseek-harness-setup·dev-team·devfleet·ecc-guide(community), flox-environments(Flox), ecc-recipes(community, author 표기), docker-patterns·esign-field-placement(origin 표기 없음). energy-procurement만 license(Apache-2.0)를 적었다.
- 프롬프트 주입 의심 문구는 없었다. 다만 delivery-gate·dmux-workflows·docker-patterns 등이 설치·실행 명령을 담고 있어 실행하지 않았다.
- 이 묶음은 웹·배포·타 언어 스택 위주라 결과가 1개뿐인 것이 정상이다.
