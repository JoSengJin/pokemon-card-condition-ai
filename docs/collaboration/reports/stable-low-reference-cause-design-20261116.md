개발 진척률 **78/100 유지** · 동결 근거38개 감사와 단일 조건부 설계 완료 · 신규 검증 미실행.

# 안정된 낮은 점수 참조: 혼입 원인 감사와 다음 검증 설계

## 1. 결론

저장된 선택/채점/정답 연결에서 불일치는 발견하지 않았다. **삭제해도 유지되는 점수 묶음은 정상 참조를 보증하지 않는다.** 혼입12곳은 모두 기존 B0 음성 오류에 포함되며 10사진의 안정된 L에 들어 있다. 혼합118장 중 거부89장은 최초 사유 기준 지지수63/삭제 불안정16/낮은 묶음 최고점10으로 설명된다. 조건을 완화한 가상 성능은 계산하지 않았다.

혼입12곳 중 이전 라벨과 현재 라벨이 일치하는 곳이10곳, 변경 이력이 있는 곳이2곳이다. 변경 이력만으로 전체 혼입을 설명하는 주장은 성립하지 않는다. 그러나 두 버전 일치는 독립 사람 재확인도, 물리적 결함의 증명도 아니다. **관찰조건/라벨 의미 차이와 모델 점수 표현 오류는 현재 패킷으로 식별 불가**다. 다음 검증은 이 식별 조건을 확인하는 출처 대조 하나로 한정하되, 기존 원문104곳은 기본 저장소에서 연결했지만 별도 독립 판정의 동일 조건·시점·비노출 요건을 확보하지 못해 `not_executable_missing_evidence`를 유지한다. 유효한 무인 검증을 확보했다고 주장하지 않는다.

## 2. 범위·근거·방법

- 기준 HEAD: `3cbf778e6ebb8f237684989177896f4367ebd140`, 실제 착수 HEAD 일치. 기본 checkout 기존 미추적 `.claude/` 보존. 별도 D-LOC checkout 보존, 정리/통합/push 없음.
- 입력 루트: 기본 checkout의 `artifacts/stable-low-reference-pair-handoff-20261116/`. 아래 E/B 경로는 그 안 `evidence/artifacts/`를 기준으로 한다. 소스 원본 경로와 packet_path를 혼동하지 않는다. 새 worktree에 artifacts/가상환경을 복사·symlink하지 않았다.
- **E** = `experiments/20261116T131107-9c2af49d/`, **B** = `experiments/20261108T215307-941b3aaa/`.
- manifest 파일38개에 대해 `hashlib.sha256(packet_path.read_bytes()) == sha256`를 가장 먼저 검사: **38/38 일치, 누락0/불일치0**. manifest 자체 SHA-256은 `15bab28bf0d5f19b02133836dccb5c22e20070a3edd317d9634666b76518447c`. 분석 재실행·복구 없음.
- 표는 원본 JSON 덤프가 아니라 요청한 추적·집계 파생표다. 원본 라벨/점수 열·사진·로컬 JSON·홈 절대경로는 커밋하지 않는다. 순위/간격/범위는 저장값 검산이며 새 선택/예측이 아니다.
- 표의 혼입은 기존 target1과 봉인 reference_rows의 교집합이라는 뜻이다. 관찰제한을 실제 손상이라고 다시 해석하지 않는다. 같은 SHA/구역이 없는 A 기록을 다른 사례에서 빌려오지 않는다.

### 정확한 연결과 봉인 검사

| 검사 | 이번 실제 확인 |
|---|---|
| scored-rows ↔ B rows/scores | `(id,image_sha256)` 1776개 유일 연결, score/target/group 정확히 일치 |
| scored-rows ↔ sealed-references | opaque row와 photo, reference_selected·accepted 일치; fold는 group별 folds.json과 일치 |
| scored-photos ↔ sealed-references | photo204개, accepted/reason/m_hat 일치, 참조 수·혼입 수 일치 |
| candidate_low/high_rows | 사진별 기존 row의 서로 겹치지 않는 합집합, 새로운 분할 생성 없음 |
| E/reference.json ↔ B | rows 및 before_scores 전체 원문 값 일치 |
| reference-seal | 봉인 두 파일과 selector snapshot SHA 일치; seal≤verified≤모든 truth read timestamp, truth_allowed=true |
| selection-access | 저장 forbidden_accesses=0, read 경로는 blind input 한 개; 새 blind input 재생 없음 |
| 실제 학습 명부5개 | B component-gradient-rows-fold0~4를 folds와 대조: train/held 1424/352,1419/357,1414/362,1420/356,1427/349; group/photoSHA 교차0 |

이는 저장 기록의 내부 일치와 학습 제외 확인이다. 과거 프로세스를 다시 실행해 재현한 것도, 감사 로그가 기록하지 않은 접근까지 증명한 것도 아니다. snapshot은 텍스트로만 읽었다. Python 표준 라이브러리만으로 연결/개수/교차표/기록값 검산을 했다. 선택기·과거 worker/analyze를 실행하거나 import하지 않았다.

소스 근거: E `code/0-after.py`의 `split/select_photo`는 점수의 유일 최대 간격으로 L/H를 나누고 L≥3·H≥2·max(L)<0.5 뒤 모든 삭제 소속을 검사한다. 삭제 단계에는3/2를 다시 검사하지 않는다. `code/1-after.py`는 선택 결과 봉인 후 scorer를 호출한다. `code/2-after.py`는 봉인 검증 후 정답을 열고 photo 유형/혼입을 채점한다. B `code/0-after.py`의 원문은 이전/수정 라벨1776행의 동일ID, 전체 변경191행, group별 tr/ho 분리와 held 점수 배치를 명시한다. 이번에는 그 코드를 실행하지 않았다.

## 3. 혼입12행 추적표

아래 P번호는 다음 사진표와 결합한다. 모든 행은 그 사진의 **봉인 reference_rows = candidate_low인 L**에 속하며, 삭제 결과는 사진 내 모든 구역을 하나씩 뺀 저장 검사 통과 수/전체다. 순위는 사진 전체 저장 점수 오름차순(1=최저), gap은 기존 L의 최대값과 H의 최소값 차이를 검산한 값이다. gap은 표에9자리로 표시하며 선택/동률 판정에는 반올림값을 쓰지 않았다. 해당12행 점수는 각 사진 안에서 동률이 없음을 최종 검산했다.

라벨 출처는 모두 `B/observations.json`의 같은 `(id,image_sha256)` 행 및 `original_rows`다. **유지**는 두 저장 버전의 일치, **변경**은 기존 변경 이력이며 사람 원문에 대한 독립 확인이 아니다. 최초 동결 패킷에는 A/관찰조건 원문이 미수록이었다. 후속 탐색에서12행 모두 기존 판정 원문과 정확히 연결했으며, 아래 출처표에 반영했다. 독립 판정 여부와 실제 관찰조건은 별도 미확인이다.

|구역ID|opaque rowID|사진|fold|순위/구역수|L/H|최대 gap|삭제 안정|라벨 이력|
|---|---|---|---:|---:|---:|---:|---:|---|
|`ebay-pair-ef6332f853348b/back/surface/middle_left`|`2bbc3737e4340ebfe2b46f115ffa4c29759e356535e8ff9516ac2c0f5599a3df`|P01|0|5/9|6/3|0.217956960|9/9|유지|
|`ebay-pair-ef6332f853348b/back/surface/center`|`27df3872ca3c747bc016dc6bb2b8ece8ee99316f746f6911c3d705ebebf0c4ed`|P01|0|1/9|6/3|0.217956960|9/9|유지|
|`ebay-pair-9eacfb8240a175/back/surface/upper_center`|`426c279803a42bc7fe832f79fdbc8e95380551e61b991a4a5327ed185090929b`|P02|3|3/8|5/3|0.316896766|8/8|유지|
|`ebay-pair-c5713f37809d71/back/surface/lower_left`|`9f6a305ac5614521c589307a812cee44251b11aee7bfe94bf7213dd1359887bc`|P03|3|5/9|5/4|0.265020669|9/9|유지|
|`ebay-pair-f9fbd5669f2646/back/surface/upper_left`|`45af1910d5ddd575d600b77862847471def0c5cec3138d3e49b613f4087e7853`|P04|0|2/9|7/2|0.161965191|9/9|유지|
|`ebay-pair-f9fbd5669f2646/back/surface/lower_right`|`420bdbf8274c094abc81df03090f99b47c6ce3f2756778b09a1d9d78f68965b6`|P04|0|7/9|7/2|0.161965191|9/9|유지|
|`ebay-pair-0bf24b72066933/back/surface/center`|`60cc9903ff5e253385f5f3a87925f8ac7f63f41aeef9b3c5475657aab60e4870`|P05|1|6/9|7/2|0.314254969|9/9|유지|
|`ebay-pair-8f73d488e2832d/back/surface/middle_left`|`91a8fe5ec57cde50859064acd73c9a3ce0ab5800b2aed43efed57a07728a34a7`|P06|3|6/9|6/3|0.247012526|9/9|변경|
|`ebay-pair-3b3a43b176da9f/back/surface/lower_left`|`764507a85e0fce4d22a8f9f99a5099fdf54934d20b06b44ba8c2cb9bd4a48059`|P07|2|5/9|6/3|0.319058061|9/9|유지|
|`ebay-pair-858f5a4f342cec/back/surface/upper_center`|`11f5123e3553abe1121405c460a495bfe9245ea2e96477107c46e05d30be4f32`|P08|1|3/9|7/2|0.227412686|9/9|유지|
|`ebay-pair-b26fe718a8a0ff/back/surface/upper_left`|`08fc9ae4c3bcb705da55b6f9e6f84be84520bb08d45d6da8cef56a5f737e2fb7`|P09|4|4/8|5/3|0.129909083|8/8|유지|
|`ebay-pair-8b712018d115e4/back/surface/middle_right`|`6cffbb41352a085002b9c622586ea6bca6a662485e6b2545100d9631a30deb69`|P10|1|5/8|5/3|0.430053949|8/8|변경|

### 사진SHA·선택 묶음·정확한 봉인 연결

L 목록은 아래 group의 `back/surface/<area>`로 펼친 정확한 구역 목록이다. opaque row는 E/scored-rows.json의 `(id,image_sha256)`로 연결한다. H는 봉인 high_rows에 그대로 있으며 새로 계산하지 않았다. 같은 사진 안 선택 대조군은 아래47곳이다.

