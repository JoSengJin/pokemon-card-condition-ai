# 10건 한 HTML·결과 한 번 복사 — 2026-11-10

개발 진척78/100(v1.13) 유지. 점선 안 확인10건을한파일로바꿨다. 이전20개항목(사진전체10/후보10)은제외하고새10개를담았다. 실제폰의전체선택/복사는미확인이다.

변경파일: tools/diagnostics/mobile-point-review-20261110/ten.py(신규),ten_checks.py(신규),docs/collaboration/tasks/mobile-ten-onefile-20261110.md,이보고서. 기존생성기/모델/worker/사람답/라벨/손실/기준은변경하지않았다.

핵심diff: 4^10개의전체JSON을미리만드는대신40개CSS선택규칙으로10개응답조각중각각하나를표시한다. 마지막contenteditable결과칸에서JSON전체를한번선택/복사한다. 스크립트는없다. CSS미지원시자동연결불가경고와전체수동textarea를보인다. 같은원사진은SHA별한번만dataURI내장하며다른항목은같은접힌사진으로이동한다. 원본crop/원사진바이트는그대로다. 점선안판정scope/token/box/SHA는기존후보규약과같다.

미선택은각응답의judgment:null로명시하며정답/완료판정으로저장하지않는다. 모르겠음은unknown이다. 이번형식은10개응답자리를유지하므로수신시null은미확인으로남겨야한다. 사진전체판정이나정밀손상좌표로변환하지않는다. 실제새사람응답0/새모델호출0/새학습0이다.

검증소스 b7f1548c89afe19feab9062c16dd8ed1566d7381. ./develop -- .venv/bin/python tools/diagnostics/mobile-point-review-20261110/ten_checks.py 통과. 76선택벡터의CSS규칙에맞춰조립한JSON을기존후보validator로검증했다. 모든선택위치/상태·범위/토큰/사각형연결/null미확인·unknown을검사했다. 사진16개의dataURI는기존crop_view와같고전체원사진은6개다. 고유ID/라디오40개/복사칸1개/noJS/noSVG/CSS미지원fallback도검사했다. 함수ten2/ten_checks0;main→render_ten→combined_editor→draft_response전이3. 이는합성/정적검사이며네이티브복사검증은아니다.

실행: ./develop -- .venv/bin/python tools/diagnostics/mobile-point-review-20261110/ten.py. artifacts/mobile-ten-onefile-20261110/review-10.html 생성. 인덱스20..29/이전20개항목과중복0/크기5,559,790bytes. 실제생성본에서4가지균일선택JSON도검증했다. manifest.json/postflight.json/checks.log에근거를남겼다. 모델성능개선은평가하지않았고진척점수도그대로다.

리스크: 실제폰이contenteditable칸의전체선택복사에서CSS로숨긴조각을제외하는지아직확인하지못했다. 복사값은수신시JSON/중복ID/범위/사진/후보validator를통과해야저장한다. 잘못된복사를정답으로추정하지않는다. 사진이작거나흐리면판단불가다. 클릭점/자동저장은없다. 설명은선택을마친뒤마지막결과칸에적으며다시선택하면다른초안으로바뀌고설명이자동이동하지않는다. 폰의실제선택/복사확인이남은사람의존이다.

롤백: ./develop -- git revert b7f1548c89afe19feab9062c16dd8ed1566d7381 로신규두도구를제거한다. 기존생성기/응답/HTML/압축파일과이번HTML은보존한다. 열기결과opening-status.txt,원격SHA remote-sync.json.

열기요청 macOS open exit0. 실제폰렌더/전체복사 미확인.
