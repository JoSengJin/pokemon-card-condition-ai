# 원본 출처·정정 이력 후속 감사

- task_id: `provenance-source-followup-20261025`
- owner: Claude
- status: ready_for_review
- base_sha: `fccc7099f027918fb4b718d70c6f6c09a3db8f32`
- branch: `claude/provenance-source-followup-20261025`
- dispatch_sha: 이 계약 커밋의 SHA를 Codex 전달 메시지에서 확인한다. 소스 기준 이후에는 계약 문서만 추가한다.
- worktree: 로컬 절대경로는 전달 메시지에서만 제공한다.

## 목표

직전 감사에서 근거 누락으로 남긴 세 항목을 추가 원본 snapshot으로 재검토한다. 사람에게 새 라벨·사진·면 정답을 요청하지 않는다.

1. 보완 6행의 photo-1/photo-3 `side=front`에 대한 근거가 실제 라벨 원본·검증 기록에 있는가? photo-4가 back이라는 사실과 다른 사진의 면을 구분한다.
2. eevee Y의 `current-effective`·정정 기록과 `Y_unknown` 검증 기록의 적용 시점·대상은 같은가? 파일명·수정시각만으로 최신 정답을 정하지 않는다.
3. raichu 모서리 정상 후보에 대해 후속 감사 실패·정정이 실제로 무엇을 무효화했는가? 모델 실패를 사람 정답 철회로 해석하지 않는다.

각 항목을 확인 가능/역사적/모순/근거 부족으로 구분하고, SHA·파일·필드·적용 범위를 근거로 제시한다. 채택/라벨 변경/수량 합산은 하지 않는다. 증거가 없으면 미해결로 남기는 것이 완료 가능한 결과다.

## allowed_files

- `docs/collaboration/tasks/provenance-source-followup-20261025.md`
- `docs/collaboration/reports/provenance-source-followup-20261025.md` (신규)

그 밖의 추적 파일은 읽기 전용이다. 과거 감사 보고서도 덮어쓰지 않는다. Python 소스·테스트·모델·라벨·진척률·기준·실행기·관제 UI는 변경하지 않는다. Codex는 별도로 집계 투영 계약을 검증하며 이 두 문서를 병행 편집하지 않는다. 기존 데이터 감사 브랜치와 `claude/pair-control` worktree를 조작하지 않는다.

## 로컬 근거와 checks

- `artifacts/collaboration/provenance-source-followup-20261025/evidence/index.json`의 상대경로·SHA를 복사본과 대조한다. snapshot은 Git 제외이며 사진·모델·키는 포함하지 않는다. 내부의 과거 절대경로는 문자열로만 읽고 기본 checkout을 탐색하지 않는다.
- 직전 감사와 `LABEL_CORRECTION_WY_20261019.md` 등 추적 문서를 함께 읽는다. 기본 checkout에서 수행한 최신 코드 수정과 과거 실패 재현을 구분한다.
- 추가 근거는 index에 별도로 표시했다. 필요한 원본이 여전히 없으면 파일·누락 이유만 기록한다. 사진 열람·추론·학습·외부 AI 호출·검토 서버·`./review --auto`는 실행하지 않는다.
- 이번 작업은 표준 라이브러리로 JSON/JSONL/Markdown의 기존 증거를 읽는 감사다. torch·모델·다른 worktree의 가상환경이 필요 없다. test split의 라벨·사진은 해석하지 않는다.
- `git diff --check`, 기준 이후 변경 파일과 allowed_files 대조, 문서의 개인 홈 경로·비밀값·실제 라벨 원문 과다 인용 검사를 한다. 보고서에는 필요한 필드·판단 범위와 상대경로만 적는다.
- SHA 대조에 성공한 것과 정답·면·실물·분할 조건이 입증된 것을 구분한다. 기존 기준·30% 진척률·모델 성능을 갱신하지 않는다.

## 인계·수용 기준

세 항목 각각의 결론·근거·미해결과 사람 입력 없이 가능한 다음 조치 최대 1개를 신규 보고서에 기록한다. 새 정답을 만들거나 국소자료를 primary에 편입하면 수용하지 않는다. status를 ready_for_review로 바꾸고 `docs(provenance): 원본 출처와 정정 이력 후속 감사` 커밋의 전체 SHA·부모·변경 파일·실행 검사를 인계한다. main 통합·push는 Codex가 담당한다.

롤백은 미통합 브랜치를 반영하지 않거나 통합된 이 task의 문서 커밋만 revert하는 것이다. 원본 데이터·모델은 변경하지 않는다.

## Claude 실행 결과

2026-10-25, 배정 worktree에서 실행. 보고서: `docs/collaboration/reports/provenance-source-followup-20261025.md`.

- 기준:
  - 브랜치 `claude/provenance-source-followup-20261025`, HEAD=dispatch `9379ed1c69b5bae1db002bcddf282e59b191ab7e`.
  - `merge-base --is-ancestor fccc709… HEAD` 종료코드 0. 시작 시 작업 트리가 깨끗했고, 기준 이후 변경은 이 문서뿐이었다.
- SHA: index 59개 중 59개 일치, 누락 0, 미등재 0. previous_snapshot 46개, additional_original 13개.
- 결론:
  1. 보완 6행의 면:
     - photo-4 back은 확인 가능하다(사람 진술). 단, photo-4는 6행에 포함되지 않는다.
     - photo-3 front는 근거 부족이다. `labels-review.jsonl`은 단일 사진 작업 슬롯 배치이고, `pair_verified: false`이며 사람 면 진술이 없다.
     - photo-1 front는 근거 부족이다. 원본이 snapshot에 없다.
  2. eevee Y:
     - corner 1 정정은 확인 가능하다. 사람 원문과 일치 기록 4개가 있고, 두 디렉터리의 current-effective가 바이트 단위로 동일하다.
     - `clarification-verification.json`의 `Y_unknown`·4행은 현재 파일과 맞지 않는 역사적 기록이다. 작성 시점은 근거 부족이다.
  3. raichu corner-1·3 정상: 사람 정답 철회 기록이 없다. "실패"는 단일 정상 group 때문에 group 평가가 불가능하다는 점과 RGB 지름길 대조라는 품질 한계였다.
- 다음 조치 1개: inventory에 면 근거 종류 필드를 추가한다(Codex 별도 계약, 값·수량 불변).
- 검사: `git diff --check` 통과. 변경 파일은 allowed_files 2개다. 문서에 홈 절대경로·비밀값이 없다. 사람 응답 원문 인용은 짧은 조각만 썼다.
- 미실행·금지 준수: 사진 열람·추론·학습·외부 AI·라벨 변경·합산·Python 소스·테스트 변경 모두 0회.
