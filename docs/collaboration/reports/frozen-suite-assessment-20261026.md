# 같은 봉인·후보 평가결과의 전범위 수치판정

개발 진척률 30/100 (usable-card-analysis-v1.0, 0%p). 이번 성과는 저장한 보고서 결속·원본정답/분모 재대조와 전범위 수치조건 보고다. 모델성능 변화는 미평가이며 실제시험은 실행하지 않았다.

## 변경 파일 / 핵심 diff
- card_condition/evaluation_suite_inputs.py: candidate/seal/report 바이트SHA, role/model/manifest/threshold, 기록한 모든 입력, 사용영수증의 SHA/실물/사진/역할을 대조한다. 원본 projection의 ID·정답·group·사진·geometry를 각 prediction과 대조한다. side의group/side는 원본 row에서 가져오고 새로 추정하지 않는다. 각보고서는 원래 저장한 {path,sha256} 핀을 명시해야 한다.
- card_condition/evaluation_suite_metrics.py: raw0.5 TP/TN/FP/FN, 양성/정상단위·실물수·점수누락·미확인, C수치20단위/5실물 및5%/10%, D1각30실물을 구분한다. 원본 metadata.language/edition과 side_annotations.visibility_issues에서 하위군 분모를 공개한다. 없으면unknown, 이름/사진에서 추정하지 않는다.
- card_condition/evaluation_suite.py: edge/corner/surface는 region_final, centering은 side_final, 관찰제한은 observation_final로 고정한다. 저장된 rawmetrics와 재계산값이 다르면 거절한다. 세역할 중 일부만 있으면 부족셀을 남긴다. 기존 physical_uncertainty를 직접 호출해 D3수치를 계산한다. 실제점반응은unmeasured/None, d1/d2/d3_verified/production_ready는false다.
- card_condition/evaluation_suite_cli.py: `python -m card_condition.evaluation_suite_cli TEST SEAL CANDIDATE OUTPUT --seal-sha256 SHA --candidate-sha256 SHA --region REPORT --region-sha256 SHA --side REPORT --side-sha256 SHA --observation REPORT --observation-sha256 SHA`. 역할보고서 일부도 가능하나 전범위통과로 해석하지 않는다.
- tests/test_evaluation_suite{,_inputs,_safety}.py: 합성60실물/120사진·mock모델에서 모든 수치조건이true여도 완료인증false 확인. report/receipt/후보혼합·변조정답/geometry·중복/누락·잘못된rawmetrics·점수누락·부분역할·하위군unknown·출력보존을 검증한다.
- task/본보고서. 기존소스는수정하지않았다. 실제원본/라벨/모델학습/기존실험/진척점수/소비서비스 변경0.

## 실행 검증
코드SHA 3d935ee4172ed132c7bb8b753659bd200a26eab6.
`PYTHONPATH=tests .venv/bin/python -m unittest test_evaluation_suite_inputs test_evaluation_suite test_evaluation_suite_safety test_frozen_candidate test_frozen_candidate_evaluation test_frozen_test test_frozen_test_evaluation test_physical_uncertainty test_physical_uncertainty_evaluation test_evaluation_inputs`: 44개PASS(2.023초), 신규12개/관련32개. 전체suite미실행. 학습/실사진추론/외부AI0, checkpoint는 metadata만읽었고 모델은mock이다.
compileall(소스4/신규검사3), diff --check PASS. 최초 fixture에 crop필드가빠져실패한7개와, 기존관찰평가기의 manifest SHA가top-level대신input_hashes에있어서실패한2개를 수정후 위검사를통과했다. 실패를 성능수치로 해석하지 않는다.
AST 함수수: suite1/inputs2/metrics3/CLI1, 신규검사7/6/4. 주요경로 main→assess_suite→matched_reports→read_candidate→file_sha256 4전이, main→assess_suite→physical_uncertainty→event_summary→wilson_upper4전이. sourceprojection호출은assess에서직접, 추가wrapper/재귀없음.

## 한계 / 위험
- 보고서 SHA는 평가직후 별도로 보존한 값을 제공해야 한다. 바뀐파일의 SHA를 새로주면 그것을 원래기록으로 인증하는 서비스가 아니다. 이 경우에도 원본정답/분모/모델·영수증 결속은 검사하지만 모델이 실제그점수를냈다는 암호학적증명은 아니다.
- receipt는시도기록이고성공인증이아니다. 후보·D1봉인·정답출처·실물그룹의정확성·선택전사용이력·필수회귀·실제클릭점반응은 별도근거가필요하다.
- 구역점수를 실제클릭점정확도로 바꾸지 않는다. 실제점측정이없으면 판정기는완료를선언하지않는다. 알려진정답의 점수없음은 원래양성/정상분모를유지하며 FN/FP율미측정으로남긴다. 미확인을정상으로채우지않는다.
- 언어/판본/촬영제한 하위군은사람metadata그대로다. 다중제한은여러하위군에들어가므로합산분모로쓰지않는다. 정상실물수는출처에제공된해당질문단위의정상이며 전체카드정상을보장하지않는다.
- 독립실자료에서한번도실행하지않았다. 파일SHA재확인·projection·checkpoint metadata로드의 I/O가추가된다. 모델 정확도/일반화/속도개선은주장하지않는다.

## 롤백 / 보고
`./develop -- git revert 3d935ee 3c08a2b 3553c49` 후 이전관련32개검사. 신규검사3개는삭제되므로신규44개검사를그대로실행하지않는다. 평가usage영수증/원본은삭제하지않는다.
HTML artifacts/frozen-suite-assessment-20261026/index.html 생성·44검사/SHA/30점/한계/롤백내용대조. 열기응답과렌더확인은별도로기록한다.

HTML 열기요청은 Codex browser 도구에서 queued 응답. 실제화면렌더는미확인이다. 내용검사와 화면확인을 구분한다.
