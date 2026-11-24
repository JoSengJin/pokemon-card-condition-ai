# batch-9 결과 (31개)

## A. 전체 판정표

| 스킬 | 한 줄 요지 | 판정 | 끝까지 읽음 |
|---|---|---|---|
| taste-distillation | 참고 영상의 색감·컷 리듬을 수치로 측정해 스타일 팩으로 만듦 | 후보 (2조각) | 예 |
| taste | 엔젤코어 뮤직비디오 미감·편집 문법 | 무관 | 예 |
| tasteforge-video | 오프라인 스타일 팩 검증·타임라인 내보내기, 공급자 생성 차단 | 참고만 (측정/생성 출처 구분은 이미 답 판정 주체 기록과 겹침) | 예 |
| tdd-workflow | 실패 테스트 먼저(RED→GREEN)·80% 커버리지·증거 보고 | 참고만 (Superpowers TDD와 중복) | 예 |
| team-agent-orchestration | 에이전트 칸반·소유·병합 관문 | 참고만 (페어코딩 계약과 중복) | 예 |
| team-builder | 에이전트 페르소나 골라 병렬 실행 | 무관 | 예 |
| terminal-opener | 셸 없이 터미널 창 열기 | 무관 | 예 |
| terminal-ops | 증거 우선 실행, 상태 단어(inspected/verified/pushed 등) | 참고만 (보고 규칙과 중복) | 예 |
| terraform-patterns | Terraform 구조·상태·plan/apply | 무관 | 예 |
| test-collaboration | 요구·버그를 TEST-ID와 실제 실패 형태 재현 테스트로 연결 | 참고만 (required_cohorts와 대부분 겹침) | 예 |
| tinystruct-patterns | Java tinystruct 프레임워크 | 무관 | 예 |
| token-budget-advisor | 답 깊이 25~100% 선택지 제시 | 참고만 (관점 4에 약함, "짧게 보고" 규칙과 겹침) | 예 |
| token-card | 토큰 사용량 SVG 카드 | 무관 | 예 |
| typescript-patterns | TS 엄격 타입 패턴 | 무관 | 예 |
| ui-canvas | 사람이 직접 고치는 HTML 목업 캔버스 | 무관 | 예 |
| ui-demo | Playwright 데모 영상 녹화(탐색→리허설→녹화) | 무관 | 예 |
| ui-to-vue | 디자인 캡처를 Vue 컴포넌트로 | 무관 | 예 |
| uncloud | Uncloud 클러스터 운영 | 무관 | 예 |
| unified-memory | 하네스 간 메모리 금고·인계 | 참고만 ("기억은 증거일 뿐" 원칙, claude-mem과 중복) | 예 |
| unified-notifications-ops | 알림 경로·중요도 정리 | 무관 | 예 |
| verification-loop | 빌드·타입·린트·테스트·보안·diff 6단계 검증 | 참고만 (verification-before-completion과 중복) | 예 |
| video-editing | FFmpeg·Remotion 편집 파이프라인 | 무관 | 예 |
| videodb | VideoDB SDK 색인·검색·편집 | 무관 | 예 |
| visa-doc-translate | 비자 서류 사진 OCR·번역 PDF | 후보 (EXIF 방향 조각만) | 예 |
| vite-patterns | Vite 설정 | 무관 | 예 |
| vue-patterns | Vue 3 패턴 | 무관 | 예 |
| web-perimeter-owasp-2025-audit | 웹 경계 보안 수동 점검 | 무관 | 예 |
| windows-desktop-e2e | pywinauto 데스크톱 E2E | 무관 | 예 |
| workspace-surface-audit | 작업공간 도구·연결 점검 | 무관 | 예 |
| x-api | X API 게시·검색 | 무관 | 예 |
| yoruba-localization-testing | 요루바어 현지화 테스트 | 무관 | 예 |

## B. 후보 상세

### 1. taste-distillation (A) — AI 판정자에게 모델 출력·수치를 주입하지 않기
- origin: ECC / license: 표기 없음
- 관점: 1, 3
- 근거 구간: 145-158줄. 인용: "once the spec is grounded in the measurements it is no longer an independent check"
- 메우는 빈자리: AI 판정자(LLM이 크롭 판정)를 보조 라벨로 쓰는 중인데, 판정 요청에 모델 점수·예측·이전 판정을 넣으면 AI 판정이 모델과의 독립 검증 역할을 잃는다. 이미 있는 "미리 채우기 앵커링 격리"는 사람 라벨용이고, "2회 독립+병합"은 판정자끼리의 독립이다. 판정자 입력과 모델 출력 사이의 독립 규칙은 따로 명시되어 있지 않다.
- 각색: 판정 요청 양식에 "모델 점수·예측 라벨·사람 라벨을 넣지 않음" 확인 칸을 추가한다. 모델 오류 분석에 쓰는 판정은 입력 주입 여부를 기록에 남겨 독립/비독립을 분리 집계한다. 같은 구간의 "모호어 금지는 코드로 강제"(152-155줄) 조각도 판정 JSON의 허용 값 검사에 응용할 수 있다.
- 확신도: 중간. 반대 근거: 현행 판정 키트가 이미 모델 출력을 주지 않고 있다면 확인 칸 하나 늘리는 효과밖에 없다(키트 내용은 확인하지 않았다).

