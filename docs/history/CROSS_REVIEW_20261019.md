# 정체 시 수동 교차 검토

구현 범위: 증거 검증 → Gemini 독립 제안 → Codex/사람의 근거 대조(interrupt) → 필요 시 두 번째 Gemini → 실험 하나 선택 또는 종료. 기존 수집·학습·평가·ReviewStore는 그대로다. 토론 합의는 성능 개선이 아니다.

## 프로젝트 조사와 선택

- `card_condition/review.py`의 atomic_write/ReviewStore는 사람 라벨 원장용이다. 이 기능을 복제하거나 교체하지 않는다. 교차 검토 상태는 LangGraph의 기존 SQLite saver를 사용한다. 같은 DB의 작은 요청 journal은 API 전송과 체크포인트 사이의 중복 호출 방지에만 필요하다.
- 소비 프로젝트 `pokecollector/providers.py:262`의 GeminiProvider는 이미지 판독·재시도·fallback을 포함하므로 이번 요구와 맞지 않는다. 전용 `POKEMON_CARD_CONDITION_GEMINI_API_KEY` 환경변수만 사용하고, 독립 SDK 호출에는 재시도/모델 fallback을 두지 않는다. 운영 코드는 수정하지 않았다.
- `OBSERVATION_CONSENSUS_20261011.md`와 소비 프로젝트 TODO의 평가·사람 정답 원칙을 적용했다. 완료 라벨을 재요청하거나 정상으로 추정하지 않는다.
- 선택 의존성 `[cross-review]`와 별도 CLI로 분리했다. 기존 CLI를 import할 때 LangGraph를 요구하지 않는다.

## 공식 자료 확인 (2026-10-19)

