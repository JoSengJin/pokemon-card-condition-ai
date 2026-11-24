# batch-5 판정 결과 (31개)

## A. 전체 판정표

| 스킬 | 한 줄 요지 | 판정 | 끝까지 읽음 |
|---|---|---|---|
| inventory-demand-planning | 소매 수요예측·안전재고·ABC/XYZ 분류·예측 정확도 지표 | 후보 | 예 |
| investor-materials | 투자 자료를 단일 사실 원본에 맞춰 일관 작성 | 참고만 | 예 |
| investor-outreach | 투자자 콜드메일·후속 메일 작성 규칙 | 무관 | 예 |
| ios-icon-gen | SF Symbols/Iconify로 Xcode 아이콘 생성 | 무관 | 예 |
| issue-review | GitHub 이슈 분류·검증·확신도 4단계·중복은 원인 기준 판정 | 후보 | 예 |
| iterative-retrieval | 하위 에이전트 맥락을 최대 3회 반복 검색으로 좁힘 | 무관 | 예 |
| ito-baskets | 예측시장 바스켓 읽기 전용 비교(match/conflict/missing/stale)·출처 기록 | 후보 | 예 |
| ito-compute | GPU 견적 요청 CLI 경계 설명 | 무관 | 예 |
| ito-inference | 추론 서빙 미지원 경계·확인 게이트 설계 | 무관 | 예 |
| ito-training | 학습 미지원 경계, 평가셋 오염 제거·실패 게이트 무시 금지 | 참고만 | 예 |
| java-coding-standards | Spring/Quarkus 자바 코딩 규칙 | 무관 | 예 |
| jira-integration | Jira 티켓 조회·요구사항/수용기준 추출·상태 갱신 | 참고만 | 예 |
| jpa-patterns | JPA/Hibernate 엔티티·쿼리 패턴 | 무관 | 예 |
| knowledge-ops | 다층 지식 저장소 수집·중복 제거·동기화 | 무관 | 예 |
| kotlin-coroutines-flows | 코틀린 코루틴·Flow 패턴 | 무관 | 예 |
| kotlin-exposed-patterns | Exposed ORM 패턴 | 무관 | 예 |
| kotlin-ktor-patterns | Ktor 서버 패턴 | 무관 | 예 |
| kotlin-patterns | 코틀린 관용 패턴 | 무관 | 예 |
| kotlin-testing | Kotest/MockK·속성 기반 테스트·커버리지 | 참고만 | 예 |
| kubernetes-patterns | K8s 매니페스트·프로브·RBAC·디버깅 | 무관 | 예 |
| laravel-patterns | Laravel 구조 패턴 | 무관 | 예 |
| laravel-plugin-discovery | LaraPlugins MCP로 패키지 탐색 | 무관 | 예 |
| laravel-security | Laravel 보안 규칙 | 무관 | 예 |
| laravel-tdd | Laravel 테스트 작성 | 무관 | 예 |
| laravel-verification | Laravel 병합 전 검증 단계 | 무관 | 예 |
| latency-critical-systems | p50/p95/p99·신선도 분리 측정, 지연 최적화 | 무관 | 예 |
| lead-intelligence | 잠재고객 점수화·소개 경로·아웃리치 초안 | 무관 | 예 |
| leanrea | CLI 역공학, 주장을 seen/inferred/unknown으로 구분 | 참고만 | 예 |
| liquid-glass-design | iOS 26 Liquid Glass UI | 무관 | 예 |
| living-docs-governance | 문서 4역할(헌법·지도·상태·이력)과 삭제 구역 | 참고만 | 예 |
| llm-trading-agent-security | 거래 에이전트 지출 한도·시뮬레이션·차단기 | 무관 | 예 |

참고만 사유 요약: investor-materials(단일 원본 대조는 이미 progress json 정본 규칙과 겹침), ito-training(평가셋 오염 제거·게이트는 기존 그룹 분리·필수 회귀와 겹침), jira-integration(요청을 수용기준·엣지케이스로 바꾸는 양식은 Superpowers brainstorming/writing-plans와 겹침), kotlin-testing(속성 기반 테스트를 "회전·재압축해도 판정 불변" 같은 모델 불변성 검사로 옮길 여지는 있으나 스킬 자체는 ML을 다루지 않음), leanrea(seen/inferred/unknown 증거 등급은 issue-review 후보에 합쳐 다룸), living-docs-governance(삭제 구역+재검토 조건은 AGENTS.md의 "실패 가설 재요청 거절"과 대부분 겹침).

## B. 후보 상세

