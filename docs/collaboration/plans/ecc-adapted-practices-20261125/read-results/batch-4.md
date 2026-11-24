# batch-4 결과 (33개)

## A. 전체 판정표

| 스킬 | 한 줄 요지 | 판정(후보/참고만/무관) | 끝까지 읽음(예/아니오) |
|---|---|---|---|
| foundation-models-on-device | Apple iOS 26 기기 내 LLM(FoundationModels) Swift 사용법 | 무관 | 예 |
| frontend-a11y | React 폼·ARIA·키보드·포커스 접근성 패턴 | 무관 | 예 |
| frontend-design-direction | UI 디자인 방향·콘텐츠 상태(로딩/빈/오류/부분)·렌더 확인 게이트 | 참고만 (HTML 보고서에 "부분 자료는 빠진 부분을 표시", "테스트 못 함은 해당 없음이 아니다" 정도) | 예 |
| frontend-patterns | React 컴포넌트·상태·성능 패턴 | 무관 | 예 |
| frontend-slides | 단일 HTML 발표 자료 제작 절차 | 무관 | 예 |
| fsharp-testing | F# xUnit/FsCheck 테스트 패턴 | 무관 | 예 |
| gan-style-harness | 생성자·평가자 분리 다중 에이전트 반복 루프와 점수 기준표 | 참고만 (평가자가 자기 수정안을 평가하지 않기, 3회 정체 시 사람 확인 — 이미 판정자 분리·정체 판정 보유) | 예 |
| gateguard | 첫 편집을 막고 구체 사실(호출처·자료 구조·사용자 지시 원문)을 요구하는 훅 | 후보 (훅 말고 "자기평가 대신 사실 요구" 아이디어만) | 예 |
| generating-python-installer | Windows용 Nuitka+Inno Setup 설치본 최적화 | 무관 | 예 |
| git-workflow | 브랜치 전략·커밋 규칙·병합/리베이스 | 무관 | 예 |
| github-ops | gh CLI로 이슈·PR·CI·릴리스 운영 | 무관 | 예 |
| godot-patterns | Godot 4 GDScript 관용 패턴 | 무관 | 예 |
| godot-testing | Godot 헤드리스 테스트·CI | 무관 | 예 |
| golang-patterns | Go 관용 패턴 | 무관 | 예 |
| golang-testing | Go 표 기반 테스트·golden file·fuzz | 무관 | 예 |
| google-workspace-ops | Google Drive/Docs/Sheets 작업 흐름 | 무관 | 예 |
| growth-log | 학습 기록을 근본 원인·이전 가능한 규칙·인식 신호로 쓰고 중복 병합 | 참고만 (미채택 변형 기록에 "다음에 볼 신호" 칸 정도. 이미 실패 가설 거절·에튜·메모리 보유) | 예 |
| healthcare-cdss-patterns | 임상 결정 지원: 약물 상호작용·용량 검증, 필수 입력 없으면 통과 대신 차단 | 참고만 ("입력 부족이면 정상으로 통과시키지 않는다"는 관찰 제한 원칙과 이미 같음) | 예 |
| healthcare-emr-patterns | EMR 진료 흐름, 서명 후 잠금+추가기록(addendum) | 참고만 (확정 라벨 수정 대신 연결된 추가기록 — 라벨 프로토콜·주체 기록과 대부분 겹침) | 예 |
| healthcare-eval-harness | 등급별 배포 게이트(핵심 100%, 그 외 95%), 테스트 0건이면 실패 | 참고만 (분모 0이면 실패 처리 — required_cohorts와 겹침) | 예 |
| healthcare-phi-compliance | 환자정보 분류·행 단위 접근제어·감사 로그 | 무관 | 예 |
| hermes-imports | 개인 작업 흐름을 공개 스킬로 정리할 때 비밀·경로 제거 | 무관 | 예 |
| hexagonal-architecture | 포트·어댑터 구조 설계 | 무관 | 예 |
| hipaa-compliance | HIPAA 전용 진입점 | 무관 | 예 |
| homelab-network-readiness | 홈 네트워크 VLAN·DNS·VPN 변경 전 점검표 | 무관 | 예 |
| homelab-network-setup | 홈 네트워크 IP·DHCP·DNS 설계 | 무관 | 예 |
| homelab-pihole-dns | Pi-hole 설치·운영 | 무관 | 예 |
| homelab-vlan-segmentation | VLAN 분리·방화벽 규칙 | 무관 | 예 |
| homelab-wireguard-vpn | WireGuard VPN 구성 | 무관 | 예 |
| hookify-rules | 정규식 기반 경고/차단 훅 규칙 파일 작성 | 무관 | 예 |
| i18n-sync | JSON 번역 파일을 사용 위치 맥락으로 동기화 | 무관 | 예 |
| inherit-legacy-style | 기존 코드 관례 추출, 강한 충돌만 증거+선택지로 하나씩 질문 | 후보 (질문 양식·신호 문턱 아이디어만) | 예 |
| intent-driven-development | 모호한 요청을 범위·가정·관찰 가능한 수용 기준(AC)과 검증 방법으로 정리 | 후보 | 예 |

