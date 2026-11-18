task_id: obslimit-rejudge-16-20261118
owner: Claude
status: ready_for_review
base_sha: 54f5fe780082c8fcdd5c702f9f8c40cbe3b0f29e
branch: claude/obslimit-rejudge-20261118
goal: '제한'으로 답했으나 사유 수집에서 not_limited로 표시된 후면 16장을 사람이 다시 판정하는 폰 페이지와 응답 검증기. 기존 답은 바꾸지 않고 재판정 응답은 별도 파일로만 받는다.
allowed_files: tools/mobile_visibility_rejudge_pages.py, tests/test_mobile_visibility_rejudge_pages.py, 이 문서
forbidden_files: 기존 라벨·answers.txt·answers-2.txt·holdout-rows.json 수정, 모델·worker·평가 기준 파일
contract: 입력 answers-2.txt(not_limited 행)·holdout-rows.json. 출력 HTML(artifacts, git 제외)과 붙여넣기 응답 검증. 응답 형식 `<group>/back=제한|정상|미확인;확신|애매`. 응답이 후보 16개와 다르거나 값이 어휘 밖이면 거부한다. 일치율 계산은 이 task 범위 밖(응답 수신 후 별도).
structure: 신규 파일 함수 4개(select_candidates, article, parse_rejudge, main), 최대 호출 깊이 2(main→article→encode 외부). 변경 전 해당 파일 없음.
checks: python -m unittest tests.test_mobile_visibility_rejudge_pages. 사진 열람·모델 실행 없음.
experiment: 없음. 새 학습·평가 아님. 성능 주장 없음.
handoff: 기능 커밋 1cd8607(전체 1cd86076bd6dcb49e10a3480a79bc26ec188bfdf), 이 문서 갱신 커밋이 tip. 변경 파일 3개(위 allowed_files). 구조: 함수 4개, 호출 깊이 2 눈으로 확인(정적 도구 미사용). RED: 모듈 없음으로 `unittest tests.test_mobile_visibility_rejudge_pages` FAILED(errors=1) 확인. GREEN: 같은 명령 exit 0, 6 tests OK(대상 SHA 1cd8607). 변이 점검(머리속): 후보 선택을 정확 일치로 바꾸면 혼합 행 테스트가 실패. 미검증: 페이지 JS(버튼 클릭→텍스트상자 갱신)는 브라우저 열기가 거부되어 실행 확인 못함, 사진 렌더도 미확인. 리스크: 응답 일치율 계산은 범위 밖. 롤백: worktree·브랜치 삭제, artifacts/obslimit-reasons-20261118/rejudge-1.html 삭제.

## 적용 스킬 (docs/AGENT_START.md 선택표)
- verification-before-completion: 완료 주장 전 테스트 명령·종료 코드를 읽고 기록. 읽은 범위 전체(120행).
- test-driven-development: 실패 테스트를 먼저 작성하고 실패 확인. `writing-good-tests.md` 전체 읽음. 문구 포함 여부·상수 값 같은 change detector 테스트는 쓰지 않고 행동(후보 선택, 응답 검증 거부)을 검사한다. SKILL.md는 1~120행만 읽음(나머지 미읽음).
- requesting-code-review: 기준은 base_sha. 하위 모델 호출은 하지 않는다(미승인).
- using-git-worktrees: 격리 확인만. worktree는 PAIR_CODING.md §4에 따라 별도 생성.
- 해당 없음: systematic-debugging(버그 작업 아님), receiving-code-review, brainstorming(요구 명확), writing-plans, executing-plans.
- 이전 사유 수집 페이지(54f5fe7 이전 커밋)는 이 순서(RED 먼저)를 지키지 않고 테스트를 코드와 같이 작성했다. 그 테스트에는 문구 포함 검사가 있다(change detector 성격). 이번 task에서 수정하지 않고 사실만 기록한다.