|사진|group|image_sha256|봉인 photo 코드|L의 area 목록|혼입/선택 대조군|
|---|---|---|---|---|---:|
|P01|`ebay-pair-ef6332f853348b`|`4ea344a2290d2c6d9079f33c54ca4426c1033fd3e7770a4894631473a136445c`|`1504a68f1336ea8d9cc6104b3faf9ac8059820ede3aa6daa27018998a124643c`|center,lower_center,lower_left,lower_right,middle_left,middle_right|2/4|
|P02|`ebay-pair-9eacfb8240a175`|`b8b0d95c23c4bd445e3ba79c4400ca3050683db14c68ac9d88805fe3ebc67a84`|`22916ad71878101ded47f10d39b901dfb7114dc3050657475468cecd2c838a4f`|lower_center,lower_right,middle_left,upper_center,upper_left|1/4|
|P03|`ebay-pair-c5713f37809d71`|`f2a6f6a464acc67a36c1f6a151e85b3a4cc59a8765579113ab004b7e3b6f7b12`|`4a4864844380dec4bcfe07f6912f1ecb701754209cdabd55755aa72cb19cfa7c`|lower_left,lower_right,middle_left,upper_left,upper_right|1/4|
|P04|`ebay-pair-f9fbd5669f2646`|`3d47a0eb728b737c69fea78d72c5780e230812f5c4595c91da50c4f3b47e3c98`|`4da4735f0d826bfacd9f902beded08f33ef02c0faaddda41b41b86072bd2524f`|center,lower_right,middle_left,middle_right,upper_center,upper_left,upper_right|2/5|
|P05|`ebay-pair-0bf24b72066933`|`f34f4e49e0e0ae7013e824185766fe894609cbf1721e1aaa91d5facdeb4d1cc2`|`6222aaf3493bfc2cfca76a259c6055fb3f31b79c370f0622da15849f536a897f`|center,lower_center,lower_left,middle_left,upper_center,upper_left,upper_right|1/6|
|P06|`ebay-pair-8f73d488e2832d`|`a067dfb2df9b50f02aaba4810e6ed76ee09b15caf85cf85ac633f00c89decf46`|`664ad4aae755be8e991991ea58886f1e9530bd447e8653e208a819f71671b09a`|lower_center,lower_left,lower_right,middle_left,upper_center,upper_left|1/5|
|P07|`ebay-pair-3b3a43b176da9f`|`45f3ee3cb639a8f04e95075f5139c9a424127bd86dd71e4f3e793f1932619422`|`7f1742cb97dbc6068fbfd4d46cfb883fe193e9c6cf450d94b84f35c9dbff3276`|center,lower_center,lower_left,lower_right,upper_center,upper_left|1/5|
|P08|`ebay-pair-858f5a4f342cec`|`dbed3ad3f1cd49b3c857f3822218141f17c5ae0c8b27fe7ea4da12b4d28bd50c`|`82c9b04e8f070c2525ac3387e0523c8da34a406e6f375d84769085f8f53525d6`|lower_center,lower_right,middle_left,middle_right,upper_center,upper_left,upper_right|1/6|
|P09|`ebay-pair-b26fe718a8a0ff`|`b22a158b61dcae8ecd41bfee135f092f654280030cfca716875d0adeddbed674`|`ea75ef5d5264c044190eaaa85a75386b40470bc569cceea1ae04bf9d0aee9f97`|lower_center,lower_right,middle_right,upper_center,upper_left|1/4|
|P10|`ebay-pair-8b712018d115e4`|`df85ad1dd0cd98a81091b314225f3e54ee897a1f6fca7e40c3fe78fee279f125`|`ed1a2014eeb1d8885fc6b05d142fad7e50d3b30b8812f6337629eb3932339b01`|lower_center,lower_left,middle_left,middle_right,upper_center|1/4|

### 추적 해석

- 12곳 모두 B0 저장 score<0.5인 FN57의 부분집합이다. 안정성 통과는 오류를 새로 만든 것이 아니라 기존 낮은 점수 오류를 정상 참조로 받아들인 연결이다. 새 FN/FP 판정 성능을 만든 것이 아니다.
- P01 center는 사진 전체 점수1위(최저)인데 같은 L에 기존 정상 대조4곳이 있다. 따라서 “정답상 모든 결함이 정상보다 높은 순서를 유지하고 사진 공통 이동만 있다”는 강한 설명에는 이미 반례가 있다. 새 순위 성능 계산을 실행할 이유가 없다. 이것만으로 라벨 오류와 모델 표현 오류를 구별하지는 못한다.
- 기존 라벨 유지10곳이 있으므로 최근 변경2곳을 제외하면 혼입 원인이 사라진다는 설명은 불충분하다. 반대로 유지10곳을 독립 정답 확정으로 부를 수 없다.
- 삭제 안정성은 모두 통과했고 gap은 약0.130~0.430에 걸친다. “간격이 더 크면 순도 보장”을 이 표로 주장하거나 간격 임계 재탐색을 하지 않는다.

## 4. 대조군과 선택 편향

|집합|구역/사진|저장 점수 범위(집계·반올림)|이전→현재 라벨 이력 집계|의미|
|---|---:|---|---|---|
|혼입|12/10|0.094583~0.440078|유지10, 변경2|기존 FN57 중 안정 L에 선택된 부분|
|동일 혼입사진의 선택 target0|47/10|0.031724~0.478330|유지47|우선 대조군: photo/fold/선택 상태 공유|
|전체 혼합사진 선택 target0|151/29|0.017928~0.496124|유지151|위47 포함, 별개 독립151개가 아님|
|정상 전용사진 선택 target0|183/29|0.029780~0.454576|유지183|사진 유형이 달라 혼입 순도를 희석하는 대조로 사용 금지|
|B0 나머지 FN|45/36|0.051901~0.496486|유지27, 변경18|혼합41구역/결함 전용4구역; 적용사진5구역·거부사진40구역|

선택 target0 총334 = 혼합151 + 정상 전용183. 같은 혼입사진은 선택59 = 혼입12 + target0 47. FN57 = 혼입12 + 나머지45. 이 분모는 서로 대체하지 않는다. 12/163의 혼합 참조 혼입을12/346으로만 보고 정상 전용을 섞으면 사용 대상의 위험을 축소한다.

모두 B에서 정확한 ID/SHA로 연결되지만, target0 유지 이력은 관찰조건/사람 원문 출처가 동질임을 보증하지 않는다. target0 대조군에는 이진 라벨로 표시되지 않은 불확실성이 있을 수 있으며 그 유무도 미확인이다. 같은 사진47곳도 구역별 재질·손상·관찰조건은 통제하지 못한다. 기본 저장소 후속 탐색에서는104곳 원문 연결을 확보했지만, 별도 독립 판정/실제 관찰조건 요건은 충족하지 못해 A 일치율이나 새 판정 검증 결과를 만들지 않았다.

점수 범위는 겹치며 범위만으로 분포·오류의 물리적 원인을 설명하지 않는다. 혼입은 “낮은 안정 묶음”에 사후 선택된 FN이고 나머지45는 그 바깥이므로, 이 둘의 변경 비중 차이를 원인 효과로 해석하지 않는다. 183곳은 정답상 정상만 있는 사진에서 선택되어 혼입0이 구조적으로 보장되는 집합이다. 적용률과 정상성/정답 정확도는 다른 양이다. 5fold 모두 혼입이 있어도 fold 효과가 없다는 증명은 아니다.

사진 출처 폴더별 저장 구역수는 다음과 같다. 이 이름은 B의 image 경로 metadata에서만 읽었고 사진은 열지 않았다. **사진 수집 출처와 라벨 판정 출처는 다르다.** 판정 원문은 후속 기본 저장소 탐색에서 연결했으며 아래 별도 출처표에 기록한다. 작성자 독립성/실제 관찰조건은 미확인이고 사진 수집 폴더로 대체하지 않는다.

|사진 수집 폴더|혼입12|같은사진47|혼합151|정상전용183|나머지FN45|
|---|---:|---:|---:|---:|---:|
|`ebay-intake-20261031-y`|1|4|10|30|4|
|`ebay-intake-20261031-z`|2|8|19|25|3|
|`ebay-intake-20261101-aa`|1|5|5|6|9|
|`ebay-intake-20261102-ad`|1|6|28|18|10|
|`ebay-intake-20261102-ae`|0|0|14|28|4|
|`ebay-intake-20261102-af`|2|5|22|14|3|
|`ebay-intake-20261102-ag`|2|4|14|28|5|
|`ebay-intake-20261102-ah`|0|0|16|27|2|
|`ebay-intake-20261102-ai`|3|15|23|7|5|

수집 폴더 구성도 대조군마다 다르다. 예를 들어 ai는 혼입3/12·정상 전용7/183, ad는 혼입1/12·나머지FN10/45다. 소표본·사후 선택 차이여서 특정 수집 조건을 원인으로 확정하지 않는다.

### 기본 저장소 원문 후속 탐색 — 2026-11-16

사용자의 추가 읽기 전용 탐색 승인으로 동결38개 밖의 기존 개발 기록을 따라갔다. **원문이 없는 것이 아니라, 원문은 있으나 이 설계가 요구하는 독립 판정 근거가 확보되지 않은 상태**로 정정한다. 원래 패킷/manifest는 수정·확장하지 않았다. 아래 파일은 기본 checkout 기준의 추가 탐색 근거이며 새 packet_path를 생성하지 않았다.

|집합|동일 구역ID·사진SHA 연결|원문 응답 연결|별도 §93 기록 연결|§97 기록 연결|
|---|---:|---:|---:|---:|
|혼입12|12/12|12/12|0|2|
|같은사진47|47/47|47/47|0|0|
|나머지FN45|45/45|45/45|1|18|

연결 사슬은 E/scored-rows의 `(id,image_sha256,group,area)` → `artifacts/surface-label-audit-20261107/audit.json`의 동일 키 → `original_response.path/line` → 원문 줄의 `group/back`와 구역명이다. `surface-corrected-labels-cv-20261104/rows.json`의 같은 ID·사진SHA·box도 대조했다. **원문 TXT 자체에 사진SHA가 들어 있는 것은 아니며**, 저장된 구역 metadata와 출처 매핑을 거친 연결이다. 원사진 파일을 다시 열거나 해시하지 않았다. 원출처7파일의 현재 SHA는 기존 `surface-label-audit-20261107/preserved-inputs.json` 보존값과 모두 일치했다. 이는 저장 출처 연결 확인이지 새 판정 검증 실행이 아니다.

