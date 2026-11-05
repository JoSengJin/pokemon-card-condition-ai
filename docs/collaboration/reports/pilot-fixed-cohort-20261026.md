# F2 동일 릴리스·선언한 실행구성 검사

전체진척30/100 (usable-card-analysis-v1.0, 변화0%p). 서로다른릴리스/장치/모델입력크기를합친p95의거짓통과를막았다. 실제시범/F2완료/속도개선/모델품질은미평가다.

변경: card_condition/pilot_summary.py, tests/test_pilot_summary.py, 신규test_pilot_fixed_cohort.py, task/본보고서.
핵심diff: 기존release_id그룹의합계는label진단값으로남기고full identity(package_version/input_contract/manifest_sha256/checkpoint_sha256)와실제성공model_sha256을대조한다. 이름이같아도full identity가다르면conflict/pinned=false/F2조건False다. full identity가없거나실패기록에release=None이면label만으로실패manifest를추정하지않으며조건None이다.
모든성공기록의device(cpu/mps)/image_size224또는448/batched_views(bool)가같아야합산warm앞뒤p95조건을평가한다. 혼합이면valueNone/metFalse, 누락이면valueNone/metNone이다. 구성별n/p95진단은보여주되가장빠른구성을선택하지않는다. 실제장치실물ID/원본사진치수는여전히미검증이다.
시간/분모검증은NaN/Inf·음수·bool숫자·analysis>total·잘못된outcome/cellcount·확정모델SHA모순을ValueError로거절한다. producer/과거usage로그/정답/학습/모델/기준/진척은변경하지않았다.

검증코드SHA 27c6f201d0d9446b7ec06f1d63d7307836a4db32.
수정전재현: same-label에manifest/모델SHA가다른cpu224·mps4482개를넣으면groups1, p95value4/n2/metTrue였다. 수정후충돌릴리스와혼합구성은합산p95를통과시키지않는다.
CPU torch.set_num_threads(1)로test_pilot_fixed_cohort와이전pilot/검토/로드바이트/관찰/릴리스/finitelogit/frozen/evaluation_suite/physical_uncertainty/evaluation_inputs를실행:91개PASS(8.205초), 신규6/기존85. 정상cohort의30초/1%/7일/100요청경계assert는유지했고기존합성fixture의identity/config를producer형태로명시했다. 기존pilot/listing검사에무작위합성checkpoint추론포함. 실사진추론·새학습·외부AI0. 전체suite미실행.
compileall소스1/수정검사1/신규검사1, diff --check PASS. 함수pilot_summary5→7(validator/configuration각1추가), 기존검사7·신규검사7. main→summarize→release_group→configuration_state→p95최대4전이,새재귀없음.

리스크: schema1 legacy파일은읽지만identity/config가없으면과거True였던숫자조건이None으로바뀔수있다. 이는증거미확인표시이고0오류/정상운영판정이아니다. 현재producer는실패시full release를남기지않는경우가있으므로그실패를이름만으로정확한릴리스에귀속하지않는다. record_error_rate의label단위진단값은보존하지만F2수용조건은미측정이다.
같은이름의다른릴리스가한파일에있으면그룹의요청합계는label진단값이다. 고정trial이아니므로pinned=false/identityvariants를확인해야하며한릴리스100요청으로해석하면안된다. 원본데이터를자동으로쪼개거나삭제하지않는다.
장치문자열cpu/mps는기종·실물hardware검증이아니다. image_size는모델입력크기이며원본사진치수고정을증명하지않는다. 승인·7일시범·50실물·정상카드오탐·독립성/하드웨어근거가없어pilot_certified=false유지.
롤백: 진행중작업없을때 `./develop -- git revert 27c6f20`. 기존로그는그대로보존한다. 원래혼합cohort통과결함이복원되므로신규검사가실패할수있다.
HTML artifacts/pilot-fixed-cohort-20261026/index.html 생성·91검사/SHA/30점/한계/롤백내용대조. 브라우저다운로드는재시도하지않았다. 성과HTML열기와실제렌더는구분한다.

성과HTML열기요청은queued,실제렌더미확인.
