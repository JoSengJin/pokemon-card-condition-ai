# 점선 안 판정용10건 — 2026-11-10

개발 진척78/100(v1.13) 유지. 모델 최고점수 후보 점선 안의 실제 결함 유무를 확인하는10건을5건씩2파일로 제공한다. 이전10건은 사진확대구역 판정으로 보존하며 후보 정답으로 바꾸지 않는다. 새모델성능평가/학습 없음.

변경 파일: tools/diagnostics/mobile-point-review-20261110/scriptfree.py(기존crop동작 유지,후보모드와공통응답필드),candidate.py(범위/사진SHA/패킷/구역/토큰/사각형검증 및10건생성),candidate_checks.py(조합/변조/범위분리검사),docs/collaboration/tasks/mobile-candidate-ten-20261110.md,이 보고서.

핵심 diff: 후보 점선을 처음부터 표시한다. 질문은 점선 안만 대상으로 하며 선택지는 ‘결함 있음/결함 없음/판단 불가’다. JSON kind=surface_candidate_review_manual_draft,scope=visible_defect_in_model_candidate_box,candidate_token/candidate_box를 원본 패킷에 묶는다. defect는 점선 안에 실제결함,normal은 충분히 보이는 점선 안에 결함없음,unknown은 판단불가다. 미선택은responses에서 제외한다. 후보 하나에 대한 답이며 카드전체 정상/모든 결함 검출/정확손상좌표/threshold 기준오탐을 뜻하지 않는다. 기존cropvalidator는새답변을거부한다.

검증 소스 9d4ecf147c4302520d443eb6adb2b19c16567ab2. ./develop -- .venv/bin/python tools/diagnostics/mobile-point-review-20261110/candidate_checks.py 와 기존 scriptfree_checks.py 모두 통과. 후보1024조합과 기존crop1024조합 검사. 토큰/사각형/사진SHA/구역정보 변조거부,unknown/null 보호,범위분리,점선초기표시,일반dataURI이미지/noJS 검사. 함수수 scriptfree2→3,candidate1,candidate_checks1;main→render→combined_outputs→draft_response 전이3. 실제폰렌더/터치/복사 미확인. CSS :has 미지원시 수동JSON fallback은 그대로다.

candidate.py를develop안에서실행하여 artifacts/mobile-candidate-review-20261110/candidate-01.html(기존번호11~15),candidate-02.html(16~20)을 생성했다. 이전10응답과 중복0,원본crop/전체사진20개dataURI는기존review03/04와동일. 실제생성파일별3개대표JSON도검증했다. 각파일에서선택을마치고JSON을한번씩복사한다. 10건을한파일에합치면4^10개JSON이필요하므로기존작은묶음제약을유지했다. 기존확대사진10개답변/정답/손실/임계/성공기준변경0,새학습/추론0,새후보정답0. 성능개선은주장하지않는다.

리스크: 점선이작거나흐리면판단불가로둔다. 모델후보는최고점수patch하나이지모든결함목록이아니다. 사진밖/점선밖손상은이번후보판정에포함하지않는다. 후보사각형은정밀손상좌표가아니다. 새JSON은사진전체판정과자동혼합하지않는다. 스크립트없이정밀클릭/자동저장은지원하지않는다. 위치설명은마지막JSON에적고선택변경시다른초안으로옮겨지지않는다.

롤백: ./develop -- git revert 9d4ecf147c4302520d443eb6adb2b19c16567ab2 로이번3소스변경만되돌린다. 기존사람응답/후보응답/HTML/패킷은보존한다. 새후보응답은별도범위로검증·원문보존해야하며기존사진전체라벨을덮어쓰지않는다. 생성/검사/열기근거 manifest.json/postflight.json/checks.log/opening-status.txt,원격SHA remote-sync.json.

열기요청 macOS open exit0. 실제폰렌더/복사 미확인. 두파일 크기7,212,228/8,360,780bytes.
