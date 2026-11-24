# batch-8 결과 (44개)

## A. 전체 판정표

| 스킬 | 한 줄 요지 | 판정 | 끝까지 읽음 |
|---|---|---|---|
| react-testing | RTL·Vitest·MSW로 React 컴포넌트 행동 테스트 | 무관 | 예 |
| recsys-pipeline-architect | 추천/랭킹 6단계 파이프라인(Source→…→SideEffect) 설계 | 무관 | 예 |
| recursive-decision-ledger | 반복 시도마다 후보에 accept/watch/reject/needs replay 표시를 남기는 추가 전용 기록, 확신만으로 승격 금지 | 후보 | 예 |
| redis-patterns | Redis 캐시·락·속도 제한·스트림 패턴 | 무관 | 예 |
| regex-vs-llm-structured-text | 값싼 규칙 추출 후 확신도 낮은 항목만 LLM 검증으로 보내는 혼합 파이프라인 | 후보 | 예 |
| remotion-video-creation | Remotion(React 영상) 규칙 파일 색인 | 무관 | 예 |
| repo-scan | 외부 repo-scan 스킬 설치 안내 스크립트(코드 자산 감사) | 무관 | 예 |
| research-ops | 최신 정보 조사 시 출처 사실/사용자 제공/추론/권고를 구분해 보고 | 참고만 | 예 |
| returns-reverse-logistics | 반품 검수 등급(A~D)·처분·사기 점수, 검수 등급 재감사 일치율 목표(>95%, 경보 <88%) | 참고만 | 예 |
| roundhouse-x402 | x402 결제 서비스 색인·MCP·정산 설정 | 무관 | 예 |
| rules-distill | 여러 스킬에 반복되는 원칙을 규칙 파일로 승격(2개 이상 근거·위반 위험 필수) | 참고만 | 예 |
| rust-patterns | Rust 소유권·오류 처리·동시성 관용구 | 무관 | 예 |
| rust-testing | Rust 단위·통합·속성 기반 테스트 | 무관 | 예 |
| safety-guard | 파괴적 명령 확인·쓰기 디렉터리 고정(권고형) | 무관 | 예 |
| santa-method | 같은 채점표를 쓰는 독립 검토자 2명이 모두 통과해야 출고, 검토자 일치율로 채점표 점검 | 참고만 | 예 |
| scientific-db-openalex-database | OpenAlex 문헌 검색 API와 검색 기록 | 무관 | 예 |
| scientific-db-pubmed-database | PubMed E-utilities 검색 | 무관 | 예 |
| scientific-db-uspto-database | USPTO 특허·상표 기록 조회 | 무관 | 예 |
| scientific-pkg-gget | gget 유전체 DB 조회 | 무관 | 예 |
| scientific-thinking-literature-review | 체계적 문헌 검토 절차(질문=대상·방법·비교 기준·지표, 검색 기록, 선별) | 참고만 | 예 |
| scientific-thinking-scholar-evaluation | 논문 평가 9차원 채점표(타당성 위협 포함) | 참고만 | 예 |
| search-first | 코드 작성 전 기존 도구·패키지 검색 | 무관 | 예 |
| security-bounty-hunter | 보상 대상 원격 취약점 탐색 | 무관 | 예 |
| security-review | 웹 앱 보안 점검표(비밀값·입력 검증·XSS 등) | 무관 | 예 |
| security-scan | AgentShield로 .claude 설정 보안 검사 | 무관 | 예 |
| seo | 검색 노출 개선 점검 | 무관 | 예 |
| short-video-distribution | 세로 영상 TikTok·Shorts·Reels 게시 | 무관 | 예 |
| skill-comply | 프롬프트 지원 강도 3단계로 에이전트의 규칙 준수율 측정 | 참고만 | 예 |
| skill-host-compat | ECC 스킬의 Codex/Cursor 호환 검사 | 무관 | 예 |
| skill-scout | 새 스킬 만들기 전 기존 스킬 검색 | 무관 | 예 |
| skill-stocktake | 설치된 스킬 품질 감사(Keep/Improve/Retire) | 무관 | 예 |
| social-graph-ranker | 인맥 그래프 기반 소개 경로 점수 | 무관 | 예 |
| social-publisher | SocialClaw로 SNS 예약 게시 | 무관 | 예 |
| springboot-patterns | Spring Boot 계층 구조·API 패턴 | 무관 | 예 |
| springboot-security | Spring Security 점검 | 무관 | 예 |
| springboot-tdd | Spring Boot TDD | 무관 | 예 |
| springboot-verification | Spring Boot 빌드·정적 분석·테스트 검증 루프 | 무관 | 예 |
| story-lifecycle | 파일 기반 에픽→스토리→스프린트 관리(수용 기준 양식) | 참고만 | 예 |
| strategic-compact | 작업 단계 경계에서 수동 컨텍스트 압축 | 무관 | 예 |
| swift-actor-persistence | Swift actor 기반 저장소 | 무관 | 예 |
| swift-concurrency-6-2 | Swift 6.2 동시성 | 무관 | 예 |
| swift-protocol-di-testing | Swift 프로토콜 DI 테스트 | 무관 | 예 |
| swiftui-patterns | SwiftUI 상태·탐색 패턴 | 무관 | 예 |
| taste-application | 스타일 팩 기반 영상 생성·색보정·편집, 분포 모양 검증·단위 함정 | 참고만 | 예 |

