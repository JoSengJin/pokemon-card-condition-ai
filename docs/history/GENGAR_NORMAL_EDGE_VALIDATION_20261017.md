# 팬텀 하단 중앙 정상 확인과 연구 모델 고정

사용자 ‘하단 중앙만 정상 우측상단은 비정상’을 review_drafts의 기존 승인 저장 경로로 영속화했다. back lower_center edge0만 새 학습 구역이며 upper_right edge1은 이미 저장된 점과 중복되는 정답이다. 기존7점/앞면/좌표/기타미확인 불변. 다른 구역은 정상으로 확장하지 않았다. 팬텀 검토는 완료로 기록했다.

같은기존182 엣지구역(양성84/음성98) 실물제외 개발 비교: FN34→33/84(40.48→39.29%, -1.19%p), FP44/98(44.90%, 0%p) 유지. 정확도57.14→57.69%(+0.55%p). 새누락0·새오탐0·회복1(ㅋ-5/back/point/2). 새정상1구역은 위분모에서 제외하고 별도 표기(.3292 정상). 같은팬텀 전체제외라 기존팬텀2결함점의 예측이1e-5미만으로 불변임도 assert. 새팬텀 엣지2점은 여전히 누락이며 한구역 개선을 전체문제 해결로 보지 않는다. 연구 기준 통과·독립 일반화 개선 미확인·운영교체0·기반4/6 유지.

모서리3점은 별도로 같은기존48구역(양성30/음성18)에서 고정 경계띠 특징/앞뒤logistic을 비교했다. FN7/30(23.33%)·FP14/18(77.78%) 동일·새오류0·개선0. 새팬텀 모서리는1/3검출. 이 실험은 연구 대조이며 운영모서리 모델 성능으로 보고하지 않는다.

입력 정책 표기 오류도 정정했다. 실제 edge_views=True는 전체구역+바깥경계띠의 평균 특징이며, 4tile이 아니다. 기존 실행/계획/결과는 해시 보존 후 별도 정정기록과 HTML배너를 추가했다. INPUT_POLICY_CORRECTION_20261017.md 참고.

코드 변경: card_condition/ebay_dataset.py collect에 reference_learn 읽기전용 과거사진 저장소 추가. tools/collect_ebay_dataset.py에 --reference-learn 전달. tests/test_ebay_dataset.py에 과거매물ID/재판매동일사진 차단 및 참조원본무변경 회귀 추가. 기존 collect 호출은 기본값으로 호환 유지. 실제19테스트 통과.
산출물: gengar-normal-edge의 정상승인근거/계획/combined-reviewed/result/run/index 및 앞뒤research-model.pt/export_verify.py/api-verification.json. gengar-edge-learning의 전 모델도 API형식으로 별도 내보냄. 승인과 비교의 원본/행/실물/사진해시/수렴/계획해시 검증. RegionAnalyzer 실제후183/전182구역 점수차<=1.1921e-7·requires_gemini 유지·production_ready false·side수동dispatch 확인. API검증은 fit점수일치일 뿐 heldout성능이 아니다.

다음 확인: 수집기로 새고우스트·피카츄2매물4사진 확보(Gemini0). 새사진은 프로젝트내부저장, 과거learn은 중복검사만 읽음. 앞뒤 실제 원본을 Codex가 직접 선별해 test 후보로 분리, 추론전 전후모델4개와사진해시를 frozen-plan.json에 고정. 사진의decodedpixel/ID와모델development이력 교집합0 검증. 다른촬영의동일실물 가능성은 완전배제할 수 없어 독립실물확정이라고 주장하지 않는다. 상태정답null·첫추론미실행·모델선택금지. 8796에서 뒷면영역·확인된엣지8구역만 휴먼인루프 대기. 완료후딘/팬텀재요청0.

리스크: 한정상구역·반복개발검사에서1곳 회복. 표기 오류가 있어 원시계획과 실제코드를 함께 봐야 한다. 연구checkpoint는앞뒤전용으로호출자가선택해야한다. 호출기본Gemini0유지. 새사진은실물독립성미확정·소표본.
롤백: out/ebay_dataset.before-reference.py·collector.before-reference.py·test_ebay_dataset.before-reference.py를 해당소스로 복원하면 reference변경을되돌린다. 연구checkpoint는운영미적용이며삭제/격리해도 운영에영향없음. 사람정답은실험실패를이유로되돌리지않는다. 소스파일추가변경이있으면백업으로일괄덮어쓰지말고해당diff만복원한다.
