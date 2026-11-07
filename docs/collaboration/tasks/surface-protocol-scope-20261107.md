# surface-protocol-scope-20261107

owner: Codex
status: ready_for_review
base_sha: 819ca70bde57728e26b0c83507b318dc2853ad9b
branch: main
goal: 1791개 개발 구역의 규약 적용 근거 미확정 목록과 제외 목록을 누락/중복 없이 산출한다. 라벨 일관성 자체의 완료와 구분한다.

allowed_files:
- docs/collaboration/tasks/surface-protocol-scope-20261107.md
- docs/collaboration/reports/surface-protocol-scope-20261107.md
- docs/collaboration/reports/surface-protocol-scope-20261107.html
- ignored artifacts/surface-protocol-scope-20261107/ 신규 감사 산출물

forbidden_files: 모든 기존 사람답/라벨/사진/선택/가중치/학습·평가·worker·운영소스/PokeCollector/fallback/진척기준/다른 작업 파일. 새 학습·실험·추론·외부 모델 호출·자동 review 금지.

contract: 값의 일치와 실제 규약 적용 근거는 다른 축이다. §97의 사용자 화이트닝 기준 확인은 해당 완료259개에만 한정, 현재 안내에서 받은1개 추가답 완료. 불가15개는 제외로 보존. 원답만1249, §93 일치228, 불일치39는 규약 적용 미확정1516개. 사용자 원답 유지 선택267개를 번복/재요청하지 않는다. 재라벨 개수는 미정이며1516개 재요청으로 바꾸지 않는다.

structure: 신규 추적 소스 없음. ignored audit.py는 함수4개(read/original_answers/classify/main), 주요 프로젝트 자체 경로 main→original_answers→read 최대2전이. 기존 실행기/모델의 호출경로 변경 없음.

checks: 합성 assert8경로, 분류합1791·ID분리·누락0, 원답 target/box/9칸 좌표 전수 일치1791, 원 안내32개·동일문장1종·면 위 화이트닝 미명시 확인, §93 scope267/외부3·일치228/불일치39 검산, 기존입력117+원대화3=120파일 SHA불변, 신규 실험record0. HTML미확정1516행·불일치39구역/16사진 표시. 새 모델점수/예측/라벨입력폼 없음.

experiment: 실행 금지. 일관성 확보 내역 보고 전에는 계획 작성/재학습/자동 review하지 않는다. training-gate.json은 사람 지시 인계이며 새 실행기 강제차단 기능을 구현했다는 뜻은 아님.

handoff: 감사목록 작성 완료, 추가 원대화에서 공통 확대/화이트닝 기준과 안내 준수에 대한 기존 답3개 확인. 같은 질문을 다시 하지 않는다. 먼저 기존 화면→답→배치/구역ID의 적용 연결 근거를 보강하고, 확인되는 원답은 그대로 제외한다. 사람이 판단할 구체 범위가 남을 때만 그 부분의 확인이 필요한지 판단한다. 값 선택을 다시 묻지 않음. 사진 HTML artifacts/surface-protocol-scope-20261107/report.html 열기/렌더 결과 및 원격동기화는 후속 기록. 전체테스트/실사진 재판정/성능평가 미실행.

rollback: 이번 신규 문서 커밋만 git revert 후 일반push. ignored 근거는 이력으로 보존. 기존 라벨/모델을 바꾸지 않아 데이터 복구 없음.

HTML 파일 열기 요청 queued, 실제 표시/렌더 미확인. 기존 브라우저 정책 우회 없음. 원격 반영 전 git diff --check·보존입력SHA·허용파일 대조를 재확인한다.

추가 원문 근거 historical-user-evidence.json(ignored)3개: 확대 판정/표면화이트닝 결함/제시 안내 준수. 공통 기준을 재질문하지 않음.1516개는 개별 적용 연결 근거가 부족한 범위이며1516개 재라벨 대상이 아님.

원답1791개를6개user원문에 연결 완료(1783원문카드전체일치+8개승인규칙전카드의상태/box일치). 실제 짧은 채팅/HTML 상충은 ad~ah1076개에서 발견; 재요청제외130개를 뺀946개를 우선 적용 미확정으로 분리. 나머지570개는 직접 채팅충돌 없이 보존/추가근거대조.1516총수 유지.

최종 검증: artifacts/surface-protocol-scope-20261107/verify.py 통과(1791 ID/미확정1516=안내상충946+근거대조570/재요청제외275/원답user원문6개/120파일 불변). 모델 소스 변경 및 모델 호출0. 감사목록 정리 완료이며 일관성 자체는 미완료, 재학습 금지 유지.
