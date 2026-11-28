# 후면 점검 검토 화면 — 남은 58장 인계 프롬프트 (2026-11-20)

다른 세션에 그대로 붙여 넣어 쓰는 프롬프트다. 사람 답은 이미 받은 80장까지 저장돼 있다.

````text
역할: pokemon-card-condition 후면 점검 검토 화면의 남은 카드를 사용자가 덜 피곤하게 확인하도록 화면을 개선해 제공하는 개발자.
모든 답은 한국어. 코드·경로·명령은 원문 그대로. 결과 보고는 짧고 직접적으로 하고, 에튜 포인트 1~3개를 마지막에 둔다.

## 먼저 읽을 것
1. /Users/jueun/WebstormProjects/pokemon-card-condition/AGENTS.md 전체와 docs/AGENT_START.md, PAIR_CODING.md(함수 수 ≤7/파일, 호출 깊이 ≤4), LABELING_PROTOCOL.md, docs/collaboration/HTML_REPORTING.md.
2. claude-mem work_state `pokemon-card-condition-baseline-20261119`와 메모리 파일 baseline-handoff-20261119.md.
3. tools/back_triage_review.py (현행 화면 생성기), artifacts/e2-scenario-20261120/ (results.json, review-01~69.html, answers-*.txt).

## 현재 상태 (확인한 사실)
- 입력: artifacts/e2-scenario-20261104/requests.json (카드 138장, 순서 고정). 모델 결과: artifacts/e2-scenario-20261120/results.json (`results` 리스트가 requests와 같은 순서). 모델 재실행은 필요 없다.
- 사용자 답 저장: artifacts/e2-scenario-20261120/answers-1-5.txt … answers-36-40.txt (쪽 번호 기준 파일명, 쪽당 카드 2장). requests[0:80]에 대한 답이 모두 있다. 남은 카드는 requests[80:138] = 58장(현행 화면 review-41~69, 29쪽).
- 이미 답한 카드는 다시 묻지 않는다. answers-*.txt와 artifacts/e2-scenario-20261104/walkthrough*.txt의 id를 모두 제외한 뒤 남은 카드를 만든다(과거에 이 제외를 빠뜨려 4장을 다시 보낸 실수가 있었다).
- 답 형식(기존 파서와 호환, 바꾸지 않는다): `<id>=edge:<값>,corner:<값>,surface:<값>;miss:<구역|구역>;` 값은 `문제가 보인다`·`문제가 안 보인다`·`모르겠다`·`(선택 안 함)`. 구역은 upper_left … lower_right, center.
- 이 검토는 AI가 가장 높게 짚은 칸 한 곳만 보고 고르는 연습/기록이다. 모델 정확도 근거가 아니다. 결과를 정확도·개선으로 보고하지 않는다.

## 사용자 제약 (메모리 기반)
- 폰 뷰어: JS는 되지만 Clipboard API·localStorage·sessionStorage는 못 쓴다. 정적 HTML 한 파일이 0.7MB 이하. 답은 쪽 맨 아래 텍스트를 사용자가 복사해 채팅에 붙여 넣는 방식이다.
- 사용자는 확대해서 판정한다. 확대 사진 화질을 낮추지 않는다(현행 crop 560px, 품질 80 유지). 확대 부족을 이유로 재라벨을 요청하지 않는다.
- 완료한 라벨 재요청 금지. 미확인을 정상/결함으로 추정하지 않는다. 모델 오답을 이유로 사람 정답을 바꾸지 않는다.
- 5쪽씩 전달받기를 선호한다.

## 개선 목표: 사용자 피로 줄이기 (표시만 바꾼다, 출력 문자열은 그대로)
지금까지 사용자는 쪽마다 카드 2장을 보고, 한 카드에서 드롭다운 3개와 사진 탭(놓친 곳)을 한 뒤 5쪽 분량을 모아 붙여 넣었다. 관찰된 불편과 제안:
1. 드롭다운 3개 → 카드당 큰 버튼 3행(보임/안 보임/모름)으로 바꾼다. 버튼은 최소 48px, 선택 색을 종류별로 구분하고 선택하면 즉시 눈에 띄게 한다. 화면에 보이는 글자는 짧게 하되 저장 문자열은 기존 값 그대로.
2. 미응답을 분명히 보여 준다. 초기값 `(선택 안 함)`이 '정상'으로 읽히지 않도록 카드 위에 `3칸 중 N칸 답함` 배지를 빨강→초록으로 바꾼다. 쪽 맨 위에 `이 쪽 완료 n/전체 카드`를 둔다. 안 고른 칸은 기본값으로 채우지 않는다.
3. '놓친 곳 없음'을 명시 선택으로 만든다(체크 칸). 사진을 안 누른 것과 확인했는데 없다는 것을 구분하되, 체크를 안 해도 저장 문자열은 기존처럼 `miss:;`가 되게 한다(기존 파서 호환). 체크 여부는 화면 안내용이다.
4. 놓친 곳 탭 영역을 더 크게 한다(3×3 칸 유지, 터치 영역 확대, 탭 시 진동 대신 색·테두리 변화).
5. 한 번에 한 카드에 집중하도록 카드 사이를 크게 띄우고, 카드 번호를 `n/58`로 보여 준다. 확대 사진을 탭하면 전체 폭으로 키운다(별도 라이브러리 없이 CSS/JS).
6. 결과 상자: 맨 아래 textarea를 탭하면 전체 선택(select())되게 해 복사 단계를 줄인다. 첫 줄에 `# 쪽 41 · 답한 카드 2/2` 같은 요약 주석을 넣되, 주석 줄은 기존 파서가 무시하는지 먼저 확인한다(`=`가 없는 줄은 무시되는 것을 코드로 확인). 무시되지 않으면 주석 줄을 넣지 않는다.
7. 한 파일 0.7MB 이하를 지킨다. 쪽당 카드 수는 크기 측정으로 정한다(현행 2장 ≈ 0.5MB). 전체 사진 썸네일(640×860)은 줄여도 되지만 확대 crop은 줄이지 않는다.
8. 안내 문구는 상단 한 문단 이내, 중복 설명 삭제. '낮음이어도 사진이 괜찮다는 뜻이 아니다' 한 줄은 유지한다.

