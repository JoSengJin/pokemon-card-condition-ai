# 최종평가 실물별 오류 집계 — 0.4.68

## 성과와 변경

구역/point 최종평가 보고서에 by_group·by_group_side 혼동행렬 및 group_error_rates_at_05를 연결했다. 기존 검증 비교에서 사용하던 group_error_rates 함수를 재사용하며 새로운 임계값 탐색은 하지 않는다. 전체 rates_at_05는 구역 수 기준이고, 새 지표는 정답 클래스가 존재하는 실물의 오류율을 동일 가중 평균한다. 알려지지 않은 라벨을 정상으로 채우지 않는다.

변경 파일: card_condition/region_evaluation.py, tests/test_evaluation_inputs.py, tests/test_point_final_evaluation.py, pyproject.toml, README.md, 본 문서, 마스터 TODO, artifacts/final-group-rates-20261011/checks.json. PokeCollector 실행 코드·사람 라벨·모델은 수정하지 않았다.

## 검증

전체139테스트 통과(43.066초), 저장소 밖 설치본 관련7테스트 통과(3.364초), wheel52개 Python/HTML파일 소스 byte 일치. 정상 구역2개인 카드의 FP1개와 정상 구역1개인 카드의 FP1개를 구성해 전체 오탐률2/3과 실물 평균(.5+1)/2=.75가 서로 다른 값임을 확인한다. 이 수치는 집계 검증 fixture로 실제 카드 성능이 아니다.

실제 임시 tiles 모델 학습 후 test2실물/앞뒤4구역에서도 그룹·면별 혼동행렬 합계가 전체 합계와 일치한다. 양성/음성 실물 각각1장으로 기록되고, 해당 클래스가 없는 실물은 그 클래스 분모에서 제외된다. source/live/선택 모델 해시 불변은 checks.json 참조.

개발 기반4/6단계(67%) 유지, 실제 독립 정확도 변화 미측정·모델 변경 없음·Gemini 절감0건. 테스트 통과 수나 개발 진척을 AI 정확도로 해석하지 않는다.

## 리스크·롤백

보고서에 부가 필드만 추가한다. 두 지표는 분모가 달라 평균 차이를 모델 개선으로 비교할 수 없다. 그룹은 사람이 지정한 실물 단위이므로 다른 실물 묶음이 잘못되면 평균도 왜곡된다. 큰 보고서에서 실물·면별 집계만큼 JSON 크기가 늘어난다.

후속 수정 여부를 확인한 뒤 .backups/group-final-0468/의 region_evaluation.py·두 테스트·pyproject.toml·README.md를 복원하면0.4.67로 돌아간다. 기록 artifacts는 보존 가능하다. 사람 라벨·모델·운영 서버 롤백은 불필요하다.

에튜: 평균에는 가중치가 숨어 있다. 사진이 많은 카드가 평균을 지배하지 않게 하려면 카드별 비율을 먼저 구한 뒤 평균한다. 여기서는 전체 구역 오류와 실물별 오류를 함께 남겨 두 관점을 구분했다.
