# batch-1 결과 (40개, 전부 Read로 끝까지 읽음 — 총 8,545줄, 모두 2000줄 미만이라 1회 Read로 전체 확인)

## A. 전체 판정표

| 스킬 | 한 줄 요지 | 판정 | 끝까지 읽음 |
|---|---|---|---|
| accessibility | WCAG 2.2 AA 웹·iOS·Android 접근성 구현·감사 | 무관 | 예 |
| agent-architecture-audit | LLM 앱 12계층(프롬프트·메모리·도구·숨은 재시도) 결함 감사 | 참고만 | 예 |
| agent-eval | 코딩 에이전트끼리 같은 과제로 통과율·비용·반복 일관성 비교 | 참고만 | 예 |
| agent-harness-construction | 에이전트 도구·관찰 형식·오류 복구 계약 설계 | 무관 | 예 |
| agent-introspection-debugging | 에이전트 실패 포착→원인 분류→최소 복구→보고 | 참고만 | 예 |
| agent-payment-x402 | 에이전트 결제(x402) 예산·지갑 정책 | 무관 | 예 |
| agent-runtime-gateway-smoke-test | 로컬 API·터널·원격 샌드박스 연결 스모크 테스트 | 무관 | 예 |
| agent-security-hardening | 에이전트 런타임 경계 검증·경로 격리·비밀 보호 | 무관 | 예 |
| agent-self-evaluation | 작업 후 5축 자기 채점(근거 필수) | 참고만 | 예 |
| agent-sort | ECC 구성요소를 저장소 근거로 DAILY/LIBRARY 분류 | 무관 | 예 |
| agentic-engineering | 평가 먼저·작업 분해·모델 등급 배정·도구 결과 해석 순서 | 참고만 | 예 |
| agentic-os | Claude Code를 다중 에이전트 OS로 쓰는 디렉터리·cron 구조 | 무관 | 예 |
| ai-first-engineering | AI 생성 코드 중심 팀의 리뷰·테스트 기준 | 무관 | 예 |
| ai-regression-testing | 발견된 버그 자리에 회귀 테스트, 같은 모델 자기검토 맹점 | 참고만 | 예 |
| android-clean-architecture | Android/KMP 계층 구조 | 무관 | 예 |
| angular-developer | Angular 코드 작성 지침 | 무관 | 예 |
| api-connector-builder | 기존 저장소 연동 패턴을 그대로 따라 새 커넥터 작성 | 무관 | 예 |
| api-design | REST API 설계 규칙 | 무관 | 예 |
| architecture-decision-records | 결정을 ADR(맥락·대안·결과)로 기록 | 참고만 | 예 |
| article-writing | 장문 글쓰기 문체·금지 표현 | 무관 | 예 |
| automation-audit-ops | 자동화 목록을 증거로 live/broken 분류 | 무관 | 예 |
| autonomous-agent-harness | 상시 자율 에이전트(cron·메모리·컴퓨터 사용) 구성 | 무관 | 예 |
| autonomous-loops | claude -p 파이프라인·PR 루프·DAG 오케스트레이션 | 무관 | 예 |
| backend-patterns | Node/Next.js 백엔드 패턴 | 무관 | 예 |
| benchmark-methodology | 경쟁사 9차원 1~5점 근거 고정 채점·교차 보정 | 후보 | 예 |
| benchmark-optimization-loop | 목표→기준선→변수 하나 변형→채택 게이트의 측정 루프 | 후보 | 예 |
| benchmark | 웹 성능(Core Web Vitals·API 지연) 기준선 비교 | 무관 | 예 |
| bengali-nlp | 벵골어 텍스트 처리 | 무관 | 예 |
| blender-motion-state-inspection | 스크린샷만 보지 말고 구조화 사실 추출 후 이미지로 확인 | 참고만 | 예 |
| blueprint | 다세션 작업을 PR 단위 계획으로 분해 | 무관 | 예 |
| brand-discovery | 다세션 브랜드 인터뷰(한 번에 한 질문·구체 예시 요구) | 후보 | 예 |
| brand-voice | 실제 글에서 문체 프로필 추출 | 무관 | 예 |
| brownfield-retrospective | 기존 코드 조각 감사→증거 붙은 결함 등록부→순차 수정 | 참고만 | 예 |
| browser-qa | 배포 후 브라우저 UI 검증 | 무관 | 예 |
| bun-runtime | Bun 런타임 사용법 | 무관 | 예 |
| canary-watch | 배포 URL 상시 감시 | 무관 | 예 |
| carrier-relationship-management | 화물 운송사 계약·평가 | 무관 | 예 |
| change-impact | 변경 전 영향 범위 증명, 변경 후 실제 diff와 대조 | 참고만 | 예 |
| cisco-ios-patterns | Cisco 장비 설정 검토 | 무관 | 예 |
| ck | 프로젝트별 세션 맥락 저장 명령 + SessionStart 훅 | 무관 | 예 |

