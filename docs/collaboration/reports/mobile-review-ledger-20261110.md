# 응답 검증·재질문 방지·다음 묶음 — 2026-11-10

개발 진척78/100(usable-card-analysis-v1.13) 유지. 받은5건을 검증한 별도 검토 기록에 연결하고 다음화면에서 제외했다. 확대 사진 안의 실제 결함 여부를 점선과 무관하게 판단하도록 안내를 바로잡았다. 모델 성능 개선은 평가하지 않았다.

## 변경 파일·핵심 diff

- tools/diagnostics/mobile-point-review-20261110/manual.py: 원본 패킷/명시적 판정 범위/항목ID/사진SHA/기존 구역정답/중복/완료/판정값/null좌표/설명 검증. 원문 바이트 해시로 이름 붙인 배타 생성 receipt에 원문을 보존한다. 읽을 때 원문과 receipt 내용을 다시 대조한다. 같은 응답 재실행은 동일 파일을 반환하며 다른 사람 답으로 덮어쓰지 않는다. 선택전은 검토 완료로 세지 않고 모르겠음은 명시적 응답으로 유지한다.
- tools/diagnostics/mobile-point-review-20261110/manual_checks.py: 합성 경계 검사. ID/SHA/구역/범위/중복/기존완료 보호,CRLF 포함 원문 보존,재실행,충돌시미쓰기,수정된receipt거부.
- tools/diagnostics/mobile-point-review-20261110/scriptfree.py: 새 JSON에 scope=visible_defect_in_displayed_crop 추가. 다음 묶음을 만들 때 검증된 기존응답을 읽고 최대5건의 미검토만 고른다. render도 받은ID와 완료 위치를 제외한다. 점선 안팎과 무관하게 확대 사진의 실제 결함을 판단하도록 문구 수정. ‘미확인’ 후보 글자 세로 줄바꿈 방지. 한 번 복사하는 JSON/원본crop/전체사진 접기는 유지한다.
- tools/diagnostics/mobile-point-review-20261110/scriptfree_checks.py: 1024선택과 새 scope 대조,받은 항목 제외·사진 동일성 회귀 검사.
- docs/collaboration/tasks/mobile-review-ledger-20261110.md: 사전 범위/체크포인트.
- 이 보고서: 실측 실행 결과/한계/롤백.

## 실제 실행 근거

소스 e385568c30f562b01ebd31972775b48529cabbb4. ./develop -- .venv/bin/python tools/diagnostics/mobile-point-review-20261110/manual_checks.py 통과. 같은 경로의 scriptfree_checks.py 통과. 함수수manual4/manual_checks1/scriptfree2/scriptfree_checks2,CLI→ingest→load_reviewed→validate_manual→digest 호출전이4. 합성/정적 검사이며 실제 모바일 렌더나 학습 검사와 다르다.

manual.py --packet artifacts/mobile-point-review-20261110/packet.json --answers artifacts/mobile-human-response-20261110-batch02/human-response.json --ledger artifacts/mobile-human-review-ledger-20261110 --legacy-scope visible_defect_in_displayed_crop 를 develop 안에서 실행했다. 예전 JSON에는 scope가 없으므로 사용자의 앞선 점선무관 확인과 이어진 답변에 맞는 범위를 명시했다. 원문 SHA0a9d50c657658a82c6837f548fb104e9ddeeebf63fdf6adbf41c94495b88d9fd 동일. 명시적5건,기존 구역 라벨과 다른2건,정밀좌표0/모델후보확인0/학습반영0. 기존 원문·receipt·패킷을 덮어쓰지 않았다.

scriptfree.py 를 develop 안에서 실행해 artifacts/mobile-followup-review-20261110/review-next.html 생성. 받은5건을 제외한 미검토308건 중 아직 답을 받지 않은 첫5건(인덱스0..4)을 제공했다. 받은ID와 중복0. 원본crop/전체사진10개의dataURI는 기존review-01과 동일. 1024가지 전체선택 JSON 유지. 실제 생성본의 초기/모르겠음/결함 JSON3개도 manual validator 통과. packet8cca9f9bd206ac1ad04fe0ad395a71cfca47c43db3695ebbddf202979a1fad96 유지.

## 리스크·남은 사람 의존

이번5건은 확대 사진 어딘가에서 보이는 결함 여부다. 점선 안이 결함인지,정확한 위치인지,카드전체 상태인지는 확인하지 않았다. 이전 정상 라벨과 다른2건은 별도충돌로 보존하며 재학습/평가기준에 편입하지 않는다. 명확한 근거 없이 라벨을 교체하지 않는다. 다음은 새5건의 사람 응답이다. 이미 받은5건의 판정은 다시 요청하지 않는다.

CSS :has/복사 실제폰 동작은 아직 미확인이다. 미지원이면 수동 전체JSON fallback을 표시한다. 스크립트 없는 화면에서는 클릭점/정밀좌표/자동저장을 제공하지 않는다. 위치설명은 선택 후 마지막JSON에 적는다. 선택을 바꾸면 설명이 다른초안으로 자동이동하지 않는다. 기존 답은 원문 유지하고 새 좌표/모델후보 정답을 추정하지 않는다. 새학습·추론·모델/손실/threshold/성공기준 변경0. 정확도/일반화 개선 주장 없음.

## 롤백

./develop -- git revert e385568c30f562b01ebd31972775b48529cabbb4 로 도구4개 변경만 되돌린다. artifacts의 원문/검증기록/이전HTML/새HTML과 기존 사람정답은 보존한다. 검증기록을 삭제해 미확인으로 되돌리지 않는다. postflight.json/checks.log/status.html/opening-status.txt/remote-sync.json을 증거로 남긴다.

열기: macOS open exit0,요청수락. 실제 렌더/폰조작 미확인. 실제 다음파일5,606,513bytes.
