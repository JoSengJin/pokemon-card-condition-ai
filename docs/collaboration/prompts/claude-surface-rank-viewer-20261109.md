보관 상태: 사용자가 Claude에 전달하지 못해 Codex가 viewer 구현을 인수했다. 이 프롬프트를 새로 실행하지 말고 docs/collaboration/tasks/claude-surface-rank-viewer-20261109.md의 현재 소유권을 확인한다. 아래는 이전 인계 기록이다.

다음 작업을 Claude 페어코딩 구현으로 맡아줘. 계약·좌표보완 포함 기준 커밋은 2cd12bb1975c5d5374b2b3a14ac5cf176246d32c다. 이 SHA로 별도 worktree를 만들고 고정해라. AGENTS.md·PAIR_CODING.md와 docs/collaboration/tasks/surface-rank-partition-20261109.md의 고정 JSON schema를 먼저 읽어라.

목표: Codex가 만드는 rank_report.json을 읽어 오순위 사진쌍을 검토하는 정적 HTML 생성기를 구현한다. Codex는 별도 analysis.py/worker.py/checks.py를 개발 중이므로 그 파일을 수정하지 않는다.

배경/고정 사실:
- 현재 main 기준58ad67d, 개발진척78/100v1.13. α0 대조는1776구역/370결함/1406정상/204사진group, FN57/370 FP167/1406 AUC0.931924954826804.
- 3×3국소대비 추가는 AUC0.925992849로악화,정상거리 추가는0.931325209·직접α0차95%[-0.002628454,+0.001217494]로개선미확인. 둘다운영미채택.
- 손실가중치/α/threshold0.5/라벨/분할/대조/성공기준고정. 중간층/백본확대/해상도/미세조정/정규화/crop평균제거/국소대비/정상거리의실패변형을반복하지않는다.
- 다음표현을지금학습하는작업이아니다. 저장OOF점수의오순위를same_photo/cross_photo_same_fold/cross_fold로분해하는진단이며,이분해자체는인과/일반화/성능향상증명이아니다. cross_fold는서로다른학습head의score비교라는한계가있다.

실행 위치/권한:
1. main에직접편집하지말고전용branch/worktree를만들어라. task/schema가포함된계약커밋을base로고정하고docs/collaboration/tasks/claude-surface-rank-viewer-20261109.md에전체base SHA를기록한다. 사용중인기존worktree는재사용/삭제하지않는다.
2. 허용파일은신규 tools/diagnostics/surface-rank-viewer-20261109/{render.py,checks.py,fixture.json},위Claude task뿐이다. Codex디렉터리/공유계약/모델/원본자료/평가기준/다른task/.claude/는편집금지.
3. 소스편집은 ./develop -- <수정명령> 안에서만한다. 자체환경/잠금확인,함수수7이하·호출전이4이하. 실제data/artifacts/venv/비밀설정을기본checkout에서복사하거나링크하지않는다.
4. 실제학습/사진추론/통계fit/./experiment/./review/모델CLI/API/자동하위에이전트 호출금지. 합성검사만한다. 별도요청없이main에merge/push하지않는다.

구현:
- 표준라이브러리Python CLI: python render.py --input rank_report.json --output report.html. 외부의존성/JS/CDN/서버/범용프레임워크없음.
- 입력schema는고정task의rank_report.json v1을그대로따른다. total/buckets에는pairs,strict_inversions,ties,error_credit,auc,loss_share가있다. AUC는1-error_credit/pairs,동률0.5,빈bucket auc=null이다.
- photos에는group/fold/image/image_sha256/zones,zone에는id/area/normalized box/target/score/prediction/outcome이있다. examples에는bucket/defect_id/normal_id와두score/margin이있다.
- 첫화면에저장점수진단·새학습/추론0·독립평가아님·개발진척78/100(고정관리점수)을표시한다. AUC/쌍분모/오순위credit과FN/FP구역분모를혼동하지마라.
- 3bucket요약에서 전체쌍비중(pairs/total.pairs)과오순위비중(loss_share)을함께표시해큰bucket이라는이유만으로문제집중을주장하지마라. 전체사진구역overlay/표,최대15개오순위사례의두사진/관련구역/사람정답/score/fold/margin을표시한다. 구역박스를사람결함점이나최고patch로부르지않는다.
- raw이미지경로는실제ignored HTML에만쓰며Git fixture에실제사진/정답/개인경로를넣지않는다. 입력문자열HTMLescape·출력HTML기준상대사진경로를검사한다. 합성사진이없으면missing을명시한다.
- 합성fixture로tie/auc=null/escaping/상대경로/동일사진의두zone/다른fold사례와함수수/호출경로를검증한다. 실제사진렌더는미검증으로적는다.

인계:
- 전체commit SHA,base SHA,변경파일,핵심diff,함수수/호출경로,실행한합성검사/미검증,리스크/롤백을task와최종응답에제공한다.
- schema문제나새근거가있으면정확한파일/행을제시하고Codex에전달할질문으로남겨라. 없는근거로원인을추정하거나schema를독자변경하지마라.
- 결과를보고threshold/계수/성공기준을바꾸거나추가실험하지않는다.

좌표 검증 보완: 실제 저장 box9개가 경계에서1.0000000000000002다. normalized0..1 검사에는1e-12 허용오차를 두고 원본 좌표를 변경하지 마라. 사진 밖 SVG 표시만 clip할 수 있다. 합성fixture에도 이 경계 사례를 포함해라. 고정schema의 필드/버전은 같다.

Codex 완료 진단(새 학습/추론0, viewer 개발과 독립):
- 공통기록 artifacts/experiments/20261109T123217-c4241d83/record.json completed/exit0.
- 실제입력 artifacts/experiments/20261109T123217-c4241d83/rank_report.json. 이 파일/사진은 기본checkout의ignored증거이므로 자기worktree로복사/링크하지말고 schema만보고합성fixture를만들어라. 실제입력검증은반환후Codex가담당한다.
- 전체520220쌍/35414오순위/동점0,저장AUC0.931924954826804 재현.
- same_photo:1520쌍/173오순위/AUC0.886184211,전체쌍비중0.2922%/오류비중0.4885%.
- cross_photo_same_fold:100493쌍/6923오순위/AUC0.931109630,쌍비중19.3174%/오류비중19.5488%.
- cross_fold:418207쌍/28318오순위/AUC0.932287121,쌍비중80.3904%/오류비중79.9627%.
- 전체AUC는조건부AUC의단순평균이아니다. cross_fold의오류수가많다는사실만으로calibration원인확정금지. 같은사진오류만직접없애고다른쌍은불변이라는산술가정의전체AUC상한증가는0.000332552이며실제훈련예측이아니다.
- 15examples는bucket별최대margin5쌍씩,대표성/인과/훈련선별주장금지.
- Codex진단구현은이미완료됐다. Claude범위는별도viewer/합성검사이며새진단알고리즘·모델학습을추가하지않는다.
