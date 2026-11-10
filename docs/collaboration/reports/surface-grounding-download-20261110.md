# 검토 JSON 파일 저장 보완 — 2026-11-10

개발 진척78/100(usable-card-analysis-v1.13) 유지. 검토한 답을UTF-8 JSON파일로저장해채팅에첨부할수있도록보완했다. 새학습/추론/사람답/성능평가0,기존모델·구역정답·packet·응답schema·품질기준 불변.

- 검증소스SHA `7eb2636ba380057a06857aa0ec2bf5eab4dd4e2a`.
- 신규검토URL `artifacts/surface-grounding-download-20261110/report.html`. 기존열린화면/HTML/동결재생runtime/snapshot/packet은변경하지않았다.
- 사용: 각항목「이 설명 기록」→「JSON 파일 저장」→내려받은.json파일을이채팅에첨부. 일부만검토해도된다. 예시파일명 `surface-grounding-397ed4fb79b6-1.json`;묶음접두어와기록수를포함한다. 기존JSON복사/가시적textarea/저장한설명불러오기기능유지. 기존화면에서입력중이었다면그화면의JSON을복사해채팅에직접제공할수있다.
- 미기록항목을응답으로채우지않는다.0답에서는download link비활성. 실제기록된동일export를검증한후Blob/objectURL로저장한다. 기존objectURL은다음변경시해제하고현재URL은다운로드가끝날수있도록유지한다. 서버/업로드/새저장소/의존성추가0.
- 변경파일5개: `tools/diagnostics/surface-grounding-20261110/review.js`,동일폴더`report.py`,`review_checks.cjs`,새task/이report. 핵심diff는refreshExport10줄·native다운로드링크/사용안내·실제Blob payload테스트이며새eventhandler/추상화없음.
- 검증: 기존합성Python/Node검사통과;NodeVM에서실제refreshExport와nativeBlob/objectURL/fetch로UTF-8 답/원문메모/packetID/file명/기록수일치·0답비활성·이전URL해제를확인. Javascriptproduction7함수,Pythonreport3,Nodechecks5정의,새project전이max3. `checks.log`.
- 실제HTML313사례/동일packet전체1776행·다운로드anchor1개·사진경로·내장JSON일치,이전HTML/packet SHA불변,원공통재생runtime소스해시불변을검증했다. postflight.json에SHA/범위보존. 새실험은실행하지않았으며과거공통record20261109T234706-4aeb730c를새성능근거로바꾸지않았다.
- 동일host OSopen exit0로열기요청성공,실제렌더/브라우저다운로드는미관찰. file콘텐츠관찰보안정책우회0. 원래313선택/147사진과370/1406정답·기존성능은그대로이며성능개선주장없음.
- 위험: 브라우저별저장동작차이,새로고침전미저장입력유실. JSON복사fallback/새주소로기존창보호/저장안내를유지했다. 기존화면의메모리입력을자동이전하거나보존됐다고추정하지않는다.
- 롤백:후속의존확인후 `./develop -- git revert 7eb2636ba380057a06857aa0ec2bf5eab4dd4e2a`,일반push. 이전검토화면/packet/모델은그대로라복구불필요. 기록·사람답삭제없음. 원격SHA확인은remote-sync.json,기존.claude/다른worktree불변.
