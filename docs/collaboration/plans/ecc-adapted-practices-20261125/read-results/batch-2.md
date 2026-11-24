# batch-2 결과 (38개)

## A. 전체 판정표

| 스킬 | 한 줄 요지 | 판정 | 끝까지 읽음 |
|---|---|---|---|
| click-path-audit | 버튼 핸들러 호출 순서별 상태 설정/초기화 지도로 "서로 무효화" 버그 찾기 | 참고만 (라벨 병합 단계가 미확인 값을 덮어쓰는지 점검하는 발상만) | 예 |
| clickhouse-io | ClickHouse 스키마·쿼리 패턴 | 무관 | 예 |
| code-tour | CodeTour .tour 파일 작성 | 무관 | 예 |
| codebase-onboarding | 새 저장소 분석 후 온보딩 가이드·CLAUDE.md 생성 | 무관 | 예 |
| codehealth-mcp | CodeScene MCP 구조 점수 게이트 | 무관 | 예 |
| coding-standards | TS/React 중심 일반 코딩 규칙 | 무관 | 예 |
| competitive-platform-analysis | 경쟁사 집합 선정·등급화 | 무관 | 예 |
| competitive-report-structure | 경쟁 분석 보고서 구성("합산 총점 열 금지") | 참고만 (지표를 합산하지 말고 따로 보고하는 원칙은 이미 갖춤) | 예 |
| compose-multiplatform-patterns | Kotlin Compose UI 패턴 | 무관 | 예 |
| config-gc | ~/.claude 설정 정리(하나씩 확인·소프트 삭제) | 무관 | 예 |
| config-health | 훅 연결 점검, "판단 못 한 항목 수를 함께 출력" 원칙 | 참고만 (아래 data-throughput 후보의 보조 근거) | 예 |
| configure-ecc | ECC 설치 마법사 | 무관 | 예 |
| connections-optimizer | X·LinkedIn 인맥 정리 | 무관 | 예 |
| content-engine | SNS 콘텐츠 작성 | 무관 | 예 |
| content-hash-cache-pattern | 파일 내용 SHA-256 기준 캐시(경로 무관, 내용 바뀌면 자동 무효) | 후보 | 예 |
| context-and-decisions | 도메인 용어집(확정·미확정 구분)과 결정 기록 분리 | 후보 | 예 |
| context-budget | 컨텍스트 사용량은 기본 명령으로 안내 | 무관 | 예 |
| continuous-agent-loop | 자율 루프 선택·실패 유형 | 무관 (같은 원인 반복 재시도 경고는 이미 갖춤) | 예 |
| continuous-learning-v2 | 훅 기반 instinct 자동 학습 | 무관 (원하지 않는 유형) | 예 |
| continuous-learning | v1, 폐기됨 | 무관 | 예 |
| contract-first | 하나의 기계 검사 가능한 계약(OpenAPI 등)으로 경계 맞추기 | 참고만 (null·빈 값 의미 명시는 라벨 프로토콜에 이미 있음) | 예 |
| conventional-commit-review | 커밋 메시지 작성 | 무관 | 예 |
| cost-aware-llm-pipeline | 모델 라우팅·예산·재시도 | 무관 (정확도와 무관한 비용 최적화) | 예 |
| cost-tracking | 토큰 비용 로그 집계 | 무관 | 예 |
| council-multi-model | council 초안을 외부 Codex가 비판 | 무관 (Codex·Gemini 검토 연결이 이미 있음) | 예 |
| council | 4개 관점 독립 의견 후 종합, 앵커링 방지 | 참고만 (독립 판정 2회·자동 검토로 이미 갖춤) | 예 |
| counterparty-channel-discipline | 외부 채널에서 에이전트 발화 통제 | 무관 | 예 |
| cpp-coding-standards | C++ Core Guidelines | 무관 | 예 |
| cpp-testing | GoogleTest/CTest | 무관 | 예 |
| crosspost | 여러 SNS에 맞춰 게시 | 무관 | 예 |
| csharp-testing | xUnit 테스트 패턴 | 무관 | 예 |
| customer-billing-ops | Stripe 결제 운영 | 무관 | 예 |
| customs-trade-compliance | 관세 분류(GRI 순서 규칙)·통관 | 무관 (규칙을 정해진 순서로 적용하고 근거를 남기는 발상은 라벨 지침에 이미 있음) | 예 |
| dart-flutter-patterns | Dart/Flutter 패턴 | 무관 | 예 |
| dashboard-builder | 운영 질문 중심 모니터링 대시보드 | 무관 | 예 |
| data-scraper-agent | 스크래핑+Gemini 보강+피드백 학습 | 참고만 (배치 응답을 순서로만 맞추고 실패 시 조용히 넘어감, 318-327행: AI 판정자 배치 호출 때 피할 함정) | 예 |
| data-throughput-accelerator | 대량 데이터 이동, 단계별 개수 "회계 블록"으로 정합성 증명 | 후보 | 예 |
| database-migrations | DB 마이그레이션 안전 패턴 | 무관 | 예 |

## B. 후보 상세