### 2. taste-distillation (B) — 배경·가림 요소의 점유율을 사진 조건 지표로
- origin: ECC / license: 표기 없음
- 관점: 1, 3
- 근거 구간: 96-110줄. 인용: "Background share is a first-class statistic"
- 메우는 빈자리: 남은 오류 중 사진 조건 5건(카드 홀더·저해상도 크롭·흰 배경)이 있는데, 기존 자동 지표 4개(해상도·크롭 px·라플라시안 흐림·포화)는 모두 사진 전체의 통계라 오류를 못 가려냈다. 이 스킬은 전체 통계가 놓치는 것을 "배경이 차지하는 비율"과 "움직이지 않는 장식 요소를 먼저 가리기"로 잡아낸 사례를 든다. 카드 사진으로 옮기면 모서리 주변 띠 안에 흰 배경이 차지하는 비율, 홀더 테두리가 있는지와 같은 구역 단위 국소 지표가 된다. 오류 원인 분해 보고서는 일회성이라 이런 지표가 정해진 진단 변수로 남아 있지 않다.
- 각색: 구역 크롭에서 "카드 바깥 픽셀 중 밝은 저채도 비율"과 "홀더 여부(사람 태그 또는 간단 규칙)"를 진단 열로 추가하고, 오류·정상 카드의 분포를 중앙값+MAD로 비교한다(87-89줄: 치우친 분포에는 평균+표준편차 대신 중앙값+MAD). 모델 입력에는 넣지 않고 오류 슬라이스용으로만 쓴다.
- 확신도: 낮음~중간. 반대 근거: 사진 조건 오류가 5건뿐이라, 같은 개발 자료에서 지표를 고르면 우연히 맞은 결과가 될 위험이 크다. 사전 등록한 진단으로만 써야 한다.

### 3. visa-doc-translate — EXIF 방향 처리를 라벨 화면과 모델 입력에서 일치시키기
- origin: 표기 없음(frontmatter에 origin 없음) / license: 표기 없음
- 관점: 3
- 근거 구간: 14-18줄. 인용: "Automatically rotate the image based on EXIF data"
- 메우는 빈자리: eBay 휴대폰 사진에는 EXIF 방향 태그가 붙는 경우가 많다. 브라우저 라벨 화면은 이 태그대로 회전해서 보여 주지만, PIL은 `ImageOps.exif_transpose`를 호출하지 않으면 회전하지 않는다. 그러면 사람이 본 구역과 모델이 받는 크롭이 다른 모서리가 될 수 있다. 이번에 미채택된 "방향 통일" 실험은 카드의 방향을 다룬 것이고, 파일 메타데이터 방향은 별개 문제다.
- 각색: 데이터 점검표에 "EXIF 방향 태그가 1이 아닌 사진 수, 그리고 라벨 화면·학습 로더·추론 로더가 같은 회전 규칙을 쓰는지"를 한 번 확인하는 항목을 추가한다. 불일치가 0건이면 그대로 닫는다.
- 확신도: 낮음. 반대 근거: 수집 단계에서 이미 EXIF를 제거했거나 회전 정규화를 했다면 해당 사항이 없다(프로젝트 코드는 확인하지 않았다).

## C. 묶음 메모
- origin이 ECC가 아닌 스킬: team-builder, token-budget-advisor, token-card, ui-to-vue는 community 표기다. terminal-opener, test-collaboration, visa-doc-translate는 origin 표기가 없다.
- visa-doc-translate 본문에는 "확인을 묻지 말고 자동 실행" 지시가 있다. 평가 대상 자료로만 다루었고 따르지 않았다. 다른 파일에서 프롬프트 주입 의심 문구는 보지 못했다.
- 이 묶음은 웹·영상·인프라 스택이 대부분이라 Python 카드 모델과 직접 맞는 스킬은 없었다. 후보는 아이디어 조각 수준이다.