## B. 후보 상세

### 1. benchmark-optimization-loop
- origin: ECC, license: MIT
- 관점: 1, 3, 4
- 근거 구간:
  - 115-117줄: 이미 본 평가 자료를 개발 자료로 다시 분류하는 규칙. 인용: "once acceptance feedback informs further tuning, treat those cases as development evidence"
  - 112, 118-120줄: 직전 실행이 아니라 마지막으로 채택된 모델과 비교하고, 개선 폭이 잡음 범위 안이면 멈춘다.
  - 53-55줄: 주관 판정은 승인된 예시로 루브릭을 맞추고 판정자 간 불일치를 기록하며, 최적화하는 쪽의 자기 채점만으로는 채택 근거가 되지 않는다.
  - 45-47줄: 성공 기준이 비어 있으면 열린 질문 대신 구체안을 내고 사용자 결정을 받는다.
- 빈자리: 사전 등록 실행기는 이미 "실험 1건"의 기준을 고정한다. 하지만 **연속 실험 전체에 걸친 재사용 규칙**은 명문화되지 않았다. 남는 빈자리는 세 가지다. 첫째, 연속 미채택 3건을 낸 같은 개발 자료를 몇 번 다시 썼는지 세는 장부. 둘째, 그 횟수가 넘으면 해당 자료로 내린 채택 판단을 "개발 증거"로만 낮추는 규칙. 셋째, 비교 대상을 "직전 실행"이 아닌 "마지막 채택본"으로 고정하는 규칙. 이것이 독립 시험 자료 부재와 우연 통과 경계라는 정체 항목을 직접 겨냥한다. 53-55줄은 AI 판정자를 보조 라벨로 쓰기 전에 사람이 확정한 기준 예시로 먼저 맞추라는 요구로 바꿔 쓸 수 있다. 진행 중인 "판정 일관성 확인"은 AI끼리의 재현성만 보므로 이와 겹치지 않는다.
- 각색: 실험 계획 양식에 두 칸을 추가한다. `dev_set_reuse_count`는 같은 평가 ID 묶음을 앞서 몇 번 썼는지, `compare_to`는 마지막 채택본의 record.json이다. 점검표에는 "재사용 N회 이상이면 독립 일반화 주장 금지"와 "AI 판정자는 사람 확정 기준 크롭 묶음과의 일치율을 먼저 보고"를 넣는다.
- 확신도: 중간. 반대 근거: 실행기·우연 판별 도구·mle-workflow 신뢰구간과 상당 부분 겹친다. 실제로 새로운 것은 "누적 재사용 횟수"와 "채택본 기준 비교" 두 조각뿐이다.

### 2. benchmark-methodology
- origin: 표기 없음 (license: MIT만 있음)
- 관점: 2, 3
- 근거 구간:
  - 134-136줄: 모든 대상의 점수를 나란히 다시 읽고 같은 점수가 같은 뜻인지 맞춘다. 인용: "a \"4\" must mean the same thing for every competitor."
  - 69-83줄: 단계마다 관찰 가능한 증거로 고정한 1~5 앵커를 쓰고, 점수마다 근거 한 줄과 출처를 남긴다.
  - 124-125줄: 근거가 확인된 것("proven")과 주장만 있는 것("asserted")을 구분한다.
