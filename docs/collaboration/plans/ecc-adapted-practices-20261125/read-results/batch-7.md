# batch-7 결과 (28개)

## A. 전체 판정표

| 스킬 | 한 줄 요지 | 판정 | 끝까지 읽음 |
|---|---|---|---|
| plan-orchestrate | 계획 문서 단계를 ECC 슬래시 명령으로 바꿔 주는 라우터(범위 못 싣는 명령은 차단) | 참고만 (완료 기준 1~3개·없는 범위 제한은 지어내지 않기, writing-plans와 겹침) | 예 |
| plankton-code-quality | 편집할 때마다 린터·포맷터 훅과 하위 Claude 자동 수정, 린터 설정 변조 방지, 복잡도 상한 래칫 | 참고만 (평가 설정 변조 방지는 사전 등록·snapshot과 겹침, 훅은 원치 않음) | 예 |
| platform-factory | pf CLI로 결정적 OCI 이미지·SBOM 빌드, freeze 훅 | 무관 | 예 |
| postgres-patterns | PostgreSQL 인덱스·RLS·쿼리 패턴 | 무관 | 예 |
| prediction-market-oracle-research | 예측시장 가격을 신호로 쓸 때 품질 평가(유동성·해석 규칙) | 참고만 (신호를 정답처럼 다루지 말라는 원칙은 AI 판정자 분리와 겹침) | 예 |
| prediction-market-risk-review | 예측시장·트레이딩 워크플로 위험 검토 관문 | 무관 | 예 |
| prisma-patterns | Prisma ORM 스키마·트랜잭션·마이그레이션 함정 | 무관 | 예 |
| product-capability | PRD를 제약·불변식·미해결 질문이 드러나는 구현 계약으로 바꿈 | 참고만 (brainstorming/writing-plans와 겹침) | 예 |
| product-lens | YC식 제품 진단, ICE 우선순위 | 무관 | 예 |
| production-audit | 로컬 근거만으로 출시 준비도 점수와 막는 항목 정리 | 참고만 ("확인한 근거/빠진 근거" 칸은 기존 보고 규칙과 겹침) | 예 |
| production-scheduling | 제조 일정·병목(TOC)·교체시간 최적화 | 무관 | 예 |
| project-flow-ops | GitHub·Linear 이슈와 PR 분류 | 무관 | 예 |
| prompt-caching-strategy | LLM 프롬프트 캐시 적중률과 비용 계산 | 참고만 (AI 판정자 호출 비용에 쓸 수 있지만 정확도와 무관) | 예 |
| prompt-optimizer | 짧은 요청을 진단하고 빠진 맥락을 점검한 뒤 다듬은 요청문 작성 | 후보 | 예 |
| python-patterns | Python 관용구·타입힌트·예외 처리 | 참고만 (일반 코딩 기준) | 예 |
| python-testing | pytest TDD·픽스처·모킹·커버리지 | 참고만 (TDD는 이미 선택 사항으로 정해 둠) | 예 |
| pytorch-patterns | PyTorch 학습 루프·시드·재현성 | 참고만 (시드 고정은 반복 편차 채택과 겹침, 고정 backbone+작은 head 구조라 쓸 곳 적음) | 예 |
| quality-nonconformance | 규제 제조 품질관리: 부적합 처리, 근본원인 분석, CAPA, SPC, AQL 샘플링, 측정시스템 | 후보 (조각 2개) | 예 |
| quarkus-patterns | Quarkus·Camel 백엔드 패턴 | 무관 | 예 |
| quarkus-security | Quarkus 인증·보안 | 무관 | 예 |
| quarkus-tdd | Quarkus JUnit TDD | 무관 | 예 |
| quarkus-verification | Quarkus 빌드·검사·배포 확인 절차 | 무관 | 예 |
| rails-patterns | Rails 서비스 객체·잡·Hotwire | 무관 | 예 |
| rails-security | Rails 보안 | 무관 | 예 |
| ralphinho-rfc-pipeline | RFC를 다중 에이전트 작업 DAG로 나눠 병합 대기열로 통합 | 무관 (자동 오케스트레이션, 페어코딩 계약과 겹침) | 예 |
| react-native-patterns | Expo/React Native 패턴 | 무관 | 예 |
| react-patterns | React 18/19 패턴 | 무관 | 예 |
| react-performance | React/Next.js 성능 규칙 | 무관 | 예 |

## B. 후보 상세