혼입10곳은 현재 라벨을 만든 원판정 자체에 연결된다. 나머지2곳은 `ebay-pair-8b712018d115e4/back/surface/middle_right`의 z73와 `ebay-pair-8f73d488e2832d/back/surface/middle_left`의 z161이며, `zone-relabel-20261104/answers-61-275.lines`의13·101줄에 원문이 있다. 두 구역의 selection number/이미지 경로/box도 같은 사진SHA의 기존 rows metadata와 연결했다. 이 재판정은 이미 현재 라벨에 반영된 출처여서 새 독립 대조 정답이 아니다. 혼입12와 같은사진47에는 별도 §93 재판정 연결이 없고, 나머지FN45의 `ebay-pair-05704a31e488bb/back/surface/lower_right`1곳에만 §93 기록이 있다. 1곳을104곳의 독립 근거로 확장하지 않는다.

§97은 점수·이전 라벨이 없는 화면에서 답했으나, **대상 선정은 모델 점수 기반**이었다(`docs/collaboration/reports/performance-top3-consensus-20261030.md:748-751`). 점수 기반 선정과 판정 화면의 점수 노출은 다르므로 “점수를 보고 답했다”고 바꾸어 쓰지 않는다. §93도 같은 사람의 반복 판정이며 그 자체로 객관적 독립 정답을 뜻하지 않는다(같은 문서:710-716). 최종 선택/규약 확인은 `surface-protocol-finalization-20261107/effective-decisions.json`에 보존돼 있으나 기존 답의 사용 선택을 확인한 기록이지104곳의 새 독립 판정이 아니다.

기존 감사의 `source_guides`에는 표면 손상·엣지/모서리·반사 제외에 관한 안내 원문이 있다. 이 안내의 존재는 확인됐지만, 모든104곳의 실제 조명/확대/관찰조건·판정 시각·점수 비노출을 독립적으로 증명하지 않는다. 폴더 날짜가 실제 판정 시각이라는 보장도 없다. 확인한 출처 사슬에서 설계 요건을 충족하는 독립 판정을 확보하지 못했다는 뜻이며 저장소 전체에 어떤 기록도 없다는 전역 부재 증명은 아니다.

#### 추가 읽기 전용 확인: 저장 화면과 실제 판정조건의 구분 — 2026-11-16

사용자는 추가 확인 결과를 기존 보고서·task 두 문서에 반영하고 전용 브랜치에 로컬 커밋하는 것만 승인했다. 아래는 앞선 추가 탐색에서 기존 JSON/응답/HTML/문서를 텍스트로 읽은 결과다. Python 표준 라이브러리로 고정104개 키의 기존 필드를 발췌했으며 selector/worker/analyze import·실행, 사진 표시·디코딩·재해시, 새 검증/실험은 하지 않았다. 최초 동결38개와 기존104행 목록을 변경하지 않았다. 이번 문서 반영에서 과거 해시·학습 명부·출처 연결 감사를 재실행했다고 주장하지 않는다.

**확보는 저장 파일이 보여주는 근거의 확보를 뜻한다. 저장 HTML의 안내·표시·초기 상태를 실제 사람이 답할 당시의 전체 관찰조건·노출 이력 확인으로 확대하지 않는다.** 고정104곳 모두 원판정 페이지에 연결되고, 별도 재판정 기록은 §97 20곳과 §93 1곳이다. 여섯 분류는 아래 기존104행 목록의 동일 키를 나눈 것이며 새 대상 선정이나 S/D/U 채점이 아니다.

|고정 집합의 세부 분류|구역수|독립 판정 근거|관찰조건 근거|판정 시점 근거|점수 비노출 근거|
|---|---:|---|---|---|---|
|혼입 중 원판정 유지|10|별도 판정 미확인|저장 화면 확보 / 실제 동일 조건 미확인|개별 응답 시점 미확인|저장 화면 근거 확보 / 당시 전체 노출 이력 미확인|
|혼입 중 §97 반영|2|§97 답은 현재 라벨 출처 자체 / 별도 독립 대조 아님|원판정·재판정 화면 확보 / 실제 동일 조건 미확인|기록 일자와 개별 응답 시점을 구분 / 후자 미확인|재판정 화면 비노출 근거 확보 / 점수 기반 선정은 유지|
|같은사진 선택 target0|47|별도 판정 미확인|저장 화면 확보 / 실제 동일 조건 미확인|개별 응답 시점 미확인|저장 화면 근거 확보 / 당시 전체 노출 이력 미확인|
|나머지 FN 중 §97 반영|18|§97 답은 현재 라벨 출처 자체 / 별도 독립 대조 아님|원판정·재판정 화면 확보 / 실제 동일 조건 미확인|기록 일자와 개별 응답 시점을 구분 / 후자 미확인|재판정 화면 비노출 근거 확보 / 점수 기반 선정은 유지|
|나머지 FN 중 §93 연결|1|별도 반복 판정 확보 / 설계상 독립성 미확인|두 화면 확보 / 실제 동일 조건 미확인|개별 응답 시점 미확인|재판정 화면 비노출 근거 확보 / 당시 전체 노출 이력 미확인|
|나머지 FN의 나머지|26|별도 판정 미확인|저장 화면 확보 / 실제 동일 조건 미확인|개별 응답 시점 미확인|저장 화면 근거 확보 / 당시 전체 노출 이력 미확인|
|합계|104|전체 진입 요건을 입증한 행은 이번 탐색에서도 확보하지 못함|실제 동일 조건 미확인|개별 응답 시점 미확인|저장 화면과 실제 노출 이력은 다른 수준의 근거|

원판정 페이지는 `audit.json`의 각 행 `source_pages`를 따라 다음25개를 읽었다. 경로는 모두 기본 checkout 기준이다. 각 페이지의1~6줄은 표시 CSS,7줄은 안내·article·초기 구역 상태,8~34줄은 입력/결과 복사 script다. 저장 화면에는 점수 표시나 이전 정상/결함의 사전 채움이 없지만, 이 파일이 당시 제공된 버전인지와 다른 화면/이전 기억을 통한 노출까지 입증한 것은 아니다.

|기본 checkout 폴더|확인한 파일(각각 위 줄 범위)|고정104 중 연결 구역수|
|---|---|---:|
|`artifacts/ebay-intake-20261102-ad/`|`surface-pages-1.html`, `surface-pages-2.html`, `surface-pages-3.html`, `surface-pages-4.html`|17|
|`artifacts/ebay-intake-20261102-ae/`|`surface-pages-1.html`, `surface-pages-3.html`, `surface-pages-5.html`|4|
|`artifacts/ebay-intake-20261102-af/`|`surface-pages-2.html`, `surface-pages-3.html`|10|
|`artifacts/ebay-intake-20261102-ag/`|`surface-pages-1.html`, `surface-pages-2.html`, `surface-pages-3.html`, `surface-pages-4.html`|11|
|`artifacts/ebay-intake-20261102-ah/`|`surface-pages-2.html`, `surface-pages-3.html`|2|
|`artifacts/ebay-intake-20261102-ai/`|`surface-pages-1.html`, `surface-pages-2.html`, `surface-pages-3.html`|23|
|`artifacts/surface-back-holdout-20261101/`|`surface-pages-1.html`, `surface-pages-3.html`, `surface-pages-4.html`, `surface-pages-5.html`, `surface-pages-6.html`, `surface-pages-7.html`, `surface-pages-8.html`|37|

§97 확인 대상은 `artifacts/zone-relabel-20261104/zones-{1,2,4,5,6,7,8,9,11,12,13}.html`의11페이지이며 각4줄에 이전 판정·점수 비노출 안내와 대상 article,5~15줄에 입력 script가 있다. 대응하는 고정 키의 번호는 z1,z3,z10,z21,z73,z86,z105,z114,z125,z128,z137,z142,z161,z176,z206,z214,z216,z236,z244,z255다. 선택 번호와 고정 키는 기존104행 표와 `selection.json:1`에 있고, 응답은 `answers-1-60.txt:1,3,10,21` 및 `answers-61-275.lines:13,26,45,54,65,68,77,82,101,116,146,154,156,176,184,195`에 있다. 점수 비노출 저장 화면은 확인했으나, 선정은 모델 점수 기반이라는 기록을 바꾸지 않는다.

§93의1곳은 `ebay-pair-05704a31e488bb/back/surface/lower_right`다. `artifacts/consistency-relabel-20261104/selection.json:1`의 c21에 대응하며 기존 표시 오프셋에 따라 응답 c22를 사용한다. `relabel-2.html:6`에 c22·점수 비노출 안내, `answers.txt:21`에 응답이 있다. `surface-label-audit-20261107/audit.json:20265-20290`은 원판정과 다른 재판정을 병기하고, `surface-protocol-finalization-20261107/effective-decisions.json:14097-14116`은 원판정 유지 선택을 보존한다. 별도 응답의 존재를 독립 정답·라벨 오류 확정으로 바꾸어 읽지 않는다.

저장 안내에도 차이가 있다. 원판정 HTML7줄은 표면 손상을 대상으로 옆면·모서리 백화/반사 등을 제외하지만, 저장된 §97 각4줄과 §93 `relabel-2.html:6`에는 “화이트닝은 정상”이라는 문구가 있다. 이는 **저장 안내문 차이의 근거**이며 실제 사람의 기준 차이나 혼입 원인의 증명이 아니다. 기존 정정·재정정 기록 `docs/collaboration/reports/performance-top3-consensus-20261030.md:753-754`와 규약 확인을 보존하고 과거 원인 미확인 결론을 뒤집지 않는다. 현재 생성 도구의 안내문을 저장 HTML 문구 대신 사용하지 않는다.

시점 관련 `artifacts/surface-label-audit-20261107/report.md:17-20`과 `audit.json:50225-50269`는 폴더 날짜를 검증된 사람 응답 시각으로 두지 않는다. `surface-protocol-finalization-20261107/confirmation.json:3,10-11`의 수신일·규약 상태 확정도 원판정 시각이나 새 독립 판정의 증거가 아니다. 저장 페이지의 CSS/이미지 틀·안내와 실제 확대율·화면·관찰 과정·시각은 별개다.104곳의 실제 동일 관찰조건과 개별 응답 시점은 이번에도 미확인이다.

