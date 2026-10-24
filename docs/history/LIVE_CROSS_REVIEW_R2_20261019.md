# 교체 키 · Gemini 3.5 · 실제 LangGraph 중단/재개 검증

이번 검증 수용기준4/4(100%) 완료: 전용 키 교체, 성공 요청1회, 실제 checkpoint 중단→재개→종료/추가호출0, 실제 usage 기록. 전체 카드 모델 완성도/정확도/토큰 절감률을 뜻하지 않는다.

## 실제 결과

- 전용 프로젝트: pokemon-card-condition / gen-lang-client-0184747717. AI Studio 무료 등급 재확인.
- 새 키: pokemon-card-condition-cross-review-r2. 사용자가 직접 최종 발급했고 이전 노출 키를 직접 삭제했다. 새 키만 남은 화면 확인 및 로컬0600 저장/새 fingerprint/런타임 읽기 일치를 검증했다. 새 키는 출력하지 않았다. PokeCollector 비밀파일/키 미접근.
- 모델 gemini-3.5-flash-lite, thinking_level=minimal, 최대 Gemini 생성1회, 출력상한4096, 입력예산16000/출력예산8192/총예산24192, 시간600초. SDK retry 총1시도, 자동 fallback 없음.
- 이전 전송과 packet 파일 byte 일치. SHA256 caa261ce3ee4184447153bc1a530f877dd8d4e2f5ba6a8ead2b4f0a9622be9f8. 같은 오류5건/개발평가26구간 수치/실패가설2개/한 줄 코드와출처/해시만 전송했다. 프롬프트에 사진·키·전체저장소·대화 없음.
- HTTP200, 이번 추가 요청1회/성공생성1회. 이전 HTTP404 1회를 포함해 누적2회. 이후 대기조회/재개/종료조회/캐시재사용 추가요청0회. SDK metadata와 별도로 HTTP 영수증으로 전송횟수 확인.
- 실제 입력1482, 출력271, 합계1753토큰. thoughts_token_count는null(미확인). 입력+출력과 총합이 같더라도 누락된 thinking 필드를0으로 바꾸지 않았다. 이전404는usage없음이므로 두요청의누적실사용토큰은확정할수없다. 최소thinking은thinking0 보장이 아니다.

실제 metadata는 artifacts/cross-review-live-r2-20261019/initial.json의 attempts 및 http-requests.json에 저장돼 있다. 입력예약량3721은 실제토큰이아니다. 토큰절감률은측정하지않았다.

## 실제 그래프 경로

1. Gemini 노드: 실제 요청1회, 8개 문자열JSON 응답 파싱·완료journal 저장.
2. compare 노드: codex_evidence_comparison interrupt. SQLite checkpoint에 대기상태 저장.
3. 별도프로세스에서같은실행조회: awaiting_comparison 및같은응답 복원, 추가요청0.
4. Codex가 로컬코드·기존결과해시를대조하고 action=stop으로재개. 최종status=unresolved, checkpoint.next=[]로종료.
5. 종료한실행다시조회: 같은종료상태 및완료요청1행 유지, 추가요청0.
6. 별도복제DB에서checkpoint/writes만제거하고실제완료응답journal을유지: 캐시로같은응답/interrupt재사용, HTTP송신함수호출0. 실제원본DB는최종종료상태로보존했다.

증거: initial.json, paused-read.json, resumed.json, completed-replay.json, state.sqlite, cache-proof.sqlite, http-requests.json, verification.json. 모형이아닌실제LangGraph/SQLite와실제Gemini응답을사용했다. 원본DB의모든checkpoint단계와pending은verification.json에요약했다.

## 응답 대조와 종료 이유

Gemini는 배경텍스처/구조적엣지아티팩트를원인가설로제시하고마스크의-inf제거실험을권했다. 사용자가라벨모호성을다시확인하라는항목도반환했다. 하지만전송자료에는사진이없으므로시각적원인확정근거가없다. 기존정상라벨을변경하거나완료라벨을재요청하지않았다.

같은logits에서제외마스크만제거하면최댓값을고르는집합이커지므로최대점수는낮아질수없다. 따라서그조작만으로FP5→0을기대하는것은코드와맞지않는다. 기존padding자료의5오탐peak사진점유율도모두100%임을원본해시와함께확인했다. 새모델추론/학습은하지않았다. Gemini는요청한짧은근거ID대신자료경로를인용했으며이는로컬대조에서해당ID로매핑했다.

실험을자동선택하지않고명시적stop으로종료했다. 다음최소진단은기존저장토큰의5오탐peak와대응정상토큰기여도를비교해실제차이가있는지확인하는것이다. 진단이특정변수의가설을지지할때만단일ablation을설계한다. 이후실험기준은동일22정상오탐감소/4결함및4사람점새누락0. 이내용은제안/판정기준이며이번에실행한성능실험이아니다. decision.json과evidence-comparison.json에쟁점/부족근거/다음최소진단을저장했다.

토론종료는실험선택성공이나성능개선이아니다. 이번요청범위의연동검증은완료했고새모델실험은시작하지않았다.

## 발견한 코드 결함과 검증

실행전기존compare분기에서모델human_confirmation이있으면사용자의명시적stop도무시하고다시사람대기로진입하는문제를발견했다. stop을먼저처리하도록2줄추가했다. 실제응답에도human_confirmation이있었으나stop재개후정상종료해수정을실제로검증했다.

관련27개테스트통과: artifacts/cross-review-live-r2-20261019/tests.log. maxcalls/반복종료/사람대기·재개/cache/오류/예산/모델별thinking옵션은API mock과실제LangGraph로검사했다. 반복주장종료·2차호출·quota/auth오류등모든분기를이번실호출로실행한것은아니다. 실호출은성공응답→근거대조중단→명시적종료경로1개와해당완료캐시를검증했다.

## 변경 파일 · 리스크 · 롤백

- card_condition/cross_review.py: 명시적stop을모델사람확인요청보다우선처리.
- tests/test_cross_review.py: 위회귀검사추가.
- data/cross-review-key.json: 전용키r2로교체,0600/Git제외. 키전문은문서나로그에없다.
- artifacts/cross-review-20261019/local-config.json, key-registration.json: 새키확인바인딩·등록상태정정.
- artifacts/cross-review-live-r2-20261019/: 같은packet/실행config/1회HTTP상한runner/실응답/대조결정/DB/테스트·검증/키교체화면.
- 본문서 및 CROSS_REVIEW_20261019.md: 결과기록.

새키기존권한/프로젝트/무료정책은변경하지않았다. 키는로컬평문파일이므로0600유지필요. Gemini의가설은검증되지않았고카드모델성능은미측정이다. 원본정답/사진/모델/수집코드는수정하지않았으므로성능비교HTML대상은없다.

코드롤백은.backups/cross-review-r2-20261019/의cross_review.py·test_cross_review.py복원. 인증롤백으로폐기된노출키를복구하지않는다. API사용중지는전용키파일/환경변수사용해제와실행중지로한다. 실제요청journal/DB/영수증은보존해야재실행중복을막을수있다. 새키의추가폐기는별도사용자결정이며자동수행하지않는다.
