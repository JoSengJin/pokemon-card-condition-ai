# Claude 실행 프롬프트 — a3-data-intake-batch-20261025

이번 목표는 테스트를 늘리는 것이 아니라 A3 평가 자료를 채우기 위한 실제 신규 검토 패킷과 부족 자료 수집 명세를 한 번에 완성하는 것이다. main 수정/라벨 추정/AI 호출은 승인하지 않는다.

먼저 AGENTS.md, PAIR_CODING.md, docs/collaboration/HTML_REPORTING.md와 아래 task를 읽고 그대로 수행하라.
- docs/collaboration/tasks/a3-data-intake-batch-20261025.md
- 자신의 artifacts/a3-data-intake-batch-20261025/LOCAL_INPUTS.json: 기본 checkout의 고정된 읽기 전용 입력 위치

기준 base 36469ce8504ce59784850dbb40ac75b2a096dc3e, branch claude/a3-data-intake-batch-20261025. 작업 시작 HEAD는 Codex가 전달한 dispatch SHA이며 임의 rebase/reset 금지. 기존 완료 worktree를 재사용하므로 디렉터리 이름보다 실제 branch를 확인한다. 자체 .venv의 card_condition.__file__이 이 worktree인지 확인한다.

핵심 사실과 요청을 요약한다:
- 새 채택본 c SHA 360f11cfdaaa61db103dd3f51e3c7e321ea3c0e5a69906cf872b10756dfaa932. f앞뒤/h뒤 box 확인만 반영, z 기존 box+표면 양성9개 보존. 이전 정답/box를 변경하지 않는다.
- A3는 5종 질문×앞뒤의 개발평가에 양성/정상 각20단위·각5실물, typed point/정상대조 출처 감사와 분모/결측/범위 동결이 필요하다. 전체30/100, A3 전부 충족 시에만+5. 현재 train/val20셀 중 train2만 수량 충족, val0. train+val 합산/split 변경/독립평가로 재명명 금지.
- 현재 val face 후보 앞14/뒤12로는40단위를 만들 수 없다. 최소 앞26/뒤28 신규사진이 필요한 하한부터 검산하라. 기존 val의 새 검토 후보를 우선하고 실제 자료 수집 부족을 드러내라. train 뒤표면 정상7개 보완은 후순위이며 A3 달성으로 말하지 마라.
- 이전29/28/25질문은 재질문 금지. 마지막25개는 미저장이지만 다시 묻지 않는다. 이번에는 f/h/z 실물과 사진 별칭도 전부 제외한다. 이미known인 정답도 제외한다. 얼굴전체 정상→구역정상 자동변환 금지.
- 전체 부족표/중복제외표 → 새 후보 전수 선별 → 최대12질문/6실물 첫라운드와 후속라운드 → geometry-first 선행 큐 → 기존 검토 UI용 정확 실행 인계 → 추가 자료 확보 명세 → 실제 집계 HTML까지 완료하라. 박스가 바뀌면 구역 질문을 자동 재사용하지 않는다.
- 라벨 서버/실제 사진 추론/모델 학습/외부 AI/API/키 접근/consumer 소스 변경을 하지 않는다. 원본 사진은 manifest가 지목한 파일의 해시/크기 확인만 하고 복사하지 않는다. Codex가 기본 checkout에서 첫 화면을 열고 사람 응답을 저장·대조·채택한다.
- 새 범용 도구/테스트 모음/UI를 만들지 마라. 기존 coverage_report와 review UI를 재사용하고, 자체 산출물 assert만 실행하라. 주어진 입력이 없으면 해당 항목을 blocked로 적고 독립 작업을 계속하라.
- 추적 변경은 task/prompt/report.md/report.html4개만. 실자료 패킷/스크립트/개인 경로는 자신의 ignored artifacts/a3-data-intake-batch-20261025/에만 둔다. 기존 manifest/ADOPTION/점수/모델/소스/테스트/Mastra 변경0.
- 보고 HTML과 private review.html을 실제로 열고 열기/렌더 확인을 구분해 인계하라. 정답 확보0, 추론0, 성능 개선 미평가, 진척30/100을 정확히 표시하라.

단계별로 커밋하고 최종 status ready_for_review, 전체SHA/부모/순서, 허용파일대조, 실제명령/결과, 패킷 절대경로/SHA, 라운드별 준비 질문/실물/geometry대기, 수집부족, 미검증/위험/롤백을 한 번에 인계하라. main 통합/push는 하지 않는다. 완료 후 다음 행동이 실제 첫 검토 화면 열기일 정도로 준비하라.