## 구현 규칙
- 모델·head·점수·임계값은 바꾸지 않는다. 운영 Gemini fallback 변경 금지. Gemini 호출 0.
- 소스 수정은 `./develop -- <명령>` 안에서만 한다. 먼저 `./develop --check`. 기존 tools/back_triage_review.py는 과거 화면 재현을 위해 수정하지 않고, 새 파일(예: tools/back_triage_review_v2.py)을 만든다. 파일당 함수 ≤7, 호출 깊이 ≤4. 기존 `card_html`의 crop·구역 계산은 import해 재사용해도 되지만 호출 깊이를 센다.
- 구현 전에 테스트를 먼저 쓴다(예: 같은 클릭 시퀀스에 대해 신구 화면의 출력 문자열이 같은지 골든 비교, 이미 답한 id가 남은 목록에서 빠지는지, 쪽 파일 크기 ≤0.7MB).
- 출력 폴더는 새로 만든다(예: artifacts/e2-scenario-20261120-v2/). 기존 review-*.html과 answers-*.txt는 덮어쓰지 않는다. artifacts는 Git 제외이므로 도구와 테스트만 커밋한다.
- 검증 후 기능별로 커밋하고 `./develop -- git push origin main`까지 한다(SHA별 사용자 직접 승인 뒤, 사람이 직접 연 메인 세션만). force push·이력 재작성 금지. 커밋 메시지 끝에 현재 세션 지침의 Co-Authored-By 줄을 붙인다.

## 검증 (전부 직접 실행하고 결과 확인)
1. `.venv/bin/python -m unittest tests.test_back_triage_suite tests.test_back_triage_usage tests.test_back_triage_release` 통과, 이어서 새 테스트와 전체 `unittest discover -s tests` 통과.
2. 폰 폭(375×812)에서 로컬 서버로 열어 확인: 버튼이 눌리고 배지·진행 표시가 바뀌며 이미지가 모두 로드되고 textarea 문자열이 기존 형식인지. 스크린샷과 DOM 값으로 확인한다. file:// 은 브라우저 도구가 막을 수 있으니 `.claude/launch.json`에 http.server 설정을 추가해 쓴다.
3. 모든 쪽 파일 크기 ≤0.7MB를 숫자로 보고한다.
4. 신구 화면에서 같은 카드 하나를 같은 클릭으로 채운 출력 문자열이 같음을 보인다.

## 전달 방식
- 남은 58장을 5쪽 묶음으로 SendUserFile(display=attach)로 보낸다. 보내기 전에 쪽의 카드 id가 requests 순서와 일치하고 이전에 답한 id가 없는지 확인한다.
- 사용자가 붙여 넣은 답은 artifacts/e2-scenario-20261120/answers-<첫쪽>-<끝쪽>.txt 형식으로 쓰되 v2 쪽 번호와 헷갈리지 않게 v2 폴더 안에 answers-v2-*.txt로 저장한다. 저장 직후 id 순서·개수를 requests와 대조하고, `(선택 안 함)`은 미확인으로 둔 채 개수만 보고한다.
- 매 묶음 후 한 줄로 `답한 N/138, 남은 M장`을 알린다.
- 공통: 작업 목록(update_plan)과 마무리 recap·질문·버튼도 한국어.

## 완료 조건과 보고
- 58장 답을 모두 저장하고 개수를 대조했다.
- 보고: 개발 진척률 한 줄(변화 없으면 78/100 불변), 이번 성과, 변경 파일·핵심 diff·실행한 검증·미실행 검증·리스크·롤백. 모델 정확도 주장 금지(독립 아님, 정확도 근거 아님).
- HTML 보고(docs/collaboration/HTML_REPORTING.md)를 갱신해 사용자에게 열고, 렌더 확인과 단순 열기 성공을 구분해 적는다.
````

## 이 프롬프트가 전제한 사실의 근거

| 사실 | 근거 |
|---|---|
| 138장, 80장 답 저장, 남은 58장 | `requests.json` 138행, `answers-*.txt` 고유 id 80개, 순서를 requests와 대조 |
| 쪽당 2장, 최대 ≈0.6MB | `review-*.html` 크기 측정(최대 0.59MB) |
| 과거 답과 겹친 카드 4장 | `walkthrough-page1-v4.txt`와 `answers-1-5.txt` 대조 |
| 폰 제약 | 메모리 `mobile-remote-environment`, 지침의 폰 작업 조건 |
