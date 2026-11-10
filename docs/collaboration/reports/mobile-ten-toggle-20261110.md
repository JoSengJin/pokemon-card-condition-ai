# 미확인 후보 표시 체크박스 복원 — 2026-11-10

개발 진척78/100(v1.13) 유지. 10건 한 파일의 각 원본crop 앞에 ‘미확인 모델 후보 보기 · 점선 켜기/끄기’ 체크박스를 복원했다. 기본은 켜짐이며 해제하면 후보 점선과 미확인 글자만 숨긴다. 판정/JSON/사진에는 영향을 주지 않는다.

변경파일: tools/diagnostics/mobile-point-review-20261110/ten.py(기본HTML체크박스/label/CSS복원),ten_checks.py(연결/기본상태/선택자회귀검사),docs/collaboration/tasks/mobile-ten-toggle-20261110.md,이보고서. 소스 a848fb13923f369641889c384d45e4afac31062f.

핵심diff: display:none인candidate를같은article의checkbox:checked~raw-frame일때만표시한다. JS는추가하지않았다. 라디오40개/마지막JSON칸1개/공유원사진/원본화질/후보판정scope/token/box는그대로다. 함수ten2/checks0과최대호출전이3도그대로다.

사용자가보낸10칸JSON은패킷/사진SHA/후보토큰·사각형검증을통과했다. 결함7건/unknown2건을명시적응답9건으로보존하고null1건은미확인으로남겼다. 원문 artifacts/mobile-candidate-human-response-20261110-batch03/human-response.json,요약 reception-summary.json. 원문SHA75de0da6b83af4512707fc2ae8c0e1256730292bcc468447f368ca00af0a964a. 후보누적응답19건(결함16/없음1/판단불가2)이며이는전체모델정확도가아니다. 기존10개사진전체응답과분리했다. 라벨교체/학습/정밀점추정0이다.

실행검증: ./develop -- .venv/bin/python tools/diagnostics/mobile-point-review-20261110/ten_checks.py 통과. 체크박스10개/for연결/기본checked/원본프레임앞의형제관계/CSS체크시표시·해제시숨김을정적으로검사했다. 기존76조합의후보JSON조립,사진dataURI일치,단일복사칸,null/unknown보호검사도통과했다. 실제브라우저의토글을클릭하거나새폰화면을본검사는아니다.

산출물 artifacts/mobile-ten-toggle-20261110/review-10-checkbox.html. 이미답한서로다른29개항목을제외했다. 이전미선택1건(원본인덱스23)과새9건(30..38)을담았으며이미답한9건을재요청하지않는다. 실제파일10checkbox/기본표시10/복사칸1/4대표JSON검증성공/크기6,872,204bytes. manifest.json/postflight.json/checks.log에기록했다. 사진/정답/손실/threshold/성공기준/모델변경없음,새추론없음. 모델성능은평가하지않았다.

리스크: 새파일의폰표시·체크박스토글은미확인이다. CSS미지원fallback은유지한다. 점선을끄면판정대상이보이지않으므로후보를확인할때다시켜서보면된다. 표시체크박스의상태자체는정답이아니다. 미선택null은정답이아니며unknown을정상/결함으로추정하지않는다. 이미받은응답은원문과검증기록을보존한다.

롤백: ./develop -- git revert a848fb13923f369641889c384d45e4afac31062f 로이번두소스변경만되돌린다. 사람원문/검증기록/HTML/기존사진·패킷은보존한다. 열기요청 opening-status.txt,원격SHA remote-sync.json.

열기요청 macOS open exit0. 실제폰렌더/체크박스토글 미확인.
