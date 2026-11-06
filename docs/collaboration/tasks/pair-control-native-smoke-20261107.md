# 관제도구 핵심 실계정 교대 확인

- task_id: pair-control-native-smoke-20261107
- owner: Codex
- status: integrated
- base_sha: a4ad9eb2b9e420507d07b792ed9e5da8f48c1a8e
- branch: codex/pair-control-native-smoke-20261107
- goal: 기존 회귀를 반복하지 않고 새 메인 양방향 인수2회와 교대 뒤 연속 통합2회만 확인한다.
- authorization: 일반 진행 요청을 실제 CLI 시험과 계정 추가 사용 꺼짐 확인으로 함께 해석했으나 사용자 의미 확인 뒤 부적절한 해석임을 정정했다. 추가 실제 호출 중단, 사용자 직접 계정 확인 사실 없음. 가짜 CLI 수정·검증만 진행.
- allowed_files: 이 계약, docs/collaboration/reports/pair-control-native-smoke-20261107.html, Git 제외 artifacts/pair-control-native-smoke-20261107/ 증거.
- forbidden_files: 제품 소스/테스트/설정/운영 상태/다른 세션 서버/.claude/사진/라벨/모델/학습/추론. 운영 Git push는 시험에서 금지하며 검증 문서 main 일반 push는 기존 승인 범위다.
- execution: 기본 checkout에서 독립 임시 Git·bare 원격·합성 파일만 사용. 기존 준비 절차 재사용, 실제 HOME과 무료 가드·로그인·설정 검사 유지. 실제 CLI 작업 총 최대4(내부 공급자 API 요청 수4회 뜻 아님). push_main 승인 없음.
- stop: 과금/한도/권한/응답 오류·결과 불명이면 중단, 재요청/구매/유료 전환 없음. 이미 요청한 CLI는 같은 시험에서 재실행하지 않는다.
- checks: source SHA/잠금/.claude 해시 → 무료 사전 조건 → 인수/연속 처리 최대4CLI → 실제 종료/응답/상태/Git 근거 확인 → HTML 렌더·증거 보존. 소스 무변경이면 전체320회귀/typecheck/구조 검사를 반복하지 않음(직전 검증 재사용으로 표시).
- structure: 제품 소스 변경0, 문서 함수0. 직전270파일/783정의/최대7/전이4 결과를 재사용, 이번 실행으로 새 검사 통과 주장 금지.
- rollback: 운영 변경 없음. 시험 fixture/결과 불명 증거 보존. 문서만 필요 시 git revert, force/reset/다른 프로세스 종료 금지.

## 실측에 따른 최소 수정 범위

- 실계정 CLI3개에서 Claude 인수·후속 통합은 통과. Codex는 Git 밖 입력 폴더를 거부해 종료1, 즉시 중단·재요청0·4번째 작업 미실행.
- 설치 Codex exec --help의 --skip-git-repo-check 지원을 모델 호출 없이 확인했다. 이 옵션으로 메인/리뷰의 독립 입력 묶음을 지원하고 read-only를 유지한다.
- allowed_files 추가: tools/pair-control/src/executor/executor.ts, tools/pair-control/src/executor/reviewStart.ts, tools/pair-control/src/executor/adapterProbe.ts, tools/pair-control/test/fake-cli/codex, tools/pair-control/test/adapter-probe.test.ts, tools/pair-control/test/free-launch.test.ts, tools/pair-control/test/pipeline-start.test.ts, tools/pair-control/test/bundle-cli.test.ts, tools/pair-control/README.md. 제품 변경0 계획을 이 실측 결함의 최소 수정으로 변경한다.
- 검증 축소: 임시 Git 밖 메인·리뷰 시작과 미지원 CLI 차단 3개만 반례로 검증. 필수 타입·구조 검사는 빠르게 실행한다. 전체320회귀·이미 완료한 실제 Claude 경로는 반복하지 않음. 기존 fake 도움말/필수 옵션 기대값만 새 옵션과 일치시킴.
- 이번 승인으로 실패한 실제 Codex 요청을 자동 재시도하지 않는다. 수정 후 실계정 Codex 확인은 미실행으로 구분한다.

## 승인 해석 정정

- 사용자는 후속 질문에서 “실제 모델이라면 뭘 말하는거야?”라고 확인했다. 앞선 일반 진행 요청을 실계정 시험 승인 및 계정 추가 사용 꺼짐 확인으로 함께 해석한 것은 부적절했다. 양쪽 계정의 추가 사용 꺼짐 직접 확인을 받은 사실은 없다.
- 실제 실행 사실: Claude CLI 응답2개, Codex CLI 시작 오류1개, 합계 CLI3개. 추가 실제 호출은 중단했다. 청구/추가 과금0을 확인했다고 보고하지 않는다. 이후 수정 검증은 stub/fake CLI만 사용한다.

## 인계

- 수정 소스 SHA: 95185459fb23f22329f06cfd81410336b80b0285
- 실제 CLI3개: Claude 응답2(인수·연속 통합 통과), Codex 시작 오류1. 4번째 실행/재시도0. 계정 추가 사용 꺼짐·청구0 미확인.
- 최소 수정: Git 밖 메인/리뷰에 Codex skip-git-repo-check + 기존 read-only, 도움말 필수 옵션 확인. 제품 파일3개 함수7/5/4 불변.
- 가짜 CLI 핵심3개+인증 보호2개 모두 통과. 타입/구조 검사 통과. 전체320개 재실행하지 않음(사용자 검사 축소 요청). main은 검증 소스와 동일 대조.
- 구조 JSON 직전과 전체 동일: 270파일/783정의/최대7/실제전이4/초과0/미확인86/외부2741. 출처 분류 근거 해시 모두 불변.
- 실제 Codex 수정 후 재시험 미실행. 모델 성능 미평가. 문서/증거: docs/collaboration/reports/pair-control-native-smoke-20261107.html 및 artifacts/pair-control-native-smoke-20261107/. HTML IAB 열기·실제 렌더 확인 완료, 화면 증거 보존.
- 리스크/롤백: 새 옵션 없는 CLI 사전 차단. 읽기 전용 유지·Git 존재 확인 생략, 도구 생성 입력 묶음만 사용. 역순 git revert·핵심 검사·일반 push.