## B. 후보 상세

### 1. regex-vs-llm-structured-text
- origin: ECC / license: 표기 없음
- 관점: 1(사람 시간 병목), 3(판정 보류·확신도 기반 분기)
- 근거 구간: 29-46줄(구조), 86-127줄(확신도 점수), 155-184줄(혼합 파이프라인), 198-205줄(지표 기록). 인용: "Use confidence scoring to programmatically identify what needs LLM help" (200줄)
- 채우는 빈자리: 지금은 AI 판정자가 보조 라벨을 붙이고 사람이 라벨을 붙이지만, 어떤 구역을 AI 판정·사람 확인으로 보낼지 정하는 규칙이 브리프에 없다. 새 라벨은 사람 시간에 막혀 있으므로, 모델 확신도가 경계 근처인 구역만 AI 판정→사람 확인 순서로 보내고 분기 비율·호출 수를 기록하는 방식이 바로 그 병목을 겨냥한다. 이미 있는 2회 독립 AI 판정+병합은 "어떻게 판정하나"이고, 이것은 "무엇을 판정 대상으로 고르나"라서 겹치지 않는다.
- 각색: 라벨 프로토콜에 "모델 점수가 미리 정한 불확실 구간에 든 구역만 AI 판정 대기열로, AI 판정과 모델이 어긋난 구역만 사람 확인 대기열로 보낸다. 분기 수·비율은 매 회차 기록하고, 이렇게 고른 구역은 평가용 분모와 섞지 않는다"를 한 단락으로 추가한다.
- 확신도: 중간. 반대 근거: 오탐 9장 중 일부는 모델이 높은 확신으로 틀렸을 수 있어 확신도 분기가 이를 놓칠 수 있다. 또 고른 구역이 학습·평가 분포를 치우치게 만드는 선택 편향 위험이 있다(평가 분리 필수).

### 2. recursive-decision-ledger
- origin: ECC / license: MIT
- 관점: 1(같은 개발 자료 반복 실험의 우연 통과), 3(실험 관리)
- 근거 구간: 17-30줄(기록 항목), 34-43줄(시도 루프·표시 종류·강등), 45-55줄(이전 채택안과의 일치 표시), 65-71줄(승격 조건). 인용: "Mark each candidate: accept, watch, reject, decay watch, or needs replay." (39줄)
- 채우는 빈자리: 실험 실행기는 실험 하나마다 통과/실패를 기록하지만, 변형 3개 연속 미채택처럼 실험 사이에 걸친 후보 상태를 관리하는 칸은 브리프에 없다. 개발 자료에서만 통과한 변형을 "채택"이 아니라 "watch(새 독립 라벨이 생기면 재검증 필요)"로 남기고, 새 자료가 오면 그 목록부터 재검증하면 같은 자료로 재실험하는 유혹을 줄인다. 우연 판별 도구는 한 결과의 우연 여부를 보고, 이것은 후보 목록의 상태 변화를 본다.
- 각색: 기존 record.json 옆에 한 줄씩 추가하는 후보 상태 표(가설 ID·현재 표시[채택/관찰/기각/재검증 필요]·근거 기록 경로·다음 재검증 조건)를 문서 양식으로 둔다. 표시 강등(관찰→기각)은 새 자료 결과로만 하고, 확신 표현만으로 승격하지 않는다고 명시한다.
- 확신도: 낮음~중간. 반대 근거: 사전 등록 실행기·얻어걸린 향상 금지 규칙이 정신은 이미 담고 있어, 새 표 하나가 관리 부담만 늘릴 수 있다.

## C. 묶음 메모
- ECC가 아닌 출처: recsys-pipeline-architect·repo-scan·roundhouse-x402·scientific-db-pubmed/uspto·scientific-pkg-gget·scientific-thinking-*·skill-scout·social-publisher·story-lifecycle(community), santa-method(개인 저자), scientific-db-openalex(OpenAlex). remotion-video-creation·swift-concurrency-6-2·swiftui-patterns는 origin 표기 없음.
- 설치·외부 호출 지시(repo-scan 설치 스크립트, roundhouse 유료 호출, social-publisher npm 설치, security-scan npx)가 있으나 자료로만 읽고 실행하지 않았다. 명백한 프롬프트 주입 문구는 없었다.
- 참고만 중 santa-method의 "검토자 일치율이 낮으면 채점표를 좁힌다"(295줄)는 진행 중인 AI 판정 일관성 확인과 겹쳐 후보에서 뺐다.