## B. 후보 상세

### 1. intent-driven-development
- origin·license: 표기 없음 (frontmatter에 metadata 없음)
- 관점: 4 (주), 2
- 근거 구간: 121-131줄(운영 규칙), 162-170줄(Quick Capture), 248-249줄(모호한 단어 금지), 103-116줄(수집됨 vs 승인됨 구분). 인용: "Ask only questions whose answers are required and cannot be safely inferred."
- 채우는 빈자리: 짧은 요청을 받으면 바로 구현하기 전에 "목표 1문장 / 범위 안·밖 / 가정 / 3~7개 수용 기준(시작 조건·동작·기대 결과·하면 안 되는 일·검증 방법)"을 짧게 적는 양식. Superpowers brainstorming/writing-plans는 긴 설계·계획 절차이고, 이건 요청마다 쓰는 짧은 양식이라 겹치지 않는다. 또 "업무 규칙은 코드에서 추정하지 않고 사용자에게서만 받는다"는 규칙은 이 프로젝트에서는 "결함 기준(얼마나 작은 화이트닝까지 결함인가)은 모델·코드에서 추정하지 않고 사람 라벨·사용자 결정으로만" 정할 때 바로 쓸 수 있다. "자료 수집됨 ≠ 승인됨" 표는 라벨 수집 상태 보고(입력 받음/검증됨/미확인)에 맞는다.
- 각색 방법: AGENT_START 작업 시작 양식에 "요청 해석 5칸(목표·범위 밖·가정·AC·검증)"을 넣고, AC에 "정확하게/개선" 같은 말은 분모·%p가 없으면 못 쓰게 한다. 차단 질문은 사람만 판단할 것(라벨 기준·승인 범위)으로 제한한다.
- 확신도: 높음. 반대 근거: (비공개). 양식만으로 요청 수정이 줄어든다는 보장은 없다(효과는 실제로 재봐야 한다).