결론: 저장 화면 근거는 추가했지만 현재 라벨 원출처와 구별되는 독립 판정 및 동일 관찰조건·시점·점수 비노출을 합친 진입 요건은 충족하지 못했다. `not_executable_missing_evidence` / `independent_judgment_and_observation_provenance_unestablished`를 유지한다. 저장 화면 근거를 S/D/U 채점·가설 반증·새 검증 완료로 보고하지 않으며 기준을 완화하지 않는다. 탐색 범위는 이104곳과 위 기존 기록이고 저장소 전체의 독립 자료 부재 증명이 아니다. 새 사람 판정도 “기존 사전 판정” 요건을 소급 충족하지 못하므로 이번 문서 반영을 사람 재요청이나 설계 변경 승인으로 해석하지 않는다.

#### 원출처 파일·SHA-256

|코드|기본 checkout 상대경로|현재 SHA-256(기존 보존값과 일치)|
|---|---|---|
|R1|`artifacts/ebay-intake-20261102-ad/surface-answers.txt`|`5dc776a8fdf3c234a35561684c071449f047aa289a952e069e4efc9bcbb66814`|
|R2|`artifacts/ebay-intake-20261102-ae/surface-answers.txt`|`ef06cf4c16172eb93e4869b6be920f518963ff90c4f3f5e7cec2ce128b6742a1`|
|R3|`artifacts/ebay-intake-20261102-af/surface-answers.txt`|`ce283fb4026e5dce514dae567983c20c5cf747968688a62fbea1a0add179fa65`|
|R4|`artifacts/ebay-intake-20261102-ag/surface-answers.txt`|`7dfde66d0a038ad3b3c75052a4732c3b0611e5fd75ec7913790387a7f2706a00`|
|R5|`artifacts/ebay-intake-20261102-ah/surface-answers.txt`|`5963dd5e7f05968b33ba19ba3d5ae05119e26f313cd26162fc3e9062d72148b2`|
|R6|`artifacts/ebay-intake-20261102-ai/surface-answers.txt`|`850287289cd83d2ba81c50033c02bacd1c207e8120d5eb2bd5c8d25f05f6f9b5`|
|R7|`artifacts/surface-back-holdout-20261101/surface-answers.txt`|`747d32ff6d3ef57868c398b28a84f86f72686edde10176a4bc64eedb80448715`|

추가 탐색의 연결 metadata SHA-256(원문 판정값/사진은 문서에 복제하지 않음):

- `artifacts/surface-label-audit-20261107/audit.json`: `e696e69235a5d554a2f8eaf720a187c828257db4877cb377f1dd024b7f5fe621`
- `artifacts/surface-label-audit-20261107/preserved-inputs.json`: `298babced09c488febd50d06ef0aeccf5978f717240bdd88e84672e9b02392e8`
- `artifacts/surface-protocol-finalization-20261107/effective-decisions.json`: `cbf761d67f0cde64424690fb2715df4846c30fcfbd1a69c2b4c69ebdcc7bc056`
- `artifacts/surface-corrected-labels-cv-20261104/rows.json`: `d23999c3f26f87538b716c225f158513969a9c0f28663287a45cb5b042138b44`
- `artifacts/zone-relabel-20261104/selection.json`: `875ee6d9b3604c2b5109acff03c964a26303d4e7af10ea6896e535e250c34b9a`
- `artifacts/zone-relabel-20261104/answers-61-275.lines`: `e4f1ed68d225fb975e4ddf57afc4f34cf8804af9fec9242d8bfa1b68b2f5a878`

#### 104곳 원문 연결 목록

아래는 원문 라벨값/점수를 옮기지 않은 출처 추적표다. 구역ID에 면·구역이 포함된다. R코드/줄은 위 원출처 TXT의 위치이며, §97은 별도 재판정의 저장 선택 번호다. `—`는 해당 audit 행에 기록이 없다는 뜻이며 정상/독립성 확인을 뜻하지 않는다. §93/§97 존재로 S/D/U를 채점하지 않았다.