### 1. issue-review
- origin: ECC / license: 표기 없음
- 관점: 1, 3, 4
- 근거 구간: 149줄(확신도 confirmed/likely/unverified/refuted), 159줄(중복 판정 기준), 71~79줄(버그 보고 완결성 점검표), 177줄(NEEDS-INFO는 빠진 항목 명시). 인용: "duplicate only when the root cause matches, not merely the symptom" (issue-review, 159줄)
- 채우는 빈자리: 남은 오류 14장 분해(라벨 의심 5·사진 조건 5·모델 4)는 일회성 보고서이고, 각 분류가 얼마나 확실한지 등급이 없다. "사진 조건"처럼 증상이 같아도 원인이 다른 경우(홀더 반사 vs 저해상도 크롭)를 한 묶음으로 세면, 그 묶음을 겨냥한 실험이 엉뚱한 원인을 고친다. 기존 "가정 금지·근거 인용"은 일반 원칙이고, 오류 귀속에 4단계 확신도와 원인 기준 묶기를 적용하는 규칙은 아직 없다. 관점 4: (비공개)에 대해 에이전트가 완결성 점검표(재현 단계·기대/실제·대상 파일/SHA·환경)를 로그로 먼저 채우고, 빈 칸만 질문하는 형식으로 쓸 수 있다.
- 각색 방법: 오류 분해 보고 양식에 열 두 개(확신도 4단계, 근거 위치)를 추가하고, "같은 원인으로 묶으려면 같은 메커니즘 근거가 필요하며 증상 일치만으로 묶지 않는다"를 규칙으로 둔다. 실패 보고 대응에는 5칸 점검표를 두고, 로그로 확인되지 않은 칸만 사용자에게 묻는다.
- 확신도: 중간. 반대 근거: 오류가 14장뿐이라 확신도 등급을 매겨도 다음 실험 선택이 실제로 바뀌는지는 미확인이다.

### 2. ito-baskets (Compare 모드 + 출처 계약)
- origin: ECC / license: 표기 없음
- 관점: 2, 3
- 근거 구간: 132~143줄(결정적 정규화, 조용한 병합 금지, ID 우선 일치, 4분류), 173~185줄(source_type·as_of·freshness 출처 기록). 인용: "Classify each item `match`, `conflict`, `missing`, or `stale`." (ito-baskets, 140줄)
- 채우는 빈자리: 사람 라벨·AI 판정자 2회·병합 결과를 대조할 때, 지금은 사람/AI 주체만 기록한다("답 판정 주체 기록"). 최근 커밋(6c25e22, 18825ee)에서 코너 라벨 페이지의 결함 수준 문구가 바뀌었는데, 이 문구가 바뀌기 전에 붙인 라벨과 바뀐 뒤 라벨을 구분하는 "stale"(구버전 기준 라벨) 범주는 아직 없다. 감정 실무에서 등급 기준이 바뀐 뒤의 판정은 따로 관리하는 것과 같다. kappa 0.47~0.62의 일부가 기준 문구 버전 차이에서 오는지 분리해 볼 수 있다.
- 각색 방법: 구역 라벨마다 `label_protocol_version`(라벨 페이지 문구 버전·날짜)을 기록하고, 사람·AI 대조표를 match/conflict/missing(미확인)/stale(구버전 기준) 4칸으로 낸다. 같은 입력과 같은 기준일이면 같은 대조표가 나와야 한다는 결정성 검사를 둔다. stale도 자동으로 정답을 바꾸지 않고 표시만 한다(모델 오답으로 정답 변경 금지 규칙 유지).
- 확신도: 중간~낮음. 반대 근거: 기준 문구 변경이 실제 라벨 판단에 영향을 줬다는 증거는 아직 없다. 이미 대부분 라벨에 버전 정보를 복원할 수 없으면 효용이 작다.

### 3. inventory-demand-planning (out-of-time 검증 한 조각)
- origin: ECC / license: Apache-2.0
- 관점: 1, 3
- 근거 구간: 49줄(fitting에 쓴 자료가 아닌 holdout으로 최적화), 53줄(희소 자료에서 과적합, out-of-time 검증). 인용: "validate on out-of-time, not out-of-sample" (inventory-demand-planning, 53줄)
- 채우는 빈자리: 독립 시험 자료가 사실상 없고, 같은 개발 자료로 변형 3개를 반복 실험했다. 새 라벨이 묶음 단위로 들어올 때 모델을 먼저 동결하고, 그 새 묶음을 학습에 넣기 전에 한 번만 평가하는 "시간 순 사전 등록 시험"이 생기면, 사람 시간을 추가로 쓰지 않고도 앞으로 들어올 라벨이 독립 시험이 된다. 기존 그룹 분리는 같은 시점 자료 안의 분리라서 이 빈자리를 채우지 못한다.
- 각색 방법: "새 라벨 묶음은 도착 즉시 학습 편입 금지. 현재 채택 모델 SHA로 1회 평가해 기록한 뒤에만 개발 자료로 옮긴다"를 라벨 수집 규칙에 넣는다. 그 1회 결과를 독립 시험 분모로 HTML에 따로 표시한다.
- 확신도: 중간. 반대 근거: 묶음이 작으면(수십 장) 신뢰구간이 넓어 판정력이 약하다. eBay 사진은 시간에 따른 분포 변화가 크지 않을 수 있어 "시간"보다는 "미사용" 자체가 핵심이다.

## C. 묶음 메모
- 출처 표기가 ECC와 다른 파일: ios-icon-gen(origin: community), inventory-demand-planning(license Apache-2.0, author evos), llm-trading-agent-security("ECC direct-port adaptation"), ito-compute·liquid-glass-design(origin 표기 없음), leanrea(origin이 metadata 밖 최상위).
- ito-compute에는 외부 저장소 clone·`npm ci` 설치 지시, jira·lead-intelligence·laravel-plugin-discovery에는 MCP 설정 추가 지시가 있다. 자료로만 읽었고 따르지 않았다. 에이전트를 직접 겨냥한 주입 문구는 발견하지 못했다(llm-trading의 주입 패턴 목록은 예시 데이터다).
- 31개 중 Kotlin·Laravel·JVM·iOS·K8s 계열 14개는 Python 카드 모델과 무관하다.