### 2. gateguard (훅 설치가 아니라 아이디어 한 조각만)
- origin·license: origin community, license 표기 없음
- 관점: 1 (AI 판정자 일관성), 4
- 근거 구간: 19-23줄(핵심 개념), 711줄(안티패턴). 인용: "LLM self-evaluation doesn't work."
- 채우는 빈자리: AI 판정자 일관성 확인이 진행 중인데, LLM에게 "확실한가?" 식으로 다시 묻는 자기평가는 거의 항상 "예"가 나온다는 주장. 그 대신 판정 전에 구체 사실을 먼저 적게 강제하라는 것이다. 코너 판정에 옮기면 결함/정상 결론 전에 (a) 크롭 안의 위치(모서리 끝/가장자리), (b) 보이는 특징(흰 점·박리·광택 반사), (c) 사진 조건(홀더·해상도·배경)을 칸으로 먼저 채우게 하고, 그 칸들이 결론과 맞지 않으면 보류로 돌린다. 지금의 "2회 독립+병합"은 반복 일치를 보는 것이고, 이건 한 번의 판정 안에서 근거를 강제하는 것이라 겹치지 않는다. 덤으로 에이전트가 작업 전에 "사용자 지시 원문 인용"을 하게 하면 방향 수정을 일찍 잡을 수 있다.
- 각색 방법: 코너 판정 프롬프트의 JSON에 결론보다 앞에 오는 관찰 칸 3개를 추가하고, 병합 단계에서 관찰 칸끼리 서로 다르면 결론이 같아도 "불일치"로 센다. 에이전트 쪽은 작업 시작 기록에 지시 원문 한 줄을 넣는다.
- 확신도: 중간. 반대 근거: 효과 근거가 작성자 자체 A/B 2건(+2.25점)뿐이고 코드 편집 품질이지 이미지 판정 결과가 아니다. 관찰 칸이 사후 합리화로 채워질 수도 있다.

### 3. inherit-legacy-style (질문 양식·신호 문턱 아이디어만)
- origin·license: origin community, license 표기 없음
- 관점: 4, 2
- 근거 구간: 64-79줄(신호 문턱과 한 번에 하나씩 질문하는 절차). 인용: "Never stack questions."
- 채우는 빈자리: 사람만 판단할 라벨 정답·모호한 증거를 물을 때 쓰는 양식. 질문 하나마다 "증거 A(경로·크롭) vs 증거 B / 섞을 때 위험 / 선택지 1·2·3(새 규칙)"을 고정해서 한 번에 하나만 묻는다. 약한 신호(소수가 5% 미만이고 10건 미만)는 묻지 않고 다수로 처리하되 기록은 남긴다. (비공개 작업 선호)와 방향은 같지만, 질문 양식과 수치 문턱은 따로 없다. 재판정 kappa 0.47~0.62의 라벨 불일치 구역을 사용자에게 보여줄 때도 같은 양식을 쓸 수 있다.
- 각색 방법: 사람 확인 요청 양식을 "증거 2개 + 위험 1줄 + 고정 선택지 3~4개, 질문 1개"로 정하고, 묻지 않고 처리할 문턱(예: 비율·건수)을 계획에 미리 적는다. 문턱 수치는 사용자 승인 대상이다.
- 확신도: 낮음~중간. 반대 근거: 원래 스킬은 코드 스타일 충돌용이고, 라벨 문제에서 "다수결로 자동 처리"는 사람 라벨을 모델·다수로 바꾸는 쪽으로 오용될 위험이 있다(라벨 정답에는 문턱 처리를 쓰면 안 되고, 질문 양식만 써야 한다).

## C. 묶음 메모
- origin 표기 없음: foundation-models-on-device, generating-python-installer(중국어 본문), hookify-rules, intent-driven-development. healthcare 3종은 병원 소속 개인 기여, gan-style-harness는 ECC-community, hipaa는 "ECC direct-port adaptation".
- 프롬프트 주입으로 의심되는 문구는 없었다. 다만 gateguard, hookify-rules, inherit-legacy-style(allowed-tools·CLAUDE.md/settings.json 훅 설치 안내), gan-style-harness(`claude -p` 실행 예시)에는 설치·설정 변경 지시가 있다. 브리프에 따라 따르지 않았다.
- 이 묶음 대부분(홈랩·Go·Godot·프론트엔드·의료 규정 등)은 카드 모델과 관계가 없다. 의료 계열의 "입력 부족이면 차단"과 "확정 기록 잠금+추가기록"은 기존 관찰 제한·라벨 프로토콜과 같은 원칙이라 새 후보로 올리지 않았다.