[가격표](https://ai.google.dev/gemini-api/docs/pricing#gemini-2.5-flash-lite)의 Gemini 2.5 Flash-Lite 표준 텍스트 입력/출력 무료 제공을 확인했다. 기본 모델은 설정 파일의 `gemini-2.5-flash-lite`. 검토된 대안 `gemini-2.5-flash`만 수동 설정 가능하며 자동 fallback은 없다. 모델 허용 목록은 무료 모델 전체 목록이 아니며, 다른 모델은 무료 조건과 thinking 옵션을 다시 검토해야 한다.

[공식 SDK](https://ai.google.dev/gemini-api/docs/libraries)는 `google-genai`. [현재 한도](https://ai.google.dev/gemini-api/docs/rate-limits)는 AI Studio에서 해당 프로젝트 기준으로 확인한다. RPM/TPM/RPD를 고정값으로 넣지 않았다. 무료 tier의 제출 내용은 제품 개선에 사용될 수 있으므로 준비한 요약/코드 일부만 검토 후 전달한다.

[LangGraph interrupt](https://docs.langchain.com/oss/python/langgraph/interrupts)는 재개 시 노드를 다시 시작한다. 따라서 외부 호출 노드와 대조/사람 입력 노드를 분리했다. 현재 Codex 에이전트가 그래프 안에서 자동 실행되는 구조가 아니다.

## 실행

```sh
.venv/bin/pip install -e '.[cross-review]'
# 기본은 전송하지 않는 미리보기. 모델·자료 전체·예산·최대 호출 수를 표시한다.
.venv/bin/python -m card_condition.cross_review artifacts/cross-review-20261019/packet.json --config examples/cross-review/config.json
```

현재 사용자가 Free tier 미확인으로 실제 호출 보류를 선택했다. config의 `free_tier_verification`은 null로 유지했다. 실제 생성 요청은 0회이며 실사용 토큰 측정값은 없다. 테스트의 usage 숫자는 mock 데이터다.

나중에 사용자가 AI Studio에서 **키 소속 프로젝트**의 Free tier와 모델 사용 가능 여부를 확인한 뒤, 로컬 config 사본에 아래 정보를 직접 기록한다. 이 기록은 수동 확인 증거이며 프로그램이 Google의 과금 상태를 조회했다는 뜻이 아니다. 실행 전마다 다시 확인한다.

```json
{"free_tier_verification": {
  "tier": "Free", "project_id": "확인한 프로젝트 ID",
  "verified_at": "실제 확인 시각", "evidence": "AI Studio 표시 및 확인 근거",
  "key_sha256": "해당 환경변수 키의 로컬 SHA256"
}}
```

키를 코드·인자·대화·파일에 넣지 않는다. zsh에서 숨김 입력:

```sh
read -rs 'POKEMON_CARD_CONDITION_GEMINI_API_KEY?Gemini API key: '; export POKEMON_CARD_CONDITION_GEMINI_API_KEY
```

`key_sha256`는 로컬 Python의 `hashlib.sha256(os.environ['POKEMON_CARD_CONDITION_GEMINI_API_KEY'].encode()).hexdigest()`로 config에 기록할 수 있다. 키 자체를 출력하지 않는다. 이 바인딩은 확인한 키와 실행 키가 바뀌는 실수를 막으며 프로젝트 소속을 독립 증명하지는 않는다.

검증 후 동일 명령에 `--execute`를 추가하면 수동 실행한다. 완료 상태는 동일 명령으로 조회된다. 근거 대조가 필요한 경우 응답의 `pending`을 보고 별도 decision JSON을 작성한 뒤 `--execute --decision <파일>`로 재개한다. 입력 packet/config가 달라지면 새 run이다. 중간 수정으로 재개하지 않는다.

```json
{"action":"second", "rationale":"근거 대조 결과와 미해결 쟁점",
 "evidence_ids":["code","errors"], "new_question":"기존 제안으로 설명되지 않는 구체적 반증 질문"}
```

- `select`: 응답의 가장 작은 실험 하나 및 성공/실패 기준이 모두 있어야 선택된다. **선택은 실험 실행이 아니다.** Codex가 별도로 승인된 실험을 구현·검증한다.
- `second`: 근거 ID·새 질문이 있어야 하며 최대 2회, 남은 예산 범위에서만 호출한다.
- `wait`: 추가 사람 판단/자료가 필요하면 별도 interrupt. `{"answer":"사용자가 실제 답한 내용"}`으로 기록·종료하며 API는 다시 호출하지 않는다. 라벨 원장은 자동 수정하지 않는다.
- `stop`: 쟁점·응답·비교 근거를 저장하고 종료한다. 불합의도 정상 종료다.
- 새 가설/근거가 없는 반복은 동일 hypothesis_id/cause/evidence의 정규화 비교로 종료한다. 의미가 같은 문장의 표현 변경까지 자동 판별하지 않으므로 검토자가 `stop`으로 종료한다.

## 예산·중복·재실행 계약

- 검토 응답은 8개 문자열(원인 ID/원인/증거/반대 증거/최소 실험/성공/실패 기준/사람 확인)으로 검증한다. 예산·오류 종료 시에도 원응답과 journal이 남는다.
- 입력은 24KB 이내 명시적 증거 packet. 전체 저장소/대화/사진/장문 로그를 자동 수집하지 않는다. 실제 프로젝트 예시는 과거 같은 26구간 결과와 코드 한 부분만 담았으며 새 성능 평가가 아니다.
- 캐시는 증거+대조 질문 해시, 모델, 프롬프트 버전, 생성 설정에 결합된다. mock과 live는 분리한다. 완료 응답은 재사용하고 `pending` 요청은 결과 불명으로 종료한다. SDK retry=1(총 시도 1회), 다른 키/프로젝트 우회 없음.
- UTF-8 바이트 수+256을 텍스트 입력의 보수적 **예약량**으로 사용한다. 실제 토큰 수/절감률이 아니다. 출력은 max_output_tokens, thinking_budget=0. 누적 예약량과 반환 usage를 함께 확인한다. usage가 없으면 JSON null로 남기며 재개 예산에는 예약량을 유지한다.
- `seconds`는 최초 실행부터의 wall-clock 제한으로 사람 대기 시간도 포함한다. API timeout은 남은 시간. 전송된 요청은 timeout 뒤 서버에서 이미 처리됐을 수도 있으므로 결과 불명 요청을 재시도하지 않는다.
- SQLite journal은 시도 수·usage metadata를 저장한다. 원문 예외는 키/요청 본문 유출 방지를 위해 저장하지 않는다. 429/401/403 및 기타 요청 오류는 즉시 종료한다.
- 같은 주제의 새 토론은 `previous_experiment_result: {"run":"이전 run ID", "evidence_ids":["새 결과 ID"]}`가 있어야 한다. 자동 새 토론/학습은 없다. 결과의 진위는 검토자가 원자료로 확인한다.
- 거절 가설은 안정적인 ID로 기록하고 `reopen_evidence`에 과거 실패 증거와 다른 ID를 명시해야 다시 선택된다. 근거의 의미적 타당성은 Codex/사람 대조 단계 책임이다.
- 로컬 DB 파일 잠금으로 동시 CLI 실행을 막는다. 다른 프로그램/복제 DB에서의 프로젝트 전체 사용량은 제어하지 않는다. recursion_limit=10은 추가 안전장치다.

## 변경 파일·검증·롤백

- `card_condition/cross_review.py`: 수동 CLI, SDK 호출, LangGraph 분기·중단·재개, 요청 journal/cache.
- `tests/test_cross_review.py`: mock API와 실제 LangGraph/SQLite로 호출·재개·캐시·오류·예산·SDK 설정 검증.
- `pyproject.toml`: optional dependencies, 별도 진입점. 기본 모델 학습 의존성은 유지.
- `examples/cross-review/config.json`, `decision.json`: 호출 차단 기본 설정과 명시적인 예시.
- 본 문서 및 `artifacts/cross-review-20261019/`: 이전 기록 기반 packet/미리보기/source-check/실행 로그. 사람 정답/원본 사진/모델 수정 없음.

검증 환경: langgraph 1.2.16, langgraph-checkpoint-sqlite 3.1.2, google-genai 1.75.0. `pip check` 통과. 실제 SDK 객체 설정을 mock client로 검사했으며 네트워크 응답은 검증하지 않았다. 최종 테스트 수/결과는 같은 디렉토리의 tests.log와 verification.json 참고.

리스크: 무료 상태 확인은 수동 증거에 의존한다. 모델/무료 조건이 변경될 수 있다. timeout/프로세스 종료 시 요청의 서버 처리 여부는 미확인으로 남긴다. SQLite에는 전달한 코드/제안이 평문 저장된다. 의미가 같은 가설의 이름 바꾸기를 코드만으로 완벽히 막지는 않는다.

롤백: 이후 편집이 없다면 `.backups/cross-review-20261019/pyproject.toml`을 복원하고 위 신규 소스·테스트·예시·문서를 제거한다. DB/실험 기록은 보존 가능하며 제거하면 중복 호출 방지 이력도 사라진다. optional 패키지는 기존 환경과 공유하는 의존성까지 일괄 삭제하지 않는다. 이 체크아웃에는 .git이 없어 Git rollback은 제안하지 않는다.

## 프로젝트 분리 정정 — 2026-10-19

이전 후속 작업에서 PokeCollector 비밀 설정을 연결한 것은 잘못된 연결이었다. 사용자 지시에 따라 참조를 제거했다. 이 프로젝트는 `POKEMON_CARD_CONDITION_GEMINI_API_KEY` 환경변수만 읽는다. 일반 `GEMINI_API_KEY`와 타 프로젝트 비밀 파일을 읽지 않는다. 기존 PokeCollector 키/파일은 수정하지 않았다.

`artifacts/cross-review-20261019/local-config.json`은 키/외부 비밀 파일 경로가 없는 독립 설정으로 정정했다. 현재 이 프로젝트 키 등록은 미완료이며 Free tier도 미확인이다. 실제 API 호출은 0회다. 이 프로젝트용으로 사용할 키는 사용자가 전용 환경변수에 직접 입력해야 한다.

변경 파일: cross_review.py(전용 환경변수만 읽기), test_cross_review.py(일반 키 무시/외부 파일 미접근 검사), local-config.json(타 프로젝트 경로 제거), key-registration.json(미등록 상태 정정), 본 문서. 24개 검토 테스트는 key-isolation-tests.log 참고. 과거 key-registration-tests.log는 잘못 연결했던 시점의 역사 기록이며 현재 등록 상태의 증거가 아니다.

리스크: 사용자가 전용 환경변수에 어느 프로젝트 키를 입력했는지는 별도 AI Studio 확인이 필요하다. 롤백 시 타 프로젝트 비밀 참조를 복원하지 않으며, 교차 검토 기능을 사용 중지하고 독립 키 설정만 해제한다.

## 독립 키 등록 방식 — 2026-10-19 재요청

사용자가 이 프로젝트 전용 키 등록을 요청하여 독립 저장 경로 `data/cross-review-key.json`을 추가했다. 이 프로젝트 전용 환경변수 `POKEMON_CARD_CONDITION_GEMINI_API_KEY`가 있으면 우선하고, 없으면 이 파일의 api_key만 읽는다. 일반 GEMINI_API_KEY와 임의 api_key_file 설정은 사용하지 않는다. 이전의 ‘환경변수만 사용’ 설명은 이 절의 독립 로컬 파일 지원으로 갱신한다.

등록 시 macOS 숨김 입력 창에서 사용자가 직접 입력한다. 키는 로그·프롬프트·config에 넣지 않고 임시 파일0600→atomic replace로 저장한다. data/는 기존 .gitignore 대상이다. PokeCollector 키/파일은 접근하지 않는다. 키 등록은 Free tier 확인이나 서버 인증 성공의 증거가 아니며 실제 호출 차단은 유지한다.

변경: cross_review.py(전용 로컬 키 읽기), tests/test_cross_review.py(테스트 키 경로 격리 및 환경변수 우선 검증), 본 문서, 독립 비밀 파일(입력 완료 시 생성). 25개 테스트 통과: dedicated-key-tests.log. 키가 평문으로 로컬 저장되므로 파일0600 권한을 유지한다. 롤백은 전용 파일 삭제와 `.backups/cross-review-dedicated-key-20261019/cross_review.py` 복원이다. 기존 PokeCollector 비밀 설정은 롤백 대상이 아니다.

## 전용 프로젝트·키 발급 완료 — 2026-10-19

사용자가 새 Google API 프로젝트 생성 및 최종 전용 키 발급·로컬 저장을 명시적으로 승인했다. AI Studio에서 `pokemon-card-condition` 프로젝트(`gen-lang-client-0184747717`, 번호257053724930)를 새로 만들고 `pokemon-card-condition-cross-review` 키를 발급했다. PokeCollector의 프로젝트·키와 별개다.

새 키는 data/cross-review-key.json에0600 권한으로 저장했고 실제 런타임의 읽기 결과가 저장한 키와 같은지 값 출력 없이 확인했다. 환경변수가 전용 파일보다 우선하는 기존 계약은 유지한다. 키 전문은 로그/대화/config에 출력하지 않았다.

동일 키 목록에서 새 프로젝트 및 키의 `무료 등급` 표시를 확인했다. local-config.json에 해당 프로젝트 ID·확인 시각·화면 근거·키SHA 바인딩을 기록했다. `key-registration.json`이 최신 상태다. 이전 ‘미등록/무료 미확인’ 기록은 발급 전 이력이다.

키 등록 수용기준 3/3 완료(독립 프로젝트·키 발급/전용 로컬 저장/무료등급 및 권한 확인). 관련25테스트 통과. 이번 등록 단계에서 실제 Gemini 생성 요청0회·서버 인증 유효성 미검증·실사용량 미측정이며 모델 성능 개선 근거도 없다. 사용자가 실행할 때 local-config.json으로 수동 실행하며 모델/자료/호출상한을 먼저 확인한다.

등록 영수증·local-config의 확인 메타데이터·본 문서가 추가 갱신됐다. 로컬 롤백은 전용 키 파일 삭제와 Free tier 확인 설정 해제다. 클라우드 키 철회/프로젝트 삭제는 별도 Google 작업이므로 자동 수행하지 않는다. 무료등급·한도는 이후 변경될 수 있어 실행 전 AI Studio 확인이 필요하다.

## 첫 실호출 — 2026-10-19

사용자 승인으로 전용 키의 실제 요청1회를 실행했지만 HTTP404로 실패했다. usage metadata가 없어 사용토큰은미확인(null). 같은 실행 재진입으로 추가호출0 및 checkpoint 오류종료를 확인했다. 정상응답의 실대조/재개는미검증이다. 신규 프로젝트의2.5접근제한 공식문서를 확인해 기본 모델을3.5 Flash-Lite/minimal thinking으로 정정했으나 추가실호출은0회다. 상세 결과/변경/리스크/롤백은 LIVE_CROSS_REVIEW_20261019.md. 이전의 모델2.5/항상thinking0/실요청0 설명은 당시 이력이며 최신 결과는 이절을 따른다. 최신mock검증26개통과.

## 교체 키 실연동 성공 — 2026-10-19

사용자가r2키최종발급/이전노출키삭제를직접완료했다. 동일packet을3.5 Flash-Lite에추가1회전송해HTTP200/실제입력1482·출력271·합계1753토큰을받았다(thinking metadata는null). 실제LangGraph compare interrupt→조회→stop재개→unresolved/END→종료조회/완료응답캐시재사용에서추가요청0을확인했다. 이전404포함누적요청2회이며이전토큰은미확인이므로누적실사용토큰은미확정이다. 명시적stop이모델human_confirmation보다우선하도록수정하고27테스트통과. 상세변경·쟁점·리스크·롤백: LIVE_CROSS_REVIEW_R2_20261019.md. 최신전용키/무료확인바인딩은local-config.json, 최신실검증은artifacts/cross-review-live-r2-20261019/verification.json. 모델성능개선주장없음.