|집합|구역ID|image_sha256|원출처/줄|§93 기록|§97 번호|
|---|---|---|---|---|---|
|혼입12|`ebay-pair-ef6332f853348b/back/surface/middle_left`|`4ea344a2290d2c6d9079f33c54ca4426c1033fd3e7770a4894631473a136445c`|R4:1|—|—|
|혼입12|`ebay-pair-ef6332f853348b/back/surface/center`|`4ea344a2290d2c6d9079f33c54ca4426c1033fd3e7770a4894631473a136445c`|R4:1|—|—|
|혼입12|`ebay-pair-9eacfb8240a175/back/surface/upper_center`|`b8b0d95c23c4bd445e3ba79c4400ca3050683db14c68ac9d88805fe3ebc67a84`|R7:25|—|—|
|혼입12|`ebay-pair-c5713f37809d71/back/surface/lower_left`|`f2a6f6a464acc67a36c1f6a151e85b3a4cc59a8765579113ab004b7e3b6f7b12`|R6:15|—|—|
|혼입12|`ebay-pair-f9fbd5669f2646/back/surface/upper_left`|`3d47a0eb728b737c69fea78d72c5780e230812f5c4595c91da50c4f3b47e3c98`|R3:8|—|—|
|혼입12|`ebay-pair-f9fbd5669f2646/back/surface/lower_right`|`3d47a0eb728b737c69fea78d72c5780e230812f5c4595c91da50c4f3b47e3c98`|R3:8|—|—|
|혼입12|`ebay-pair-0bf24b72066933/back/surface/center`|`f34f4e49e0e0ae7013e824185766fe894609cbf1721e1aaa91d5facdeb4d1cc2`|R6:12|—|—|
|혼입12|`ebay-pair-8f73d488e2832d/back/surface/middle_left`|`a067dfb2df9b50f02aaba4810e6ed76ee09b15caf85cf85ac633f00c89decf46`|R7:47|—|z161|
|혼입12|`ebay-pair-3b3a43b176da9f/back/surface/lower_left`|`45f3ee3cb639a8f04e95075f5139c9a424127bd86dd71e4f3e793f1932619422`|R6:1|—|—|
|혼입12|`ebay-pair-858f5a4f342cec/back/surface/upper_center`|`dbed3ad3f1cd49b3c857f3822218141f17c5ae0c8b27fe7ea4da12b4d28bd50c`|R1:18|—|—|
|혼입12|`ebay-pair-b26fe718a8a0ff/back/surface/upper_left`|`b22a158b61dcae8ecd41bfee135f092f654280030cfca716875d0adeddbed674`|R7:6|—|—|
|혼입12|`ebay-pair-8b712018d115e4/back/surface/middle_right`|`df85ad1dd0cd98a81091b314225f3e54ee897a1f6fca7e40c3fe78fee279f125`|R7:30|—|z73|
|같은사진47|`ebay-pair-ef6332f853348b/back/surface/middle_right`|`4ea344a2290d2c6d9079f33c54ca4426c1033fd3e7770a4894631473a136445c`|R4:1|—|—|
|같은사진47|`ebay-pair-ef6332f853348b/back/surface/lower_left`|`4ea344a2290d2c6d9079f33c54ca4426c1033fd3e7770a4894631473a136445c`|R4:1|—|—|
|같은사진47|`ebay-pair-ef6332f853348b/back/surface/lower_center`|`4ea344a2290d2c6d9079f33c54ca4426c1033fd3e7770a4894631473a136445c`|R4:1|—|—|
|같은사진47|`ebay-pair-ef6332f853348b/back/surface/lower_right`|`4ea344a2290d2c6d9079f33c54ca4426c1033fd3e7770a4894631473a136445c`|R4:1|—|—|
|같은사진47|`ebay-pair-9eacfb8240a175/back/surface/upper_left`|`b8b0d95c23c4bd445e3ba79c4400ca3050683db14c68ac9d88805fe3ebc67a84`|R7:25|—|—|
|같은사진47|`ebay-pair-9eacfb8240a175/back/surface/middle_left`|`b8b0d95c23c4bd445e3ba79c4400ca3050683db14c68ac9d88805fe3ebc67a84`|R7:25|—|—|
|같은사진47|`ebay-pair-9eacfb8240a175/back/surface/lower_center`|`b8b0d95c23c4bd445e3ba79c4400ca3050683db14c68ac9d88805fe3ebc67a84`|R7:25|—|—|
|같은사진47|`ebay-pair-9eacfb8240a175/back/surface/lower_right`|`b8b0d95c23c4bd445e3ba79c4400ca3050683db14c68ac9d88805fe3ebc67a84`|R7:25|—|—|
|같은사진47|`ebay-pair-c5713f37809d71/back/surface/upper_left`|`f2a6f6a464acc67a36c1f6a151e85b3a4cc59a8765579113ab004b7e3b6f7b12`|R6:15|—|—|
|같은사진47|`ebay-pair-c5713f37809d71/back/surface/upper_right`|`f2a6f6a464acc67a36c1f6a151e85b3a4cc59a8765579113ab004b7e3b6f7b12`|R6:15|—|—|
|같은사진47|`ebay-pair-c5713f37809d71/back/surface/middle_left`|`f2a6f6a464acc67a36c1f6a151e85b3a4cc59a8765579113ab004b7e3b6f7b12`|R6:15|—|—|
|같은사진47|`ebay-pair-c5713f37809d71/back/surface/lower_right`|`f2a6f6a464acc67a36c1f6a151e85b3a4cc59a8765579113ab004b7e3b6f7b12`|R6:15|—|—|
|같은사진47|`ebay-pair-f9fbd5669f2646/back/surface/upper_center`|`3d47a0eb728b737c69fea78d72c5780e230812f5c4595c91da50c4f3b47e3c98`|R3:8|—|—|
|같은사진47|`ebay-pair-f9fbd5669f2646/back/surface/upper_right`|`3d47a0eb728b737c69fea78d72c5780e230812f5c4595c91da50c4f3b47e3c98`|R3:8|—|—|
|같은사진47|`ebay-pair-f9fbd5669f2646/back/surface/middle_left`|`3d47a0eb728b737c69fea78d72c5780e230812f5c4595c91da50c4f3b47e3c98`|R3:8|—|—|
|같은사진47|`ebay-pair-f9fbd5669f2646/back/surface/center`|`3d47a0eb728b737c69fea78d72c5780e230812f5c4595c91da50c4f3b47e3c98`|R3:8|—|—|
|같은사진47|`ebay-pair-f9fbd5669f2646/back/surface/middle_right`|`3d47a0eb728b737c69fea78d72c5780e230812f5c4595c91da50c4f3b47e3c98`|R3:8|—|—|
|같은사진47|`ebay-pair-0bf24b72066933/back/surface/upper_left`|`f34f4e49e0e0ae7013e824185766fe894609cbf1721e1aaa91d5facdeb4d1cc2`|R6:12|—|—|
|같은사진47|`ebay-pair-0bf24b72066933/back/surface/upper_center`|`f34f4e49e0e0ae7013e824185766fe894609cbf1721e1aaa91d5facdeb4d1cc2`|R6:12|—|—|
|같은사진47|`ebay-pair-0bf24b72066933/back/surface/upper_right`|`f34f4e49e0e0ae7013e824185766fe894609cbf1721e1aaa91d5facdeb4d1cc2`|R6:12|—|—|
|같은사진47|`ebay-pair-0bf24b72066933/back/surface/middle_left`|`f34f4e49e0e0ae7013e824185766fe894609cbf1721e1aaa91d5facdeb4d1cc2`|R6:12|—|—|
|같은사진47|`ebay-pair-0bf24b72066933/back/surface/lower_left`|`f34f4e49e0e0ae7013e824185766fe894609cbf1721e1aaa91d5facdeb4d1cc2`|R6:12|—|—|
|같은사진47|`ebay-pair-0bf24b72066933/back/surface/lower_center`|`f34f4e49e0e0ae7013e824185766fe894609cbf1721e1aaa91d5facdeb4d1cc2`|R6:12|—|—|
|같은사진47|`ebay-pair-8f73d488e2832d/back/surface/upper_left`|`a067dfb2df9b50f02aaba4810e6ed76ee09b15caf85cf85ac633f00c89decf46`|R7:47|—|—|
|같은사진47|`ebay-pair-8f73d488e2832d/back/surface/upper_center`|`a067dfb2df9b50f02aaba4810e6ed76ee09b15caf85cf85ac633f00c89decf46`|R7:47|—|—|
|같은사진47|`ebay-pair-8f73d488e2832d/back/surface/lower_left`|`a067dfb2df9b50f02aaba4810e6ed76ee09b15caf85cf85ac633f00c89decf46`|R7:47|—|—|
|같은사진47|`ebay-pair-8f73d488e2832d/back/surface/lower_center`|`a067dfb2df9b50f02aaba4810e6ed76ee09b15caf85cf85ac633f00c89decf46`|R7:47|—|—|
|같은사진47|`ebay-pair-8f73d488e2832d/back/surface/lower_right`|`a067dfb2df9b50f02aaba4810e6ed76ee09b15caf85cf85ac633f00c89decf46`|R7:47|—|—|
|같은사진47|`ebay-pair-3b3a43b176da9f/back/surface/upper_left`|`45f3ee3cb639a8f04e95075f5139c9a424127bd86dd71e4f3e793f1932619422`|R6:1|—|—|
|같은사진47|`ebay-pair-3b3a43b176da9f/back/surface/upper_center`|`45f3ee3cb639a8f04e95075f5139c9a424127bd86dd71e4f3e793f1932619422`|R6:1|—|—|
|같은사진47|`ebay-pair-3b3a43b176da9f/back/surface/center`|`45f3ee3cb639a8f04e95075f5139c9a424127bd86dd71e4f3e793f1932619422`|R6:1|—|—|
|같은사진47|`ebay-pair-3b3a43b176da9f/back/surface/lower_center`|`45f3ee3cb639a8f04e95075f5139c9a424127bd86dd71e4f3e793f1932619422`|R6:1|—|—|
|같은사진47|`ebay-pair-3b3a43b176da9f/back/surface/lower_right`|`45f3ee3cb639a8f04e95075f5139c9a424127bd86dd71e4f3e793f1932619422`|R6:1|—|—|
|같은사진47|`ebay-pair-858f5a4f342cec/back/surface/upper_left`|`dbed3ad3f1cd49b3c857f3822218141f17c5ae0c8b27fe7ea4da12b4d28bd50c`|R1:18|—|—|
|같은사진47|`ebay-pair-858f5a4f342cec/back/surface/upper_right`|`dbed3ad3f1cd49b3c857f3822218141f17c5ae0c8b27fe7ea4da12b4d28bd50c`|R1:18|—|—|
|같은사진47|`ebay-pair-858f5a4f342cec/back/surface/middle_left`|`dbed3ad3f1cd49b3c857f3822218141f17c5ae0c8b27fe7ea4da12b4d28bd50c`|R1:18|—|—|
|같은사진47|`ebay-pair-858f5a4f342cec/back/surface/middle_right`|`dbed3ad3f1cd49b3c857f3822218141f17c5ae0c8b27fe7ea4da12b4d28bd50c`|R1:18|—|—|
|같은사진47|`ebay-pair-858f5a4f342cec/back/surface/lower_center`|`dbed3ad3f1cd49b3c857f3822218141f17c5ae0c8b27fe7ea4da12b4d28bd50c`|R1:18|—|—|
|같은사진47|`ebay-pair-858f5a4f342cec/back/surface/lower_right`|`dbed3ad3f1cd49b3c857f3822218141f17c5ae0c8b27fe7ea4da12b4d28bd50c`|R1:18|—|—|
|같은사진47|`ebay-pair-b26fe718a8a0ff/back/surface/upper_center`|`b22a158b61dcae8ecd41bfee135f092f654280030cfca716875d0adeddbed674`|R7:6|—|—|
|같은사진47|`ebay-pair-b26fe718a8a0ff/back/surface/middle_right`|`b22a158b61dcae8ecd41bfee135f092f654280030cfca716875d0adeddbed674`|R7:6|—|—|
|같은사진47|`ebay-pair-b26fe718a8a0ff/back/surface/lower_center`|`b22a158b61dcae8ecd41bfee135f092f654280030cfca716875d0adeddbed674`|R7:6|—|—|
|같은사진47|`ebay-pair-b26fe718a8a0ff/back/surface/lower_right`|`b22a158b61dcae8ecd41bfee135f092f654280030cfca716875d0adeddbed674`|R7:6|—|—|
|같은사진47|`ebay-pair-8b712018d115e4/back/surface/upper_center`|`df85ad1dd0cd98a81091b314225f3e54ee897a1f6fca7e40c3fe78fee279f125`|R7:30|—|—|
|같은사진47|`ebay-pair-8b712018d115e4/back/surface/middle_left`|`df85ad1dd0cd98a81091b314225f3e54ee897a1f6fca7e40c3fe78fee279f125`|R7:30|—|—|
|같은사진47|`ebay-pair-8b712018d115e4/back/surface/lower_left`|`df85ad1dd0cd98a81091b314225f3e54ee897a1f6fca7e40c3fe78fee279f125`|R7:30|—|—|
|같은사진47|`ebay-pair-8b712018d115e4/back/surface/lower_center`|`df85ad1dd0cd98a81091b314225f3e54ee897a1f6fca7e40c3fe78fee279f125`|R7:30|—|—|
|나머지FN45|`ebay-pair-02170c802a45b2/back/surface/lower_left`|`e9e0f7016f1a184403a6644b6dc727735dab6cef53231bd94367bd8badace9ed`|R4:12|—|—|
|나머지FN45|`ebay-pair-02170c802a45b2/back/surface/lower_right`|`e9e0f7016f1a184403a6644b6dc727735dab6cef53231bd94367bd8badace9ed`|R4:12|—|—|
|나머지FN45|`ebay-pair-ba1c588f1093ca/back/surface/lower_right`|`0b64a9c7b434a74dce08d2998d3bf64f3cdf3d66befd85ec3b89bc58eb469a5c`|R7:42|—|z176|
|나머지FN45|`ebay-pair-a1eda100ac6e20/back/surface/upper_center`|`25fedbc158bc0b4da049a8f6c87b54e4ba2692ad08600e37a05a78e937de98e2`|R2:15|—|—|
|나머지FN45|`ebay-pair-4e32857c4919a9/back/surface/upper_right`|`eafbe97d26fd9e357924c789aec27e737f4dba968fa4faa02cee6adfe15298be`|R7:37|—|z1|
|나머지FN45|`ebay-pair-a8272f9ea217b0/back/surface/middle_right`|`a9b0fcb0adc40db11c0bfb353d2c1436ac44febf41dd7c2cd8c12399e430fbad`|R7:57|—|—|
|나머지FN45|`ebay-pair-83d2433a5374d2/back/surface/upper_center`|`af281dc7657d265f5fecf07788b64c4f1b8292174cbc7da068fe5e18d60e11b1`|R6:10|—|—|
|나머지FN45|`ebay-pair-83d2433a5374d2/back/surface/upper_right`|`af281dc7657d265f5fecf07788b64c4f1b8292174cbc7da068fe5e18d60e11b1`|R6:10|—|—|
|나머지FN45|`ebay-pair-5eb308b036ff51/back/surface/upper_center`|`b9a2289f21b0c9de99baf664aa778f1e926606ce0fcf4b38a4783c90327540e7`|R5:12|—|—|
|나머지FN45|`ebay-pair-2ea06a1e89a680/back/surface/center`|`c150c2f7bf7d11ae7c2804126614605bce3ca41443e0a73337c9c281226aa11c`|R2:29|—|—|
|나머지FN45|`ebay-pair-05704a31e488bb/back/surface/lower_right`|`845057d4dfa7bd220b706ca3181a3c3afbd55017c169dc6bd8dca39d4029a561`|R1:24|있음|—|
|나머지FN45|`ebay-pair-08e1afb7f248d9/back/surface/lower_left`|`3a8946a53afc502ad8ba8b69bda482f2caaeb34c7c1393e6547ebdb441d48348`|R7:50|—|—|
|나머지FN45|`ebay-pair-08e1afb7f248d9/back/surface/lower_center`|`3a8946a53afc502ad8ba8b69bda482f2caaeb34c7c1393e6547ebdb441d48348`|R7:50|—|—|
|나머지FN45|`ebay-pair-08e1afb7f248d9/back/surface/lower_right`|`3a8946a53afc502ad8ba8b69bda482f2caaeb34c7c1393e6547ebdb441d48348`|R7:50|—|—|
|나머지FN45|`ebay-pair-c5751d71bc4072/back/surface/middle_left`|`798f4fddc4544805a79e99b84d28d7c0ac3874aae38dd6bfa35e3eea218cd22a`|R1:7|—|—|
|나머지FN45|`ebay-pair-c5751d71bc4072/back/surface/middle_right`|`798f4fddc4544805a79e99b84d28d7c0ac3874aae38dd6bfa35e3eea218cd22a`|R1:7|—|z255|
|나머지FN45|`ebay-pair-c5751d71bc4072/back/surface/lower_right`|`798f4fddc4544805a79e99b84d28d7c0ac3874aae38dd6bfa35e3eea218cd22a`|R1:7|—|z86|
|나머지FN45|`ebay-pair-e7d7987b6879d2/back/surface/lower_right`|`a29593098dd9d6c3163a83afab4de41c6ce7845d208beee1b2c499c371954957`|R1:17|—|z125|
|나머지FN45|`ebay-pair-437c25d2b6161a/back/surface/upper_left`|`d60626728d2313a216c1f5c1dd14ed4b0b10eb996abded02ae76733d2fe2ac3e`|R7:49|—|z114|
|나머지FN45|`ebay-pair-437c25d2b6161a/back/surface/middle_right`|`d60626728d2313a216c1f5c1dd14ed4b0b10eb996abded02ae76733d2fe2ac3e`|R7:49|—|—|
|나머지FN45|`ebay-pair-9d3e6b22db7bad/back/surface/lower_right`|`0d37fd763e876b7067f08fb9b045a36bdf355ed6c20920fa8cfaa83f184fd87a`|R4:25|—|—|
|나머지FN45|`ebay-pair-2792f7f5843a18/back/surface/lower_left`|`9887b703e32d5c0b6fd47c93e905bb695a50d81d60a6d38ee9273c06c399d77c`|R7:40|—|z137|
|나머지FN45|`ebay-pair-af379b8eda0561/back/surface/lower_center`|`d9d17be42ad722985fd6a72b602bfad9cd5d796d2b9dd7c2bf8432877f09cd17`|R7:45|—|z206|
|나머지FN45|`ebay-pair-858f5a4f342cec/back/surface/center`|`dbed3ad3f1cd49b3c857f3822218141f17c5ae0c8b27fe7ea4da12b4d28bd50c`|R1:18|—|—|
|나머지FN45|`ebay-pair-bb523f319b49b2/back/surface/upper_right`|`6a47a35d31656fb579b1471e88bc9f184ba3cb804e844f331ab486118d1ca4ed`|R6:2|—|—|
|나머지FN45|`ebay-pair-8f4dba6a9c52eb/back/surface/lower_right`|`b14de0b1d2bf0ca4ee90dcf4078ebf0225d2ab6939aa06e227b053698156b9ae`|R7:46|—|z214|
|나머지FN45|`ebay-pair-c141bce426d0ad/back/surface/middle_left`|`a9cb2642ee2fb5ad54a8b6c112af7efb41a629d112376835d1c168884cc6f17e`|R4:11|—|z105|
|나머지FN45|`ebay-pair-533058b8573da1/back/surface/upper_center`|`7628ab2a4ea703a38bd54bec3caa20409a1ca5eeff2b1902bd52dcd890e83921`|R2:2|—|z236|
|나머지FN45|`ebay-pair-77fde2eaab6169/back/surface/lower_right`|`ee7c6748af6d6e5044053ceb3f060ad1ba79354d3f7cb6d3ac6085bf656af577`|R7:4|—|—|
|나머지FN45|`ebay-pair-9a4d114851c961/back/surface/middle_left`|`e597599022e1372c929810751e4de276e280f6440a89f95e5216128b26ce4a6d`|R1:22|—|—|
|나머지FN45|`ebay-pair-9a4d114851c961/back/surface/lower_left`|`e597599022e1372c929810751e4de276e280f6440a89f95e5216128b26ce4a6d`|R1:22|—|—|
|나머지FN45|`ebay-pair-2cf43268f5db04/back/surface/lower_right`|`f521eeaf55d8e167f89d9360770c0d5de3b401618f203b126d1fa7f31b5f63d4`|R4:18|—|—|
|나머지FN45|`ebay-pair-fc8b2605607a5d/back/surface/lower_left`|`3ed8d74b1d9cdba9592bef4c8bf23c2786ef8d51a4a44244fe266863108d450a`|R1:19|—|—|
|나머지FN45|`ebay-pair-b4b20d9851016c/back/surface/middle_right`|`64498373665e908ba06b3fd73f1d22971edfa5e346c3f537776f917a7ee3fe6b`|R3:17|—|z21|
|나머지FN45|`ebay-pair-6863e6760d0cbc/back/surface/upper_right`|`def4d603e18b04841b011e1872280f88db6252ccc42f03e5a1eea3b4a3cd766a`|R6:7|—|z244|
|나머지FN45|`ebay-pair-e169ee45a9507e/back/surface/lower_left`|`aa4ccc091e3a552a9c60d51d398f9624664415750ffa9573a19b800e64ed72e0`|R2:18|—|—|
|나머지FN45|`ebay-pair-0bfd194e23ca2b/back/surface/center`|`9230a9775693501416675da67a415aaa3828b5cd0a39af5c536f7a4318f0c408`|R7:58|—|z10|
|나머지FN45|`ebay-pair-8aec026c3585f7/back/surface/upper_right`|`478269ef98924306dc8fef360334a636ee0acb198b16d7dbb6c120db7e9a0abc`|R3:13|—|z216|
|나머지FN45|`ebay-pair-8aec026c3585f7/back/surface/lower_left`|`478269ef98924306dc8fef360334a636ee0acb198b16d7dbb6c120db7e9a0abc`|R3:13|—|z3|
|나머지FN45|`ebay-pair-2ba279a56e0323/back/surface/middle_right`|`f330cee569085a78715fe0466b2a772fa0ee6a65e61ae5d7428c0e3a2c0e298b`|R7:17|—|—|
|나머지FN45|`ebay-pair-3babd9fcfe1802/back/surface/lower_right`|`ffe415aa8f0503d54721a575c2385a99a38580b96168e5bd32da485537047dfb`|R7:21|—|z128|
|나머지FN45|`ebay-pair-b26fe718a8a0ff/back/surface/middle_left`|`b22a158b61dcae8ecd41bfee135f092f654280030cfca716875d0adeddbed674`|R7:6|—|—|
|나머지FN45|`ebay-pair-6a8abb37502417/back/surface/middle_left`|`8b3f851a387d44e1f3a7f828e59899f5c6526ada3ee01bd2374cdb31dd3a18e5`|R6:8|—|—|
|나머지FN45|`ebay-pair-c65d9a14e07512/back/surface/lower_right`|`13a59cffc753a8e3ba8acc3257cf26c65887161445fe37e86e346da48dd8ca4d`|R1:9|—|z142|
|나머지FN45|`ebay-pair-fb29e2064d5396/back/surface/middle_left`|`29fbab8073db633c83e43d3b017a0d63525704a9a3f2f2f93e53e7836d93884f`|R5:16|—|—|

