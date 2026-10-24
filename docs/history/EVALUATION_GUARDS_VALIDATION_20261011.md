# 최종평가 입력 보존 검증 — 0.4.66

## 결과

기존 면·구역 평가가 서로 다른 실물에 같은 사진을 배정하거나 평가 도중 사진/모델/manifest/개발 이력을 바꿔도 성공 보고서를 저장하던 경로를 차단했다. 모델 성능 개선 실험이 아니라 평가 신뢰성 수정이다.

## 변경 파일·핵심 diff

- card_condition/evaluation_inputs.py: 요청 안에서 파일 SHA 추적, 디코딩 픽셀의 실물 group 충돌 검사, 저장 직전 변경 검사.
- card_condition/region_evaluation.py·side_evaluation.py: 평가 사진과 개발 이력까지 검사 연결, 보고서에 input_hashes·종류별 오류율 추가.
- tests/test_evaluation_inputs.py: 정상 출처 기록, 동일 픽셀의 다른 실물 배정, 추론 중 4종 입력 변경을 두 평가기에서 검증.
- pyproject.toml·README.md·본 문서·마스터 TODO 및 artifacts/evaluation-guards-20261011/.

## 실행 증거

137테스트 통과(41.305초), 저장소 밖 설치본 관련5테스트 통과(1.659초), wheel Python/HTML52파일 byte 일치. 재현 스크립트는 이전 코드와 현재 코드에 같은 임시 파일을 사용해 10개 잘못된 성공을 10개 거부로 바꿨다. 이 재현의 추론기는 파일 변경을 주입하는 mock이며 실제 카드 정확도 시험이 아니다. 기존 실제 임시 모델 학습 평가 테스트도 별도로 통과했다.

artifacts/evaluation-guards-20261011/reproduction.json·checks.json·reproduce.py 참조. 실제 독립 정확도 미측정, 운영 Gemini 절감0건.

## 리스크·롤백

평가 시작/종료 해시 검사만큼 파일 I/O가 늘어난다. 사람이 같은 실물을 서로 다른 group에 기록한 다른 사진까지 자동 판별하지 않는다. 고의적인 동시 변경에 대한 원자적 파일시스템 잠금은 제공하지 않는다.

후속 수정 유무를 확인한 뒤 .backups/evaluation-guards-0466/의 기존 두 평가기·pyproject.toml을 복원하고 신규 evaluation_inputs.py·해당 테스트를 제거한다. 이후0.4.67은 이 검사에 의존하므로 함께 되돌려야 한다. 사진·라벨·모델·운영 서비스는 수정하지 않았다.
