# 정상 공동 제외 실측 — 2026-10-27

개발 진척률 **30/100 (usable-card-analysis-v1.0, +0%p)**. 성과: 미실행이던 정상 공동 제외16fit을 실제 수행했고 사전규칙 H3에만 일치했다. 성능개선/인과확정/독립검증/운영채택 아님.

## 실제 기록과 판정

- record: artifacts/experiments/20261027T132418-8a5aa6ae/record.json
- status: completed, return_code0, 24.676초.
- diagnostic H3=true, H1=false, H2=false. 모든16fit수렴. 단독제외4개재현최대차2.9802322387695312e-8, .5판정일치. 기준선147행재생최대차0.
- source: main084a2c3에통합한196664e, workerSHA 5c2f573f110042b8695170755d95e52af26367f363ed013e6591e68ec47c6a59.
- primary_acceptance_passed=true는기존기준선재생일치일뿐이며 전체acceptance_passed=false.11required_cohort는기존부터모두미통과였고점수/행/기준을동일하게재생했다. 보호검사보존을품질통과라고부르지않는다.

## 정상 실물별 실측 (각9구역, 사람정답 모두0)

| 대상 | 단독 제외FP | 다른 정상1 제외 | 다른 정상2 제외 | 다른 정상3 제외 |
|---|---:|---:|---:|---:|
| A |2/9|B:3/9(+11.11%p)|C:4/9(+22.22%p)|D:3/9(+11.11%p)|
| B |1/9|A:0/9(-11.11%p)|C:2/9(+11.11%p)|D:4/9(+33.33%p)|
| C |1/9|A:4/9(+33.33%p)|B:1/9(0%p)|D:4/9(+33.33%p)|
| D |4/9|A:5/9(+11.11%p)|B:4/9(0%p)|C:8/9(+44.44%p)|

방향쌍12개는고유학습집합6개를공유한다.4실물/출처·크기·디자인교란을유지하며12개독립반복으로합산하지않는다. H1/H2 미충족은그가설의반증이아니다. 양성은진단평가분모0이므로진단FN은미측정이다.

주평가재생은동일147구역 FN16/94(17.02%)→16/94, FP18/53(33.96%)→18/53,각0.00%p. 실제점typed51 FN21/51(41.18%)→21/51,0.00%p. 진단head수치와이재생수치를혼합하지않는다.

사진구역정답/각head점수: artifacts/experiments/20261027T132418-8a5aa6ae/index.html (16PNG패널). 독립시험이아닌반복개발진단이며원사진은Git제외.

## 변경 파일·핵심 diff·실행

- tools/experiments/surface-normal-coexclusion-20261025/worker.py: Claude완료본을통합.4재현후12방향쌍,양성53행고정/학습평가실물·원본/decoded해시분리,기준선/11cohort보존,진단규칙·사진출력.
- 같은폴더 plan.json: 고유가설/사전H1H2H3/11cohort/11SHA/호출0동결.
- tests/test_normal_coexclusion_worker.py: 전달된6합성검사. 새검사를양산하지않았고실제16fit로이어갔다.
- docs/collaboration/tasks/surface-normal-coexclusion-20261025.md: 실제완료브랜치/검토해소상태정합.과거잠금밖편집사실은보존.
- docs/collaboration/tasks/normal-coexclusion-run-20261027.md, 이MD/동명HTML: 실행범위·결과·한계기록.
- 명령: ./experiment --plan tools/experiments/surface-normal-coexclusion-20261025/plan.json -- .venv/bin/python artifacts/surface-normal-coexclusion-20261025/worker.py
- 실행전관련9검사OK,최종관련12검사OK. worker함수7/test함수7,학습최대4전이(기존계약LBFGS내부프레임제외).

## 리스크·롤백

4장에대한사후패턴으로새실물일반화를증명하지못한다. 분모9는구역수이며독립실물9장이아니다. 모델복구불필요. 구현제거는 ./develop -- git revert 196664e 후관련검사/일반push. 인계문서통합084a2c3과추적보고서는별도revert가능. 실제실험은성공/실패모두삭제하지않는다.

## 에튜 포인트

대조재현을먼저통과시켜야새비교를해석할수있다.같은설정으로기존점수를재현하지못하면데이터/코드차이와정상카드제외효과를구분할수없다.이번4대조는판정까지같았으므로뒤의FP변화를계획한제외조건에대한민감도로읽을수있다.

## 보존·운영·협업 경계

Claude 데이터 보완 checkout·신규 라벨/manifest/사진·coverage 구현·소비서비스는 변경하지 않았다. 기본 checkout에서 공통 실행기로만 직렬 실행했다. 기존 입력11개와 사람응답 파일의 전후 SHA 일치 확인. 외부 Gemini/Codex 모델 호출0, 새 backbone forward0, 운영모델 채택0. 새head는실험폴더전용이거나수렴실패로저장되지않았고 card_condition 모델 소스 수정0이다.

자동검토 정책의 session_id와 현재 세션이 달라 자동 handoff는 생성되지 않았다. artifacts/development-cycle/latest.json은 과거 세션 기록이며 이번 성공/실패 기록을 대신하지 않는다. 이번 next_steps/token_report 자동산출물도 없다. 실제record경로를직접사용한다.

코드 검증은 main `ad3ea94e0a3f5954fb7247d65803c4735ac7bed1` 기준 관련12개 검사 OK(0.968초), git diff --check 통과. 12개는 수식/계약 검사이며 성능 수치가 아니다. 문서와 HTML 내용 대조 및 외부스크립트/개인경로 없음 검사. 전체회귀/독립평가/실사용 검증은실행하지않았다.

원격: 코드 main/origin ad3ea94 일치 확인 후 보고 문서를 추가한다. 최종 문서까지 일반 push한다. force push 없음.

정리: 통합 대응2커밋·clean·개발잠금·고유lock 증거SHA 보존을 확인한 이전 Codex typed-point-assessment checkout만 일반 worktree remove로 정리했다. 브랜치/이력은 보존했고 최근 normal-group-objective checkout을 롤백용으로 유지한다. Claude 데이터/미통합/부분통합 작업과 다른 Codex checkout은 보존. 감사는 artifacts/normal-coexclusion-run-20261027/worktree-cleanup/audit.json.

HTML: 실제 사진 보고서는 Codex 열기도구 queued 및 탭 목록 존재 확인. Browser Use URL policy가 file URL 접근을 차단해 HTML 실제렌더 미확인이다. 서버/터널/다른브라우저로우회하지않았다. 생성PNG1개는이미지뷰어로직접확인했고 GT=0과점수·색상구역표시를확인했다. 이것을 HTML 렌더 검증으로 대체하지 않는다.

## 다음 의존과 중단 근거

성능을 올렸다는 근거는 아직 없다. 공동제외 진단은 정상 실물 쌍 민감도를 좁혔으나 원인을 확정하지 못했고, 후속 단일 목적식은 수렴하지 않았다. 기존 색특징결합·양성손실조정도이미시도된이력이있다. 이번실행의온도/반복수/수렴허용치변경·동일가설재학습은사전기준위반이므로하지않는다. 추가모델변경을정당화할새근거는현재없다. 다음성능평가는Claude소유데이터보완에서오는다양한정상실물의명시적정답과고정geometry/분리감사에의존한다. 이자료를우회해unknown을정상으로채우거나독립자료를개발에편입하지않는다.
