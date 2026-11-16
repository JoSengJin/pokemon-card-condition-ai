# stable-low-reference-cause-design-20261116

task_id: stable-low-reference-cause-design-20261116
owner: Codex (페어코딩 설계 담당)
status: ready_for_review
base_sha: 3cbf778e6ebb8f237684989177896f4367ebd140
branch: codex/stable-low-reference-cause-design-20261116
worktree: 별도 관리 worktree, 절대경로는 세션에서만 전달

goal: 동결 기록에서 혼입12곳/혼합사진 적용29·거부89의 설명 가능 범위를 감사하고 다음 검증 하나의 사전 설계 또는 식별 불가 결론을 제출한다. 실행하지 않는다.

## 소유권

allowed_files:
- docs/collaboration/tasks/stable-low-reference-cause-design-20261116.md
- docs/collaboration/reports/stable-low-reference-cause-design-20261116.md

forbidden_files: 위 두 문서 이외 전부. 기본 checkout, .claude/, D-LOC 및 다른 worktree, 원본 artifacts, 라벨/점수/사진/모델/worker/실행기/PokeCollector/비밀 설정 보존. D1 봉인·표면 보충시험·폐기105·예약보류9그룹 열람 금지.

contract: PROMPT.txt/HANDOFF.md와 manifest38개를 읽기 전용 입력으로 사용. packet_path/SHA38/38 일치 확인 후 진행. 누락/불일치 시 기대·실제·경로 기록 후 중단하며 재분석 복구 금지. 허용 계산은 저장 연결·개수·교차표·기록값 검산뿐이다. 과거 worker/selector import·실행 금지. 원본 라벨·점수·사진·로컬 JSON·홈 절대경로 커밋 금지. 보고서에는 감사 파생표와 상대 근거 경로/키만 기록한다.

structure: 문서만 변경, 소스 함수 수/호출 경로 변경 없음(해당 없음).

## 작업 순서와 checks

- [x] 인계 계약/manifest와 현재 HEAD/status/worktree 확인. HEAD 일치, 기본 checkout 기존 미추적 .claude/ 보존.
- [x] manifest packet_path 38/38 SHA-256 일치, 불일치0.
- [x] 이 task 계약을 먼저 로컬 커밋하여 소유권 고정.
- [x] 저장 scored rows/photos, sealed references, B0와 snapshot의 정확한 키/값/분모/봉인 순서 대조. 혼입12행, 대조군, 거부 교차표 작성.
- [x] systematic-debugging의 원인 추적/대조, brainstorming의 가설·대안 비교, writing-plans의 단일 사전 설계/반례 점검을 설계 범위에 적용.
- [x] verification-before-completion: 근거 해시 재확인, 문서 요구사항/허용 경로/금지 내용/git diff --check 검사 후 로컬 최종 커밋.

experiment: 불필요/실행 금지. 신규 학습·추론·검증·사람 판정 요청·외부 AI 호출0. main 통합/push 금지. 구현용 설치·단위/모델 테스트는 수행하지 않는다. 이번은 설계 문서2개만 허용되므로 HTML 생성/열기/렌더는 하지 않으며 HTML_REPORTING.md의 지침/설계 준비 범위로 기록한다.

고정 조건: 진척78/100 유지(점수 재산정 없음), 제품 FN≤67/370·FP≤112/1406·AUC +0.03·사진그룹 bootstrap 하한>0·유효5fold 유지. D-LOC12/22·결정표④·후속 과제 선정 보류 유지.

## handoff

계약 커밋: `84d550698807ae57e60549f58ee4aa22538d7c1f`.
최종 설계 커밋은 이 문서 자신의 해시 순환을 피하기 위해 최종 응답과 전용 브랜치 `git log -1 --format=%H`로 전달한다. 최초 제출 후 사용자가 원문104곳 연결 결과의 문서 반영과 전용 브랜치 로컬 커밋을 추가 승인했다. 이번 보완 후 자동 실행하지 않는다.