- 빈자리: 사람 재판정 kappa가 0.47~0.62다. 감정사 실무에서는 등급별 **기준 카드(reference set)** 와 "나란히 다시 보기" 보정으로 이 문제를 줄인다. 이미 갖춘 라벨 프로토콜과 코너 결함 단계 문구는 **글 기준**이다. 단계마다 사람이 확정한 대표 크롭 2~3장의 앵커 묶음과, 라벨 묶음을 마치기 전 같은 단계끼리 나란히 보는 보정 절차는 목록에 없다.
- 각색: 코너 결함 단계(정상/경미 화이트닝/결함/관찰 제한)마다 사용자가 이미 확정한 라벨 중 대표 크롭을 골라 고정 앵커 페이지를 만든다. 재요청이 아니라 기존 라벨을 골라 쓰는 것이다. 새 라벨 페이지와 AI 판정 프롬프트 모두 이 앵커를 함께 보여 준다. 라벨 묶음이 끝나면 같은 단계로 붙인 크롭을 한 화면에 나란히 띄워 "튀는 것"만 표시하게 하되, 모델 출력은 보여 주지 않는다.
- 확신도: 중간. 반대 근거: 원문은 경쟁사 마케팅 채점용이라 이미지 라벨 근거가 아니다. 나란히 보기가 이전 라벨에 끌려가는 앵커링을 만들 수 있으므로, 미리 채우기 격리 원칙과 충돌하지 않게 설계해야 한다.

### 3. brand-discovery
- origin: 표기 없음 (frontmatter에 metadata·license 없음. ECC 출처 확인 불가)
- 관점: 4
- 근거 구간:
  - 45-47줄: 한 번에 한 질문만 하고, 답마다 짧게 되짚은 뒤 한 번만 더 파고들거나 그 주제를 닫는다.
  - 53-54줄: 답이 막연하면 구체 예시를 요구한다. 인용: "if generic, jargon-heavy, or vague, ask for one concrete example"
  - 61-62줄: 두 번 더 물어도 새 정보가 없으면 요약하고 닫는다.
- 빈자리: (비공개) 요청이 짧을 때 에이전트가 의도를 한 줄로 되짚고, 결정적인 빈칸 하나만 묻거나 구체 예시 하나만 요구하는 절차는 현재 갖춘 목록에 없다. Superpowers brainstorming은 설계 탐색용이라 범위가 다르다. 이 방식은 훅 없이 대화 규칙만으로 쓸 수 있다.
- 각색: 요청 접수 규칙 세 줄로 옮긴다. ① 짧거나 모호한 요청은 "이렇게 이해했다" 한 줄로 되짚는다. ② 결과를 바꿀 빈칸이 있으면 질문 하나와 기본안을 함께 낸다. ③ 화면·파일 실패 보고는 "어느 화면/파일, 무엇을 기대했나" 중 빠진 것 하나만 묻는다. (비공개 작업 선호)를 우선한다.
- 확신도: 낮음~중간. 반대 근거: (비공개). 질문을 늘리면 (비공개 작업 선호)와 부딪힐 수 있다.

## C. 묶음 메모
- ECC 표기가 아닌 출처가 섞여 있다. agent-architecture-audit(oh-my-agent-check), agent-payment-x402·blueprint·cisco-ios-patterns·ck(community), api-connector-builder(ECC direct-port adaptation), carrier(Apache-2.0)가 그렇다. brand-discovery·change-impact·benchmark-methodology는 origin 표기가 없고, agent-self-evaluation은 origin이 metadata 밖에 있다.
- ck("You are the Context Keeper assistant… 스크립트 실행")와 carrier("You are a senior transportation manager")는 읽는 에이전트에게 역할을 지정하는 문구다. agent-payment-x402·autonomous-agent-harness에는 설치·npx·curl 지시가 있다. 모두 자료로만 취급했고 따르지 않았다. 숨은 주입 문구는 발견하지 못했다.
- agent-payment-x402에는 특정 상업 업체 관계자가 일부를 썼다는 공개 문구(270줄)가 있다. 내용 판단에는 영향이 없다.
