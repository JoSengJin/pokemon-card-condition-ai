# 최신 프로젝트 근거를 쓰는 수동 교차 검토

이번 범위의 수용기준4/4 완료: 최신실패·실험자동수집, 같은cohort/근거SHA보존, 수동후속검토최대3회와누적usage, 기존명령/중단재개호환. 모델정확도/독립검증/절감률의완료율이아니다.

명령은그대로다:

```sh
./review
```

## 최신 근거 선택

새검토시artifacts/*/result.json 중지원하는paired-score 실험형식을수집한다. 날짜있는실험디렉토리의날짜→result수정시각순으로선택하며cross-review/manual실행결과는제외한다. result가reference/runs.candidate를가진형식과before_scores/scores형식을지원한다. 새결과형식은전용adapter가필요하다. 예제packet으로대체하지않는다.

저장된점수와인간이확정한binarytarget을기존compare_predictions로검산한다. group/사진hash/box/ID/target/fold/profile/split동일성해시가같은과거실패만비교이력에사용한다. 최신결과수치가틀리면오래된결과로대체하지않고중단하며, 잘못된과거이력은제외한다. threshold0.5계약외자료도자동혼합하지않는다. decoded사진hash와원본파일SHA를동일한것으로가정하지않는다.

현재선택되는것은artifacts/edge-normal-objective-20261019/result.json이다. 기존저장보고서에서정상FP5→3/22·FN0/4/실제점누락0/4였던개선과후속geometry-diagnostic에서추가개선없음(FP3/22·FN0/4)을분리해전달한다. 현재오류3개ID/확정target/저장점수/전후점수를포함한다. geometry가승인된positive평가행0이라는한계도포함한다. 이수치는새평가가아니라원래저장된결과다. 새추론/학습/label수정0이며새모델성능비교HTML대상이아니다.

자료구성: 최신result/plan, 후속geometry진단(있으면), 같은cohort의최근실패최대4개, 남은오류최대12개(전체오류건수별도), 관련프로젝트함수최대2000자, 실행당시candidate.py함수최대2000자(있으면). 현재구현과과거실행snapshot은구분한다. 전체사진/대화/저장소/긴로그/비밀설정은전송하지않는다. 최신정체근거가없거나관련코드가없으면호출하지않는다. packet최대24KB검증은유지한다.

최신파일은시작시에만수집하고모든출처경로·SHA를packet.latest_sources로기록한다. 중단재개때원자료가바뀌어도이미저장한packet/config를읽는다. 새원자료는새검토에서만반영한다. 현재수집packet미리보기는artifacts/cross-review-latest-20261019/packet-preview.json.

## 최대3회와 종료

첫응답에서Enter는종료, q는저장, r은추가검토다. r을 선택하면 프로그램이 현재 응답에 맞는 반증 질문과 유효한 근거 ID를 자동 선택한다. 보낼 질문과 근거를 한글 안내로 표시한 뒤 추가 호출하며 직접 입력은 없다. 선택할 새 질문·근거가 없으면 종료한다. 최신 변경·검증은 AUTO_COUNTER_REVIEW_20261019.md를 따른다. 직전질문+근거ID가반복되면핵심그래프가종료한다. 모델이사람정답/새자료가필요하다고하면추가r호출을막고종료또는보존만허용한다. 완료된사람라벨을재질문하거나모델제안으로바꾸지않는다.

각후속요청에는동결근거와현재대조질문/직전제안하나만담는다. 전체토론대화는누적전송하지않는다. 핵심validate와journal상한도3으로바꿨다. SDKattempts=1/자동fallback없음은유지한다. 세번째응답후r을눌러도네번째호출은차단된다. 실제usage는모든시도에대해합산하고항목누락이하나라도있으면해당누적항목은미확인으로남긴다.

예산: 입력72000/출력12288/총84288예약량, 응답출력최대4096, thinking minimal, wall-clock600초. 이것은RPM/TPM/RPD가아니라검토한건의로컬예산이다. 실제token수와UTF8입력예약량은구분한다. 예산·시간·반복·오류·사람의존종료가3회보다먼저적용될수있다. 모델합의/응답파싱성공이성능개선을뜻하지않는다.

기존예제로멈춘active검토는superseded.json사유만기록하고DB를보존한채새최신검토를만든다. 과거실행을새packet/3회설정으로덮어쓰지않는다. 이미최신source_mode인미완료실행은그대로재개한다.

## 변경 파일

- card_condition/cross_review_evidence.py: 새최신근거수집기. 기존비교함수재사용.
- card_condition/cross_review.py: 상한2→3, 직전제안문구가바뀌어도같은질문/근거반복이면종료.
- card_condition/cross_review_manual.py: 예제복사제거/최신수집연결, r후속입력/최대3회, 누적usage, 과거예제대기보존/전환.
- tests/test_cross_review_evidence.py, tests/test_cross_review_manual.py, tests/test_cross_review.py: 선택/정답동일성/최신자료검증/3회상한/재개회귀.
- README.md, ONE_COMMAND_REVIEW_20261019.md, 본문서와검증artifacts.
- review실행파일·전용키·학습코드·원본라벨·소비프로젝트는변경하지않았다.

검증: 최종tests.log및verification.json참고. 실제현재프로젝트근거수집과mock SDK를연결한전체CLI흐름도별도임시DB에서성공했다(current-data-mock-smoke.json). 이로그는실제Gemini응답이아니고새외부전송도없다. 이번실제Gemini추가호출0회/실사용token미측정. 기존1회/실토큰1753기록은이전실행이며이번개선의실측값으로재사용하지않는다.

## 리스크 · 롤백

현재의지원실험형식외새로운보고서형식은adapter확장이필요하다. 최신실험은파일수정시각만이아니라디렉토리날짜가우선한다. 독립시험과반복개발자료를혼합하지않으며이번선택자료는독립성능시험이아니다. 최대3회이므로기존1회보다실제요청과usage가증가할수있고토큰절감은주장하지않는다.

롤백은.backups/cross-review-latest-20261019/에서cross_review.py/cross_review_manual.py/관련기존tests/README.md복원후새cross_review_evidence.py·그test를사용중지한다. 최신자료로이미생성한실행DB/영수증/동결입력은보존한다. 기존예제대기검토를복구하려면기록을먼저확인해야하며자동으로이전active포인터를되돌리지않는다. 키복구나모델파일롤백은필요없다.

에튜: 동일cohort의키에사진hash·영역·정답을함께넣으면같은ID라도다른사진이나수정정답을개선비교에섞지않는다. 이번수집기는그해시가같은실패만새검토이력으로넘긴다.
