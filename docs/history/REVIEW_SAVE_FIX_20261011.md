# 0.4.77 영역 확인·저장 버튼 수정

브라우저 오류 로그에서 clearFieldErrors → refreshAggregateWarning의 null.textContent 예외를 확인했다. clearFieldErrors가 모든 .field-error 요소를 삭제하면서 영구 aggregate-warning과 결함점 경고까지 제거했다. 이벤트가 dirty=true·buttons()에 도달하지 못해 저장이 비활성으로 남았다.

변경 파일: card_condition/review.html, tests/review_validation.test.cjs, pyproject.toml, README.md, 본 문서, artifacts/review-save-20261011/saved-fixture.png, 소비 프로젝트 CONDITION_ANALYSIS_TODO.md.
핵심 diff: 일시 검증 메시지 #field-error-message만 제거한다. geometry URL에 image 생략 시 선택 사진으로 시작하되 명시한 image가 다르면 거부한다. 기존 train-only 큐·저장 검증·정답 계약은 보존한다.

검증: JS 회귀에서 영구 경고를 삭제하려 하면 실패하는 DOM stub 검사와 geometry 링크5경계 통과. Python review7테스트1.212초 및 전체150테스트47.750초 통과. 임시 복사본8769에서 실제 브라우저 영역 체크→저장 활성화→저장 성공, 오류 로그0. 저장 후 파일 대조에서 box_reviewed 한 값만 변경됐음을 확인했다. 실제 data/chieut-review-20261011.jsonl SHA는 사용자 확인 직후와 동일, 기존 입력 라벨 불변.

사용 화면8768을 수정 소스로 다시 열어 light 영역 확인 모드가 바로 열리는 것을 확인했다. 이전 탭은 연결 당시 이미 닫혀 있어 저장 전 브라우저 입력을 추출하지 못했다. 디스크에 저장된 라벨은 보존됐으나 이전 미저장 입력 복구를 주장하지 않는다. 임시 복사본만 저장했으며 실제 사용자 영역 확인 정답은 대신 입력하지 않았다.

리스크: 수정 전 탭은 오류가 난 이전 JS를 계속 사용하므로 새 화면 필요. 전체 AI 정확도 변화 없음·개발 기반67%·Gemini절감0. wheel 재빌드는 미실행.
롤백: .backups/review-save-0477의 review.html/review_validation.test.cjs/pyproject.toml을 대응 경로에 복원한다. 사용자 데이터 롤백은 필요 없다.

에튜: CSS 클래스는 표시 목적이고 삭제 수명주기는 별개다. 같은 빨간색 경고라도 영구 안내와 임시 검증 메시지를 동일 클래스로 일괄 삭제하면 이벤트 처리까지 깨질 수 있다.
