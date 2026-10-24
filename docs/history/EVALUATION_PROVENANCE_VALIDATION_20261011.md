# 평가 근거 없는 성공 저장 차단 — 0.4.69

## 성과

면 평가가 지원 정답0건인데 성공 보고서를 저장하던 문제를 실제 임시 학습 모델로 재현하고 수정했다. 일부 정답만 알려진 경우 해당 분모만 집계하며, 한 클래스가 없을 때 그 클래스 오류율은null로 유지한다.

면/구역 평가의 개발 이력은 키 존재만 검사하거나 set()으로 바로 변환해 빈 배열·문자열·사전·빈 ID·None을 수용했다. 공통 development_sets 검사로 비어 있지 않은 문자열 목록 및64자리 소문자16진수 이미지 해시를 요구하고, 추론 이전에 오류를 반환한다. 구역 평가의 모델 생성은 이력/자료 검사 뒤로 이동했다.

## 변경 파일·핵심 diff

- card_condition/side_evaluation.py: 지원 정답0건 거부, 개발 이력 검사 연결, 비사전 checkpoint 오류 처리.
- card_condition/region_evaluation.py: 공통 개발 이력 검사와 추론 전 검증 순서 연결.
- card_condition/evaluation_inputs.py: development_sets 추가, 기존 파일 보존 검사 유지.
- tests/test_side_evaluation.py: 실제 임시 학습 모델의 빈 정답 final/regression 거부 및 부분 정답1건 집계.
- tests/test_evaluation_inputs.py: 개발 이력 잘못된 형식40경우 거부, 추론기 미호출·성공 파일 미생성 검증. 기존 정상 fixture의 개발 이력을 유효한 형식으로 갱신.
- pyproject.toml·README.md·본 문서·마스터 TODO·artifacts/evaluation-provenance-20261011/.

## 실행 증거

수정 전 실제 임시 면 모델 테스트에서 ValueError 미발생·성공 파일 생성을 확인했다. 잘못된 이력30경우도 기존 평가기에서 수용됨을 확인한 뒤 수정했다. 현재 전체141테스트 통과(43.952초). 저장소 밖 설치본 관련9테스트 통과. wheel Python/HTML52파일 소스 byte 일치.

reproduce.py는 백업한 이전 두 평가기와 새 평가기를 같은 임시 파일로 비교한다. 빈 개발 이력6경우와 빈 정답1경우 모두 이전 성공→현재 거부/보고서 미생성이다. 이7사례의 추론기는 mock이며 실제 카드 정확도 측정이 아니다. 실제 임시 모델 학습 테스트를 별도로 실행했다.

현재 선택한 point tiles 모델, 기존 region 모델, 기존 single_side 모델의 개발 이력3개는 새 검사에 통과했다. 상세 목록/원본 SHA는 checkpoint-compatibility.json. source/live/선택 모델 해시 불변은 checks.json.

## 성능과 남은 의존성

개발 기반4/6(67%) 유지·선택 모델 변경 없음·실제 독립 정확도 미측정·Gemini 절감0건. 이번은 평가 무결성 개선이며 AI 정확도 상승으로 보고하지 않는다.

현재 상단 TODO의 앞면 nested 실험은 학습 반사 실물2장 때문에 필요한 fold가 성립하지 않는다. 독립 최종평가는 미사용 test0장 때문에 실행할 수 없다. 사용자의 추가 사진 없음 답변을 유지한다. 완료 라벨을 재요청하거나 기존 val/train을 test로 옮기거나 동일 입력을 반복 재학습하지 않는다.

## 리스크·롤백

빈/손상된 개발 이력이 있는 구형 모델은 이제 평가에서 거부된다. 이력을 추정해 채우지 말고 실제 학습 기록을 복구해야 한다. 형식 검사만으로 개발 이력이 완전하거나 동일 실물 그룹이 정확함을 보증하지 않는다. caller의 전체 history 제공 요구는 유지한다. 추론 API와 운영 fallback은 변경하지 않았다.

후속 변경 유무를 확인한 뒤 .backups/side-scoring-0469/의 side_evaluation.py·region_evaluation.py·evaluation_inputs.py·두 테스트·pyproject.toml·README.md를 복원한다. 사람 라벨/원본/모델/서버는 바꾸지 않아 별도 데이터 롤백이나 서버 재시작은 필요 없다.

에튜: 검증 함수는 ‘값이 존재한다’와 ‘의미 있는 값이다’를 구분해야 한다. set(빈 문자열)은 오류 없이 빈 집합이 되므로, 누수 검사를 하기 전에 문자열 목록인지·비어 있지 않은지부터 확인해야 한다.