변경: 허용 문서2개만 추가. 혼입12행·10사진SHA/봉인L/순위/간격/삭제 결과·기존 라벨 버전 연결, 대조47/151/183/FN45와 사진 출처 교차표, 혼합118의 적용29/거부63·16·10, 원인 식별 한계와 조건부 단일 출처 대조 설계 작성.
실제 검사: manifest38/38 해시, scored1776/204↔봉인↔B0↔fold 정확 연결, reference rows/before_scores 일치, 봉인 두 파일/selector SHA·truth timestamp, 실제 train/held 명부5개·group/photo 겹침0, 혼입12순위 동률0. 최종 문서 감사 PASS: 근거38개 불변, 혼입12행/사진10개 및 순위·간격·삭제 결과 일치, 고정 교차표 일치, 홈 경로 없음·개행/공백 검사 통과. 기본 main HEAD/status와 D-LOC HEAD/clean 상태도 착수값대로 유지됐다. 최종 staged diff 검사 후 로컬 커밋한다.
미실행: 모든 신규 학습·추론·검증·사람 요청·외부 AI·worker/selector/analyze 실행/import, 조건 완화 가상 성능, 모델 테스트, HTML 생성/열기/렌더, main 통합/push. 기존 원문104곳은 연결됐지만 단일 설계에 필요한 별도 독립 판정/동일 관찰조건 출처가 미확보되어 `not_executable_missing_evidence`; 물리적 H_L/H_M 식별 불가. score/라벨/모델 원본 수정0. 78/100·D-LOC12/22·결정표④·후속 과제 선정 보류 유지.
HTML 산출물: 없음. 두 Markdown만 허용된 설계 준비 범위이며 새 실행 성과 HTML을 만들지 않음.
구조: 소스 변경0, 함수 수/호출 깊이 해당 없음.

 리스크: 개발 자료 반복 관찰 편향과 원문 출처와 독립 판정/실제 관찰조건의 혼동. 롤백: 이 전용 브랜치의 두 문서 변경만 되돌린다. 원본 기록/기존 worktree는 복원·삭제하지 않는다.

## 사용자 요청에 따른 원문 출처 후속 보완 — 2026-11-16

- 선행 설계 커밋: `85f8a43ca375b821b155ad65237be6aaa5fd0621`. 같은 전용 브랜치의 기존 소유 문서2개만 갱신한다. 새 task/코드/로컬 JSON/HTML 생성 없음.
- 근거: 기본 checkout의 `artifacts/surface-label-audit-20261107/audit.json`·`preserved-inputs.json`, `surface-protocol-finalization-20261107/effective-decisions.json`, `surface-corrected-labels-cv-20261104/rows.json`, `zone-relabel-20261104/selection.json`·`answers-61-275.lines`, 기존 원출처 TXT7개. 상세 상대경로/해시는 보고서에 기록하며 동결38개 manifest는 변경하지 않는다.
- 연결 결과: 혼입12/12·같은사진47/47·나머지FN45/45 = 104/104 동일 구역ID·사진SHA·group·area 및 원문 줄/구역 연결. 원문 TXT 자체의 SHA 필드가 아니라 기존 사진/구역 metadata를 경유한 출처 사슬임을 명시한다. 원출처7개 SHA는 기존 보존값과 일치. 원사진 열기/재해시 없음.
- 독립성 구분: 혼입10곳은 현재 라벨 원출처,2곳은 §97 z73/z161의 이미 반영된 재판정. §97 화면은 점수/이전 라벨 비노출이나 선정은 점수 기반이며, 화면에 점수를 노출했다고 해석하지 않는다. 혼입12·대조47은 §93 연결0,나머지FN45만1곳 연결.104개 독립 판정 확보를 주장하지 않는다.
- 설계 상태: `not_executable_missing_evidence` 유지, reason=`independent_judgment_and_observation_provenance_unestablished`. 원문 부재가 아니라 별도 독립 판정과 동일 관찰조건·시점·비노출 요건 미확보가 실행 불가 사유다. S/D/U 채점·새 판정·가설 검증은 하지 않았다. 보호자료 열람·학습·추론·사람 요청·외부AI·main 통합·push 없음.
- 핵심 diff: 보고서의 원문 부재 표현 수정,104행 출처표와7개 원출처/metadata 해시 및 독립성 범위 추가, 이 handoff 갱신. 원문 라벨/점수/사진/홈 절대경로는 커밋하지 않는다.
- 문서 검사 PASS: 104행의 기존 감사 키/원문 포인터와 집합12/47/45 일치,7개 보존해시 일치,허용 파일2개·홈 경로 제외 확인 및 `git diff --check` 통과. 검사 후 로컬 커밋한다. 이번 검사는 문서/출처 연결 검사이며 설계 검증 실행이 아니다. 최종 SHA는 최종 응답/전용 브랜치 git log로 전달한다.
- 리스크: 기존 라벨의 원출처를 독립 정답으로 재사용하는 순환,표적선정과 화면 노출의 혼동,저장 연결과 실제 관찰조건 확인의 혼동. 일반화 개선/검증 실행 가능을 주장하지 않는다.
- 롤백: 이번 후속 보완 커밋만 `git revert <보완 SHA>`하여 선행 설계 문서 상태로 복귀. 기존 기록/다른 worktree/브랜치/원문은 보존한다.
