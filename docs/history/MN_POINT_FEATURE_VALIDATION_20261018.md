# M 실제점·N 정상 동시 학습과 실제 특징 학습 — 2026-10-18

## 결과와 수용기준

- 사용자 저장 M점 x=0.13627075619345727, y=0.22783138711095913. 원본1600×1600 및 미리 고정한M crop 안에 있음. 기존edge1/검토자J 보존. N은 이전 사용자확정edge0의짧은구간만사용. 원본183라벨과Q surface1/edgeunknown 보존.
- 56crop=기존54+N0+M실제점1. 손상점33·정상crop23·출처그룹20. 정상/손상혼합출처그룹2(꼬렛,새피카츄). 출처그룹/원본해시분리는검사했지만실물독립은판매사진만으로확정하지않음.
- M/N동일사진은함께학습처리. 이후독립시험으로재사용하지않음. 미확인전체카드box를승인으로추정하지않음. 클릭한M실제점만위치정답이며그밖의양성crop픽셀은음성학습하지않음.

| 같은26개개발구간 | 손상구간누락/4 | 정상오탐/22 | 실제사람점누락/4 |
|---|---:|---:|---:|
| 기존고정448최선 |0|5|0|
| 이전N만학습 |0|6|0|
| M실제점+N0 고정특징 |0|5|0|
| 동일M/N 실제QKV rank4학습 |0|5|0|
| 동일QKV학습+같은사진비교손실 |0|5|0|

M점반영은N실패후보의새오탐index7을복구해27.27→22.73%(−4.55%p). 기존최선대비추가누락/오탐개선0%p. 셋다기존최선돌파없어운영미채택. 독립품질검증미통과·Gemini절감0.

## 가설·실행

1. `confirmed-mn-point-training-20261018`: N0만반영한모델에M1실제점추가. 기존448 DINO특징·L2=1·0.5기준·실물출처/원본해시제외·학습그룹/클래스가중치유지. 기존전체그룹가중치는새동일그룹M/N을포함해재계산되므로단순샘플개수만바뀐것으로주장하지않음.
2. `confirmed-mn-feature-training-20261018`: 같은56자료/기준에서마지막QKV rank4 LoRA만실제학습. seed42, AdamW lr.001/weight_decay.01, 고정10step. 학습후head를학습안에서수렴재적합. 바뀐백본키가`attn.qkv.weight`하나임을확인. 학습손실은감소했으나평가판정추가향상없음.
3. `confirmed-mn-pair-feature-training-20261018`: 2와같은데이터/고정10step에비교항하나만추가. `softplus(max_normal_N_logit - human_M_point_logit +1)`, 가중치는기존M/N crop가중치의합. 정상N은실제로확인된구간이라내부고득점패치를정상으로강조할수있지만, M의최고반응을인간점으로바꾸지않음. 여전히평가판정개선없음.

모든후보O/P/Q미학습. M/N은학습사진이므로성능분모에추가하지않음. 원래26구간은반복개발평가이지26새실물블라인드시험이아님. 새epoch/임계값선택을평가출력으로하지않음.

## 변경 파일·핵심 diff

독립 프로젝트 `.`:
- 위3개연구폴더: `plan.json`, `run.py`, `result.json`, `fold-{0,1,2}.pt`, `verification.json`. M/N점학습은`patches.pt`, `human-point-M.json`; 실제특징학습은`prefix448.pt`와병합QKV저장. 원본모델덮어쓰기없음.
- `artifacts/wear-pooling-audit-20261018/new-pikachu-review/training-use-M-point-20261018.json`: M점추가학습사용이벤트. 기존사전계획/예측/사용자정답은불변.
- `artifacts/mn-point-feature-review-20261018/{build_report.py,index.html,summary.json,M-training.png,N-training.png,78개위치표시PNG}`: 사람정답/최고반응/전후성능을사진으로표시.
- `artifacts/wear-normal-learning-20261018/{build_report.py,index.html}`: M입력완료및후속결과링크로정정. 완료위치재요청없음.
- `artifacts/mn-pair-next-intake-20261018`: 기존eBayCLI로3매물7사진·Gemini0·조건라벨생성0. 판매자NearMint문구를정상정답으로사용하지않음. Codex가카드한장·로고·네변/모서리를확인하고추가후보선정. 광고사진제외.
- `artifacts/mn-point-feature-review-20261018/new-vulpix-review`: 새식스테일R/S 입력/예측선고정. 사람정답미확인/학습0/성과통계null. 사진원본decodedhash가56학습원본과겹치지않음을확인했으나실물독립성은미확인.
- `MN_POINT_FEATURE_VALIDATION_20261018.md`: 이검증기록.
- 소비프로젝트 `CONDITION_ANALYSIS_TODO.md`: 체크포인트추가. 소비런타임미변경.

## 검증

- 저장모델각각실제원본26forward 총78회,각구간출력과4사람점점수검증. 점수차0, 일반QKV학습사람점최대차5.96e-8, 그외0. 바뀐백본키QKV하나뿐. 학습안가중치정규화/수렴/실물그룹및원본해시제외검사통과.
- unittest27개통과: regression_audit, dino_wear_lora, local_wear_cnn, point_patch_head.
- 두특징학습후보의전체56prefix캐시를고정DINO마지막블록으로재구성해원래특징과최대차0을확인. `artifacts/mn-point-feature-review-20261018/verify.py`, `verification.json`으로재현가능.
- HTML 모든로컬참조존재검사, R/S 원본짧은구간확대사진직접시각확인.
- M저장좌표를직접확인하고실제입력상에표시해시각검증. 원본183 SHA `23fbe9ea6f4be297887c87a32ccc496cc95e08162292cfe711b11ab43b94935a` 불변.
- 앱HTML열기요청은queued일수있으며완전브라우저E2E를주장하지않음.
- 특징학습첫실행은자동승인검토사용량한도로시작되지않음. 사용자재개후같은승인절차재시도로실행완료; 승인우회없음.

## 리스크와 롤백

소수실물·저해상도/촬영문맥·미세특징표현의일반화한계가남음. 실제가중치변화/학습손실감소는운영성능향상을보장하지않음. 원본평가26구간반복사용으로선택편향이있어최신사진도실물독립검증전일반화로부풀리지않음. 운영교체를하지않았으므로런타임롤백불필요. 새후보artifact를사용하지않으면기존경로유지. 사람M/N정답·학습사용이력은삭제하거나독립시험으로되돌리지않음. HTML은generator로재생성가능.

## 다음 사람 입력

M/N완료좌표/정답/카드영역재요청없음. 새eBay식스테일R(좌측중간짧은끝선)·S(우측중간짧은끝선)만정상/엣지손상/표면흔적/판단어려움구분이필요함. 모델추론전에입력·가중치계획을고정했고표시화면에서두구간만비교함. Q는판단어려움으로확인종료.