### 1. quality-nonconformance — 조각 A: 채택 표본계획(AQL/LTPD 두 위험)
- origin: ECC, license: Apache-2.0 (frontmatter, author evos)
- 관점: 1(독립 시험 부재·우연 통과), 2(감정 실무의 표본 검사), 3(작은 자료 평가 통계)
- 근거 구간: 93~95줄(AQL·LTPD), 보조로 77~78줄·143~150줄(CAPA는 "구현했다"와 "실제로 재발이 없었다"를 따로 확인). 인용: "AQL protects the producer (low risk of rejecting good lots)"
- 채우는 빈자리: 지금 갖춘 신뢰구간·반복 편차는 결과가 나온 **뒤** 해석하는 도구다. 이 조각은 새 카드를 라벨하기 **전에** "몇 장(n)을 보고 오류가 몇 개(c) 이하면 채택"을 정하고, 좋은 모델을 버릴 위험과 나쁜 모델을 받을 위험을 둘 다 숫자로 적는다. 사람 라벨 시간이 막힌 상황에서 "새로 몇 장이 필요한가"에 답한다.
- 각색: 실험 계획 양식에 `acceptance_sampling` 칸(n, c, 받아들일 수 있는 오류율, 거절할 오류율, 두 위험 %)을 추가하고, 사람 라벨 예산으로 n을 정한다. 채택한 변경은 다음 새 카드 n장에서 "재발 없음"을 확인할 때까지 "검증 대기"로 두고, 실패하면 다시 연다(CAPA의 효과 확인 규칙).
- 확신도: 중간. 반대 근거: 사실상 이항 검정력 계산이라, 이미 채택한 신뢰구간 절차를 확장해 계획 단계에 쓰는 것과 차이가 작을 수 있다.

### 2. quality-nonconformance — 조각 B: 측정시스템 분석(Gauge R&R) 관점의 라벨 잡음 관문
- origin: ECC, license: Apache-2.0
- 관점: 1(같은 자료 반복 실험 정체, kappa 0.47~0.62), 2(2인 판정·기준 카드), 3(라벨 잡음)
- 근거 구간: 189~190줄(재현 안 되는 결함과 Gauge R&R), 보조로 64~65줄(Ishikawa에 Measurement 범주), 86줄(능력 지수). 인용: "can reveal intermittent measurement system contributions"
- 채우는 빈자리: kappa는 일치도 숫자 하나뿐이다. Gauge R&R식으로 보면 라벨 변동을 반복성(같은 판정자가 다시 판정)과 재현성(사람과 AI 판정자의 차이)으로 나눌 수 있다. 그 측정 잡음이 모델 변형으로 기대하는 차이(예: 오탐 9/81 → 7/81)보다 크면, 그 실험은 결과를 판별할 수 없다고 미리 판단할 수 있다. 현재 "얻어걸린 향상 금지"는 결과를 본 뒤 거르는 규칙이고, 이것은 실험을 시작하기 전에 거르는 관문이다.
- 각색: 고정 기준 카드 묶음(예: 20~30장, 결함·정상·관찰 제한 섞어서)을 정해 사람 재판정과 AI 판정 2회를 같은 양식으로 받고, "반복성 불일치 장수 / 재현성 불일치 장수"를 기록한다. 새 모델 실험 계획에는 "기대 개선 장수가 측정 불일치 장수보다 큰가"를 필수 칸으로 둔다.
- 확신도: 중간~낮음. 반대 근거: 사람 재판정 kappa와 AI 판정 일관성 확인이 이미 진행 중이라, 새 도구라기보다 해석하는 틀을 하나 더하는 데 그칠 수 있다.

### 3. prompt-optimizer — 빠진 맥락 점검표와 질문 상한
- origin: community (author YannJY02, version 1.0.0), license: 표기 없음
- 관점: 4
- 근거 구간: 136~155줄(Phase 4 빠진 맥락 11항목과 질문 규칙), 보조로 213~222줄(완성 요청문에 완료 기준·검증·하지 말 것 포함). 인용: "If 3+ critical items are missing, ask the user up to 3 clarification questions"
- 채우는 빈자리: (비공개). 이미 있는 brainstorming과 writing-plans는 큰 작업용이고, 짧은 요청 하나에 "빈칸 몇 개면 묻고, 나머지는 가정을 적고 진행"하는 가벼운 기준은 없다.
- 각색: 요청을 받으면 에이전트가 속으로 5칸(대상 범위, 완료 기준, 하지 말 것, 보고 형식, 설명 수준)을 채운다. 프로젝트 문서로 채울 수 없는 칸이 3개 이상일 때만 최대 2~3개를 묻고, 그 밖에는 가정을 한 줄로 밝히고 진행한다. 시작할 때 채운 5칸을 한 줄로 되돌려 보여 주어 방향이 어긋난 것을 일찍 잡는다(훅 없이 규칙 문서로).
- 확신도: 낮음~중간. 반대 근거: (비공개). 질문이 늘면 (비공개 작업 선호)와 부딪힐 수 있다.

## C. 묶음 메모
- quality-nonconformance와 production-scheduling은 frontmatter에 license: Apache-2.0(author evos)으로 적혀 있다(MIT 아님). prompt-optimizer, plankton, platform-factory, production-audit, prompt-caching, rails-*는 origin이 community다. react-performance는 Vercel MIT 원문을 각색한 것이다.
- 설치·실행 지시가 있다: platform-factory의 `/plugin marketplace add`, plankton의 brew 설치와 훅 복사. prompt-optimizer에는 에이전트 역할을 바꾸라는 문구("Advisory only — do not execute")가 있다. 셋 다 따르지 않았다. 악성 주입으로 보이는 문구는 없었다.
- 이 묶음은 대부분 웹·백엔드 스택 전용이라 무관하다. 제조 품질관리 스킬의 통계 품질 개념이 유일하게 실질적인 조각이었다.
