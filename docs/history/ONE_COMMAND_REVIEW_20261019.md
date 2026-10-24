현재 기본 1회·최대 3회와 같은 자료 재사용 동작은 [최신 사용법](DEFAULT_ONCE_REVIEW_20261019.md)을 따릅니다. 아래는 이전 구현 이력입니다.

# 수동 교차 검토 명령 하나

이번 수용기준4/4(100%) 완료: 단일 실행 명령, 응답 출력/중단/재개/종료, 검토당 최대1회 호출, 중단 후 같은명령재개/추가호출0. 모델정확도/일반화/절감률과 무관하다.

어느 폴더의 터미널에서든:

```sh
./review
```

- 새검토를 만들고 기존정체실험예제 packet을 전용키로 전송한다. 전송전 모델/자료파일/오류건수/근거ID/호출상한/출력상한/무료확인기록/저장위치를 표시한다.
- 현재모델은전용local-config.json의 gemini-3.5-flash-lite. 최대호출1, thinking minimal, 출력상한4096, 입력예산16000/출력8192/총24192, 시간600초로동결한다. 비밀키는기존프로젝트전용읽기방식을그대로쓴다.
- Gemini응답8개항목을한글제목으로보여주고실제LangGraph interrupt에서입력을기다린다. Enter는저장지점에서 action=stop으로재개후종료한다. unresolved는실험미채택종료라는의미다. 자동실험선택/모델수정은하지않는다.
- q나Ctrl+C는상태를보존한다. 같은명령을다시실행하면미완료검토를이어간다. 요청전송중Ctrl+C로응답이불명확해져도journal의pending때문에재호출하지않는다.
- 검토가종료된뒤같은명령을실행하면별도새검토를만든다. 이것은사용자가명시적으로시작한동일예제자료의수동검토체험이며새성능실험결과가아니다. 자동새토론/반복학습은없다.
- 2차검토선택지는없다. 기존execute의max_calls=1과SDK의HttpRetryOptions(attempts=1)을재사용한다. 설치된google/genai/types.py:2258은attempts가원래요청을포함한전체시도수라고명시하며_api_client.py:524에서stop_after_attempt로적용한다. 별도API호출관리자를중복구현하지않았다.
- artifacts/manual-cross-review/ 아래검토별packet/config/decision/result/state.sqlite를저장하고active.json으로미완료검토를찾는다. 최상위session.lock은동시터미널중복시작을막는다. DB/active.json은삭제하지않는다.
- 파이프입력등비대화형실행은API호출전에거부한다. 인증/한도/요청오류는추가사용자입력이나자동재시도없이종료한다. 실제usage없음은미확인으로표시한다.

## 변경 파일

- review: 실행위치를프로젝트로맞추고기존.venv로새UI모듈실행. 실행권한설정.
- card_condition/cross_review_manual.py: 기존execute/SQLite체크포인트와ReviewStore의atomic_write를재사용하는터미널입출력. 새의존성없음.
- tests/test_cross_review_manual.py: 새UI9개검사.
- README.md: 명령한줄안내추가.
- 본문서 및artifacts/cross-review-one-command-20261019/테스트·검증기록.

## 실행 검증

실제LangGraph/SQLite와SDK mock으로기존27+UI9=36테스트통과(tests.log). 새검토→응답표시→중단→Enter재개종료, q/프롬프트Ctrl+C후같은검토재개추가API0, 전송중Ctrl+C응답불명재호출차단,잘못된입력,완료후새검토,429오류종료,비대화형거부,동시실행거부를검사했다. 각검토별mock SDK호출최대1을확인했다.

sh -n review통과. 프로젝트외부/private/tmp에서도절대경로review --help실행성공. 이번개발의실제Gemini추가호출0회/실사용토큰측정없음. 이전r2실연동검증은별도기록으로유지한다. 새모델학습/평가0회이므로성능HTML대상없음.

## 리스크 · 롤백

기본자료는기존예제이며최신실험증거를자동수집하지않는다. 완료후명령을다시실행하면새검토가생겨다시최대1회사용한다. 저장파일을지우면중복방지근거가사라지므로보존한다. 무료등급/한도는변경될수있고현재설정의확인기록을출력하며자동조회하지않는다.

롤백은신규review/cross_review_manual.py/test_cross_review_manual.py를제거하고README.md를.backups/cross-review-one-command-20261019/README.md에서복원한다. 토론기록은삭제할필요없다. 기존핵심cross_review.py/키/운영코드/사람라벨/모델은이번변경대상이아니다.

에튜: 체크포인트는중단된계산위치를저장하고journal은이미시도한외부호출을기억한다. 이번코드는q후다시시작할때같은DB를읽으므로응답을다시받지않고이어간다.

## 최신 자료 · 최대3회로 갱신 (2026-10-19)

최신 동작은 위 과거 예제/1회 설명 대신 CURRENT_REVIEW_EVIDENCE_20261019.md를 따른다. 실행 명령은동일하다. 새검토시현재프로젝트의지원하는최신실험result/후속진단/동일cohort실패이력/관련코드에서packet을자동구성한다. 검토당최대3회이며 r을 누르면 현재 응답에 맞는 반증 질문·근거를 자동 선택하고 한글로 표시한 뒤 추가 호출한다. 질문/근거 ID 입력은 없다. 최신 변경·검증은 AUTO_COUNTER_REVIEW_20261019.md를 따른다. Enter종료/q보존은유지한다. 과거예제대기검토는기록만보존하고새최신자료검토로전환한다. 재개중인최신검토는동결된자료와설정으로계속된다.