## 5. 혼합118사진 적용/거부 감사

최초 거부사유 교차표(재선택 없음):

|사진 유형|고정 사진수|적용|지지수3/2 거부|삭제 불안정 거부|낮은 묶음 최고점 거부|거부 합계|
|---|---:|---:|---:|---:|---:|---:|
|혼합|118|29|63|16|10|89|
|정상 전용|79|29|35|14|1|50|
|결함 전용|7|0|4|0|3|7|
|전체|204|58|102|30|14|146|

혼합 적용은29/118(24.58%). 실패한 C≥60/118을 새 기준으로 바꾸지 않는다. 전체146을 혼합 거부로 부르지 않는다. 정상 전용 거부50이 모두 잘못된 거부라고 주장하지 않으며 결함 전용 거부7은 정상 참조가 없는 상황과 양립한다.

|혼합의 저장 상태|사진수|전체 구역수별 사진수|저장 L/H 크기 범위|저장 삭제검사|
|---|---:|---|---|---|
|적용|29|8구역7장,9구역22장|L3~7/H2~6|254건 모두 stable|
|지지수 미충족|63|7구역2장,8구역22장,9구역39장|L1~8/H1~8|검사 미실행(빈 목록)|
|삭제 불안정|16|7구역1장,8구역5장,9구역10장|L3~7/H2~6|137건 중unstable21건|
|낮은 묶음 최고점 미충족|10|8구역2장,9구역8장|L3~7/H2~6|검사 미실행(빈 목록)|

지지수63장 중 L<3이25장, H<2가38장으로 이번 저장 분할에서는 서로 겹치지 않는다. 세부 L/H별 사진수는 다음과 같다(합63):

|L/H|1/8|2/7|1/7|8/1|7/1|1/6|6/1|2/6|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|사진수|7|4|10|28|9|1|1|3|

전체 구역수가5 미만이라서3/2가 불가능했던 사진은 이 혼합63장에 없다. **가능한 구역 수 안에서 기존 최대 간격 분할이 한쪽에 몰렸다**는 절차적 설명까지 가능하다. 이 자체가 분할 규칙 결함이나 사진 품질 문제라는 인과 결론은 아니다. H=1의 정상 전용33장(8/1이31장,7/1이2장)은 정상사진에도 높은 점수 꼬리 하나로 분리가 생길 수 있음을 보여주지만 물리적 원인은 미확인이다.

낮은 묶음 최고점 거부10장은 원래3/2는 통과했고, 저장 candidate_low의 max가0.5 이상이다. 삭제 불안정16장은 원래3/2와 낮은 최고점 조건을 통과했으나 삭제검사에서1~3개 실패가 저장돼 있다. 안정성 거부를 “낮은 점수 정상 참조가 실제 없음”과 동치로 부르지 않는다. 앞서 거부된63/10장의 삭제 결과는 **미검사**이며 stable=false나 stable=true로 채우지 않는다. 다중 원인·조건을 바꾼 회복 적용률은 계산하지 않았다.

## 6. 사실·추론·미확인 가설

