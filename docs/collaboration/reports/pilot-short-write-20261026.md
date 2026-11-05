# F2 계측 로그 부분 쓰기 실패 처리

개발진척30/100 (usable-card-analysis-v1.0, 변화0%p). 부분로그쓰기를기록성공/요청성공으로계수하지않는오류수정이다. 실제시범운영/F2완료/모델성능은미평가다.

변경파일: card_condition/pilot_record.py, tests/test_pilot_short_write.py, task/본보고서.
핵심diff: append_line의단일os.write반환바이트수를저장하고fsync후line전체길이와다르면OSError를발생시킨다. 기존O_APPEND·singlewrite·fsync·finally close와스키마는유지한다. 자동부분재시도/재작성/truncate없음.

수정전반례: 임시파일에실제로절반prefix만쓰는fault injection에서OSError가발생하지않아회귀검사가실패했다. 수정후부분/0byte쓰기가거절되고, 파일close/fsync·손상prefix보존·기존strictJSONL거절을확인했다. UsageRecorder.finish의completed는0으로남고CLI는stdoutempty/exit1/stderrJSON requires_gemini=true다. 모의요청analyze는한번뿐이고자동재시도는없었다.

검증코드SHA 72c7854b0f745f30a1625df0d7b44e55e2a08700.
CPU torch.set_num_threads(1) unittest test_pilot_short_write/test_pilot_record/test_pilot_summary 및이전listing/관찰/로드바이트/릴리스/finite_logits/frozen_candidate/frozen_test/evaluation_suite/physical_uncertainty/evaluation_inputs:85개PASS(7.122초). 신규5+기존pilot9+이전71. 기존pilot/listing검사에합성무작위checkpoint추론포함, 실제사진추론·새학습·외부AI0. 실제디스크고갈을유발한검사가아니며OS부분쓰기반환을fault injection했다. 전체suite미실행.
compileall변경소스1/신규검사1, diff --check PASS. pilot_record함수7→7, 신규검사6함수, 호출전이추가없음.

리스크/복구: 부분prefix는증거로남으며그뒤에실패기록을추가하려다역시부분쓰기될수있다. 해당JSONL전체는기존요약기가거절한다. 오류율을0으로간주하거나자동으로손상행을버리지않는다. 운영자가원본파일을보존한뒤독립적인요청총수/실패로그와함께감사해야한다. 다른동시요청의append를잘라내지않기위해이수정은파일truncate/롤백을하지않는다.
정상전체쓰기의메트릭/스키마는같다. F2의7일/50실물/100요청·정상카드오탐·동일릴리스/장치고정·승인소비경로는별도실측·증거가필요하다.
롤백: 실행중작업없을때 `./develop -- git revert 72c7854`. 과거로그를복원/수정하지않는다. 원래부분쓰기성공계수결함이돌아오므로해당회귀가실패한다.
HTML artifacts/pilot-short-write-20261026/index.html 생성·85검사/30점/SHA/리스크/롤백내용대조. 실제화면렌더는열기응답과구분한다. 브라우저다운로드를재시도하지않았다.

성과HTML열기응답은queued, 실제렌더미확인.