### 1. context-and-decisions
- origin·license: frontmatter에 origin 표기 없음. 본문 Attribution(90-92행)에 Matt Pocock의 MIT `domain-modeling` 스킬을 각색했다고 적힘.
- 관점: 4, 2
- 근거 구간: 13-32행. "Mark unconfirmed items as `needs confirmation`; do not guess." (22행)
- 채우는 빈자리: kappa가 0.47~0.62다. (비공개 작업 선호)는 출력 규칙일 뿐이다. 사용자와 **합의한 판정 용어 정의**(예: 화이트닝 결함과 정상 광택 경계, 관찰 제한과 미확인, 카드 단위와 구역 단위 오탐)를 한 곳에 두고 확정/미확정을 표시하는 장치는 없다. 라벨 프로토콜은 라벨 처리 절차이고 용어 정의는 아니다.
- 각색: 기존 라벨 지침 문서 안에 "판정 용어" 절을 두고 용어마다 1~2문장 정의, 근거 라벨 예시 ID, `확인 필요` 표시를 단다. 에이전트는 사용자의 짧은 요청이 이 정의와 어긋나면 구체적 상황으로 한 번 되묻는다(29-30행 방식). 새 파일 생성은 사용자 승인을 받은 뒤에만 한다(13행 규칙과 같음).
- 확신도: 중간. 반대 근거: 용어집이 kappa나 누락률을 개선한다는 증거는 없다. 정의를 확정하려면 사람 시간이 든다.

### 2. data-throughput-accelerator (보조: config-health)
- origin·license: origin "ECC", license "MIT"(4-5행). config-health는 origin "ECC", license 표기 없음.
- 관점: 3, 1
- 근거 구간: 52-73행(회계 블록, 가드레일), config-health 248-255행. "Do not skip failed files silently." (70행)
- 채우는 빈자리: AGENTS.md는 성능 보고에 분모를 요구한다. 그러나 사진→카드 검출→구역 크롭→라벨 있음→미확인/관찰 제한 제외→평가 분모로 **단계마다 몇 건이 빠졌는지** 적는 고정 양식은 없다. 남은 오류 중 "사진 조건 5건"(카드 홀더·저해상도 크롭)처럼 크롭 실패나 제외가 조용히 생기면 분모가 바뀌어 비교가 무효가 된다. config-health의 "판단 못 한 항목 수를 함께 출력" 원칙(253-255행)과 같은 취지다.
- 각색: 평가 보고와 observations.json에 단계별 개수와 제외 사유별 개수를 고정 필드로 넣는다. 이전 실험과 단계별 개수가 다르면 "분모 변경"으로 표시하고 %p 비교를 막는 점검 규칙을 둔다.
- 확신도: 중간. 반대 근거: 실험 실행기와 required_cohorts가 이미 고정 평가 ID를 강제하고 있다면 이 양식은 이미 있는 것과 겹친다(이번 묶음에서는 프로젝트 코드를 보지 않아 확인하지 못함).

### 3. content-hash-cache-pattern
- origin·license: origin "ECC", license 표기 없음.
- 관점: 3
- 근거 구간: 21-45행, 158-162행. "Results that depend on parameters beyond file content" (162행, 캐시를 쓰지 말아야 할 경우)
- 채우는 빈자리: (a) 고정 backbone 특징을 캐시한다면 키에 크롭·여백·방향 통일 설정이 빠졌을 때, 다른 설정의 특징이 섞여 "모델 변형 미채택" 결론이 오염될 수 있다. 162행이 이 함정을 직접 짚는다. (b) 내용 해시는 같은 사진 파일이 다른 판매글·카드 ID로 학습과 평가에 동시에 들어가는 누수를 찾는 데도 쓸 수 있다. (b)는 스킬 본문에 없는 내 응용이다.
- 각색: 특징 캐시 키를 "이미지 내용 해시 + 크롭/전처리 설정 해시 + backbone ID"로 정하는 규칙을 둔다. 그룹 분리 검사에 "같은 내용 해시가 학습과 평가에 동시에 있으면 실패" 항목을 더한다.
- 확신도: 낮음. 반대 근거: 현재 캐시 키 구조와 그룹 분리 방식을 확인하지 않았다. 바이트가 같은 중복만 잡히므로, eBay 재압축본을 잡으려면 지각 해시(perceptual hash)가 따로 필요하다.

## C. 묶음 메모
- origin 표기가 ECC가 아닌 스킬: click-path-audit·codehealth-mcp·cost-tracking·data-scraper-agent(community), conventional-commit-review(personal), dashboard-builder(ECC direct-port adaptation). competitive-platform-analysis·competitive-report-structure·context-and-decisions·counterparty-channel-discipline은 origin 표기가 없다. customs-trade-compliance는 Apache-2.0, author "evos".
- 프롬프트 주입 의심 문구는 없었다. 다만 configure-ecc·continuous-learning-v2·config-health·codehealth-mcp에는 설치·훅 등록·npx 실행 지시가 있다(따르지 않음). council-multi-model은 외부 OpenAI 전송 절차를 담고 있다.
- data-scraper-agent의 피드백 학습(사용자 선택을 프롬프트에 예시로 넣는 방식)을 AI 판정자에 옮기면 앵커링이 생겨 사람 라벨과 분리하는 원칙이 깨진다. 반면교사로만 본다.