|분류|내용|경계/반례|
|---|---|---|
|사실|정확한 연결1776/204 일치, 봉인 후 채점, 혼입12·적용29|기록 밖 실행의 독립 증명은 아님|
|사실|혼입10곳 라벨 유지·2곳 변경, same-photo target0 47|기존 원문104곳 연결; 독립성/실제 관찰조건 동질성 미확인|
|추론|낮은 점수·큰 간격·삭제 안정성만으로 정상성이 식별되지 않음|실패한 고정 규칙의 충분성 반례이며 모든 무정답 규칙의 불가능 증명은 아님|
|추론|가용 구역 수보다 후보 분할 불균형이 지지수 거부를 직접 설명|임계 완화의 효용·물리 원인은 모름|
|미확인 H_L|기존 target1과 현재 사용하려는 정상 참조 의미/관찰조건 사이 차이가 일부 혼입을 설명|변경 이력만으로 확인 불가; 관찰제한도 원래 target1의 유효 범위일 수 있음|
|미확인 H_M|같은 관찰/판정 기준에서도 모델 표현이 양성을 낮은 점수로 배치|정확한 독립 의미 확인 없이 물리적 모델 오류로 확정 불가|

H_L와 H_M은 동시에 성립할 수 있다. 같은 `(score,target,선택/삭제기록)`은 (a) 유효 양성을 놓친 모델과 (b) 표현하고자 하는 개념과 관찰조건이 다른 라벨 모두에서 나올 수 있다. 저장 이진 target·이전 버전·기존 AI 합의만으로 두 세계를 구별할 수 없다.

전체 중앙값 보정 FN57→221/FP167→129는 실패 기록으로 유지한다. target0 반사실은 새누락128 중64 순감소를 보였으나 정답을 필요로 하고 전체 FN151/FP169로 제품 게이트 미달이다. 이번 Q=12, C=29도 반증이다. G 범위[-0.896830603480339,+0.04006087966263294]는 거부를 포함한 가능 범위이며 신뢰구간이 아니다. 세 실패를 새 임계/필터의 근거로 재포장하지 않는다.

## 7. 다음 검증 하나 — 독립 판정 출처의 동일 조건 일치 대조(조건부·미실행)

**ID: D-REFERENCE-SEMANTICS-IDENTIFIABILITY-20261116. 상태: not_executable_missing_evidence.**

선정 이유: 새 감사에서 동일 사진 대조47곳, 혼입 라벨 유지10/변경2, 모든 삭제 통과라는 연결이 드러났다. 따라서 라벨 변경을 재현하거나 score 규칙을 바꾸는 검증으로는 부족하며, 점수와 독립된 동일 구역 판정 근거의 의미 일치가 선행돼야 한다. 이 문서는 실행 계획을 승인받았다는 뜻이 아니다. 현재 자료만으로 실행 가능한 유효 검증은 없다.

### 구별하려는 주장과 변경 변수

- 핵심 H_L-all: 혼입12곳 **전부**가 같은 사진·구역·관찰조건의 독립된 사전 판정과 기존 target1의 의미 불일치로 설명되며, 유효 양성이 안정 L에 들어간 반례는 없다.
- 대립 H_not-all:12곳 중 **최소1곳**은 같은 기준의 독립 사전 양성 근거가 있어, 의미 불일치만으로 전부를 설명하지 못한다. 이때 모델/참조 선택의 부족은 해당 기존 양성 기준에 대해 남는다.
- 둘은 물리적 H_L/H_M의 완전한 인과 분해가 아니라 **“의미 불일치만으로 충분한가”의 한정된 반증 검사**다. 일부 불일치와 점수 오류의 공존은 허용한다.
- 변경 변수 하나: **채점 근거의 출처**를 기존 이진 target에서 점수 비노출·독립·동일 조건의 이미 존재하는 판정 원문으로 대조한다. 모델/점수/참조 선택/사진/기준은 변경하지 않는다. 정답을 사용하는 사후 진단이며 배포 가능한 무정답 추정법이 아니다.

### 대상·대조군·고정 분모

- 주 대상: 위 표12구역/10사진 전부. 결과가 애매한 행도12에 남긴다.
- 우선 대조군: 같은10사진의 선택 target0 47곳. 사진/fold/참조 선택 조건을 맞추기 위함이며 원래부터 정상이라는 새 확인을 생략하기 위함이 아니다.
- 오류 맥락 대조군: B0 나머지 FN45곳/36사진. 선택 바깥 오류에 동일한 출처 문제가 있는지 표시하며, 주 가설 분모12와 합쳐 비율을 희석하지 않는다.
- 총 고정104구역=12+47+45, 세 집합은 구역 기준 서로 겹치지 않는다. 혼합151/정상 전용183은 이번 감사의 맥락 대조이며 별도 검증으로 늘리지 않는다. 혼합 적용/거부118장도 고정 이력으로 남기고 개선 성능을 채점하지 않는다.

### 필요한 저장 자료·키·진입 조건

현재 E/B와 folds/학습 명부 외에 기본 저장소의 기존 감사·원응답·최종 선택 기록을 찾았다. **104/104구역은 동일 ID·사진SHA의 출처 사슬로 원문에 연결되며 원출처7개 해시도 기존 보존값과 일치한다.** 추가 상대경로/줄/해시는 위104행 표에 고정했다. 이는 최초 동결38개의 구성 변경이 아니다. **여전히 확보하지 못한 것은 현재 라벨의 원출처와 구별되는 독립 판정 및 그 동일 관찰조건·시점·점수 비노출 근거다.** 원문 미존재를 실행 불가 사유로 사용하지 않는다.

필수 연결은 `(id, image_sha256, side, area/동일 box, 판단기준 버전, 관찰조건)`이고 group/fold를 보존한다. 파일 이름·비슷한 카드·구역명만 같은 연결, 다른 사진SHA, 면 전체 판정의 구역 전파는 불허한다. 원문이 관찰제한을 유효 target1로 정의했다면 “손상 아님”만으로 라벨 불일치로 분류하지 않는다. 정답을 바꾸지 않고 두 출처의 주장만 비교한다.

진입 조건은 사전에 존재한 독립 원문을 합법적인 범위에서104/104 정확히 연결하고 정의·시각·점수 비노출을 확인하는 것이다. 이 조건을 통과하기 전 새 검증을 시작하지 않는다. 추가 원문 연결104/104만으로 이 조건을 충족하지 않는다. 혼입10곳은 원판정 자체,2곳은 현재 라벨에 반영된 점수 기반 표적 재판정이며, 혼입12곳을 별도 독립 판정과 대조할 수 없다. 따라서 상태는 `not_executable_missing_evidence`로 유지하되 reason은 `independent_judgment_and_observation_provenance_unestablished`로 구체화한다. 이는 새 검증 실행 결과나 H_L-all 반증이 아니다. 사용자는 기존 출처의 읽기 전용 탐색과 문서 반영만 추가 승인했으며 실행·보호자료 접근·추가 동결/사람 요청은 승인하지 않았다.

### 입력/채점 분리와 봉인 순서(미래에 별도 승인될 경우)

1. 이 설계와104개 키 목록·원문 허용 경로/해시·판정 대응 정의를 먼저 고정한다. 변경 변수는 출처 대조 하나이며 새 threshold/선택 규칙을 만들지 않는다.
2. 보관자가104행을 익명화하고 집합 역할/score/target/B0 오류ID/참조 선택 여부를 판정 근거 추출 단계에서 숨긴다. 이 감사는 이미 선택편향이 있는 진단이므로 완전 맹검을 주장하지 않는다.
3. 점수 비노출의 **기존 명시 판정**만 `동일 기준 양성 지지/명시적 의미 불일치/미확인`으로 기계적 연결한다. 자유 텍스트를 새 사람/AI 판단으로 재해석해야 하면 미확인으로 남긴다. 신규 사람 작업0·AI0이 성립하려면 기존 구조화 정의가 필요하다.
4. 대응표·미확인·중복·배제 없음·출처 해시를 봉인한 다음 역할과 기존 target/score를 열어 채점한다. 이미 봉인된 선택 결과를 재실행/변경하지 않는다.
5. 5fold train/held group와 photoSHA 분리 재확인. 같은 실물·사진의 여러 구역은 독립 표본이 아니므로104를 독립 표본수로 해석하지 않는다. 기존 모델선택/점수선택 라벨 및 반복 개발자료 편향을 해소하지 못하므로 독립 성능 시험이라 부르지 않는다.

### 사전 수치 판정(12곳의 충분성 주장만)

각 혼입 행을 S(동일 기준 독립 양성 지지), D(명시적 의미 불일치), U(미확인)로 기록한다. S+D+U=12이며 결측/상충 판정도U에 포함한다. 대조47/45는 동일 분류와 각 분모를 따로 보고한다.

- **제한적 지지:** D=12, S=0, U=0이고 필수 출처/대조104/104 진입 검사를 통과한 경우에만 H_L-all을 지지한다. 이것은 “현재 두 출처가12곳 모두 불일치”를 뜻하며 어느 쪽이 진짜 정답인지/성능 개선인지는 증명하지 않는다.
- **반증:** 유효한 S≥1/12이면 H_L-all을 반증한다. 최소1은 “전부 의미 차이”라는 보편 주장을 반박하는 논리적 수치이며 통계적 검정력/검증된 임상 기준이 아니다. S≥1과D≥1이면 두 문제 공존 가능성을 기록한다. H_M의 물리 원인 확정이나 새 학습 채택으로 연결하지 않는다.
- **판정불가:** S=0이고U≥1, 또는 독립성/동일 조건 미확인으로 주장을 구별할 수 없으면 판정불가. 좋은 사례만 남겨12를 줄이지 않는다. 현재는 원문104곳이 있어도 독립 판정/동일 조건 요건이 미충족인 **진입 차단**이며 검증 실행 결과로 기록하지 않는다.
- 출처 SHA/ID 불일치·중복 키·실행 오류는 `stopped_integrity_error` 등 절차 중단으로 구분하고 가설 반증/성능0으로 쓰지 않는다. 자동 재시도하지 않는다. 이미 검증된 일부 반례가 있더라도 완결된 검증 성공으로 포장하지 않는다.

