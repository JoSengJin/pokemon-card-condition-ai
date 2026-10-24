# 오류 검토 도구

error-review manifest report output 명령으로 val 오류 사진과 불일치 항목을 표시하는 독립 HTML, 원인/reviewer/notes를 작성할 CSV, 출처 해시 receipt를 생성한다. 원본 라벨과 기존 서버는 수정하지 않는다. 최종평가 보고서, 다른 manifest 해시, 라벨/ID 불일치는 거부한다. 화면 이미지는 축소되어 원본 확인이 필요할 수 있다. CSV는 수동 기록용이며 자동 학습 반영 기능은 없다.

변경: card_condition/error_review.py 신규, card_condition/cli.py 명령 추가, tests/test_error_review.py 신규, 이 문서 및 PokeCollector TODO. 테스트22개 통과. 실제 balanced-30epochs 보고서로 artifacts/error-review-20261008 생성. receipt.json에 사진/오류 수 기록. 브라우저 상호작용 검증은 미실행이며 생성·이미지 포함·파일 보호 검증 완료.

기술 도입 검토 조건:
- OpenCV: 사람이 기록한 오류 원인에서 원근/경계 문제가 반복되고 정확한 네 꼭짓점을 확보하면 보정 비교 실험.
- PyTorch 부분 미세조정: 라벨 일관성 확인 후 고정 특징의 일반화 격차를 개선하는 비교 실험. 기존 의존성으로 가능.
- timm: torchvision 후보/부분 미세조정 비교 후에도 목표 미달이고 모델 특징 변경 근거가 있을 때.
- scikit-learn: 결함별 PR/임계값 비교가 필요할 때 평가 도구로 검토. 설치 자체가 정확도를 높이지 않음.
- FastAPI/Pydantic: 독립 프로세스 계약 필요 시. Docker: 배포 재현 필요 시. Mastra: 기존 worker로 처리하기 어려운 다중 서비스 흐름 확인 시.

현재 추가 라이브러리 도입 근거는 미확정. 이후 개발의 오류 검토 시 위 조건을 확인하고 충족하면 사용자에게 알린다. 별도 백그라운드 감시는 설정하지 않았다.

리스크: HTML에 사진이 포함되므로 파일을 공유하면 사진도 공유된다. 불일치는 사람이 틀렸다는 의미가 아니다. 출력은0.5 기준이며 자동 점수/운영 판정에 사용하지 않는다. 롤백: .backups/step11/cli.py 복원, 신규 error_review.py/test_error_review.py 및 산출물 폴더 제거. 원본 데이터 롤백 불필요.