12/12와1/12는 현재 실패안의 Q=0 보편 요구를 설명하는 충분성 반증 논리에서 온 값이다. 적용률60/118이나 기존 제품 FN/FP 게이트를 대체하지 않는다. 비교 후 임계값·판정 문장을 바꾸지 않는다.

### 동률·결측·거부·오류·비용

서로 충돌하는 동일 우선순위 사전 판정은 다수결/최신값 고르기를 하지 않고U. 점수 동률은 이 검증의 판단 기준이 아니며 새 순위를 만들지 않는다. 면·구역·사진·시각/정의 불일치는 연결 불가U로 남기며 정상으로 보충하지 않는다. 원래 추정 거부89장은 그대로 거부로 남기며 대체 추정값을 만들지 않는다. FN 대조45 중 거부사진40구역을 빼지 않는다. 사람 판정/재라벨 요청0, 신규 학습/추론0, 외부AI0. 원문이 구조화되어 없거나 독립성이 미확인이면 사람 작업0으로는 성립하지 않는다. 필요한 신규 사람 작업의 수/시간/금액은 현재 산정할 근거가 없어 미측정이며 요청하지 않는다. 프로그램 구현·실행비도 미측정이다.

### 결과별 결정과 반례

|결과|후속 결정(자동 실행 안 함)|남는 불확실성|
|---|---|---|
|제한적 지지|점수 보정/학습 전에 출처·관찰조건 계약을 메인 검토 대상으로 제출|독립 원문도 틀릴 수 있고, 라벨 불일치가 실제 FN의 원인이라는 인과 증명은 아님|
|반증|의미 차이만의 설명을 폐기하고 기존 양성을 놓치는 점수/참조 문제가 남는다고 기록|어떤 표현/물리 요인이 원인인지, 낮은 적용률과 같은 원인인지 미확인|
|판정불가/진입 차단|현재 보류 유지, 자료 요건만 남기고 실험/사람 요청 없음|현재 상황. 유효한 무인 원인 검증을 꾸미지 않음|
|무결성/실행 오류|오류 경로·기대/실제 보존 후 중단|성능과 가설 어느 쪽도 판정하지 않음|

반례1: A가 같은 target의 복사본이거나 점수를 보고 작성됐다면12/12 일치여도 독립 근거가 아니어서 H_M/H_L을 식별하지 못한다. 반례2: A가 다른 조명 사진 또는 면 전체의 손상 판정이면 구역 동일 조건의 근거가 아니다. 반례3: A는 손상만, 기존 target1은 손상+관찰제한이면 불일치가 정답 오류가 아니라 개념 차이다. 반례4: 모델 오류와 관찰조건 차이가 동시에 있으면 출처 대조만으로 각 효과의 크기·물리 원인을 분리하지 못한다. 따라서 이 한 가지 조건부 설계도 물리적 두 원인을 완전히 식별하는 검증이라고 과장하지 않는다.

### writing-plans 적용: 미실행 단계의 인계 체크리스트

- [ ] 메인이 별도 실행 승인 및 원문과 구별되는 독립 판정 근거/동일 관찰조건·시점·비노출·정의를 먼저 확정한다. 기존104곳 원문 연결만으로 진입시키지 않는다. 현재는 이 단계 전에서 멈춘다.
- [ ] 고정104키 연결 및 익명 판정/역할 분리 계약을 만들고, 출처 충돌·결측·관찰제한 포함 정의를 고정한다.
- [ ] 봉인된 출처 대응표 이후에만12/47/45를 각 분모로 채점한다. 사전 상태/가설 판정을 분리한다.
- [ ] 중단/판정불가를 포함한 전행 표와 결과별 결정만 보고한다. 기준 미달 뒤 새 임계/반복 검증을 이어가지 않는다.

검토한 접근: 점수 임계/분위수/최소수 변경은 기존 실패 반복이라 제외했다. 동일 사진 순위 점검은 위 감사의 최저순위 반례 이상으로 관찰/라벨 원인을 식별하지 못해 새 검증으로 선정하지 않았다. 남은 독립 출처 대조 하나도 진입 근거 부재를 숨기지 않고 조건부 설계로 제한했다. 사용자는 설계 제출 후 종료를 명시했으므로 구현 방식 선택/실행 승인을 이번 턴에서 요청하지 않는다.

## 8. 실제 검사·미실행·리스크·롤백·handoff

변경 문서는 task 계약과 이 보고서 두 개뿐이다. 최초 diff는 혼입12행 추적/사진별 L, 대조군 집계, 혼합118 교차표와 단일 조건부 설계다. 사용자 추가 요청에 따른 이번 diff는 기존 원문104행 연결표·원출처7개 해시·§93/§97 범위와 독립성 한계를 반영하고, 실행 불가 사유를 원문 부재에서 독립 판정/관찰조건 출처 요건 미확보로 갱신한 것이다. 함수 수/호출 깊이 변경 없음.

실제 검사는 Python 표준 라이브러리로38개 해시,1776/204 연결,기존 값/분모/집계,봉인 순서,5fold 실제 명부를 대조한 읽기 전용 감사다. 새 검증/공통 실험/selector/worker/analyze import·실행/학습/추론/보정/가상 성능/라벨 변경/사람 요청/외부AI 호출/설치·모델 테스트는 모두 미실행이다. D1·표면 보충시험·폐기105·예약보류9그룹 열람 없음. main 통합·push 없음.

리스크: 원문 연결을 독립 판정/실제 관찰조건 확인으로 오인하는 과도한 인과 해석, 기존 점수·오류 선택/반복 개발 편향, 같은 사진 구역의 상관, 독립 판정처럼 보이는 복사/점수노출 기록. 따라서 일반화 개선·모델 정확도 향상·절감률을 주장하지 않는다. 기존 성능은 B0 FN57/370·FP167/1406의 기록이며 이번 새 성능 수치/%p 비교는 생성하지 않았다.

고정 상태: 진척78/100(기준 파일 확인·점수 갱신 없음), 제품 FN≤67/370·FP≤112/1406·AUC 개선+0.03·사진그룹 bootstrap 하한>0·유효5fold 유지. D-LOC12/22·결정표④·후속 과제 선정 보류 유지. 이 출처 대조 설계가 D-LOC 후속 과제 채택이라는 뜻은 아니다.

HTML: 이번 명시 소유 파일은 Markdown2개뿐이고 지침/설계 준비 범위다. 새 성능 평가가 없으며 HTML 생성/열기/렌더 확인은 **미실행**. 기존 HTML을 이번 실행 성과로 인용하지 않았다.

롤백: main에 통합되지 않은 전용 브랜치의 두 문서 추가만 되돌린다. 필요 시 최종 문서 커밋을 `git revert <최종 SHA>`로 되돌리고, 계약까지 철회할 때에만 선행 계약 커밋도 역순으로 revert한다. 다른 worktree/브랜치/원본 artifacts/.claude는 삭제·복원하지 않는다. 이 브랜치는 미통합 상태로 보존한다.

이번 문서 반영 검사는 앞선 읽기 전용 탐색의104/104 출처 사슬/원출처7개 보존해시 일치 결과를 대조하고 허용 문서2개 범위·원문 라벨/점수 미복제·홈 경로 제외·diff 공백을 검사했다. 104행 키/포인터·집합12/47/45·원출처7개 보존해시 일치, 홈 경로 제외 및 `git diff --check` 통과를 확인했다. 새 검증/실험의 실행이 아니다. 이번 후속 보완만 롤백할 때는 이 보완 커밋만 revert하여 최초 설계 커밋 `85f8a43ca375b821b155ad65237be6aaa5fd0621`의 문서 상태로 되돌린다. 기본 저장소 원문과 다른 작업은 보존한다.

계약 로컬 커밋: `84d5506` (전체 SHA는 task에 기록). 최종 설계 커밋은 자기 SHA를 자기 본문에 넣을 수 없으므로 최종 응답과 `git log -1`을 정본으로 전달한다. 최종 확인 결과는 task handoff에 기록한다.

추가 확인의 문서 반영: 저장 화면25+11+1페이지 근거와104곳6분류를 위에 추가했다. 과거 해시 검사·출처 연결 감사는 재실행하지 않으며 이번 확인은 허용 문서2개의 diff/범위/공백으로 제한한다. 새 검증·사람 판정 요청·학습·추론·외부AI·main 통합·push 미실행. 실행 불가 상태·78/100·기존 게이트·D-LOC12/22·결정표④·후속 과제 선정 보류를 유지한다. 이번 추가 문서 반영만 철회하려면 이번 로컬 커밋만 revert하여 선행 `448147473c8b3bb6474404f64230c126517f0a0a` 문서 상태로 돌아간다. 원본 기록·.claude/·다른 worktree는 보존한다. 실제 롤백은 하지 않았다.

## 9. 새 관찰·독립 평가자료 수집 계약의 문서 보존 — 2026-11-17

사용자가 검토한 [수집 계약](new-observation-independent-evaluation-contract-20261117.md)을 이 전용 브랜치 문서로 추가하고 로컬 커밋까지만 승인했다. 정책 방향7개 선택 완료와 기준 기기·사진 출처·인력·시간·금액 한도·표본 수 미정을 구분한다. 구체 절차·통계 수치는 미정 또는 승인 전 제안이다. 새 계약은 `not_executable_pending_collection_contract_approval`이며, 이 보고서의 기존 원인 대조 설계 `not_executable_missing_evidence` / `independent_judgment_and_observation_provenance_unestablished`를 해제하거나 과거104곳의 독립성을 소급 확보하지 않는다.

이번 변경은 새 계약과 기존 task/이 보고서의 연결 기록 세 문서다. 문서 diff·경로·공백·로컬 커밋 상태만 확인하며 원출처 해시 감사나 모델/설계 검증은 재실행하지 않는다. 라벨 재요청·실제 수집·검증 실행·학습·추론·외부 호출·main 통합·push·HTML 생성/열기/렌더는 하지 않는다. 기존 평가 기준·원본 기록·.claude/·D-LOC·보호 자료·다른 worktree는 보존한다. 새 성능/일반화 개선은 확인하지 않았다.

리스크는 정책 선택을 실행 승인으로 확대하거나 새 수집 계약을 기존 근거의 독립성 확인으로 오인하는 것이다. 롤백은 이번 문서 반영 로컬 커밋만 revert하고 필요할 때만 선행 소유권 확대 커밋도 역순 revert한다. 실제 롤백은 하지 않는다.
