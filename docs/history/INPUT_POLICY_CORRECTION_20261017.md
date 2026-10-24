# 엣지 연구 입력 정책 설명 정정

최근 연구script에서 patch_features(..., edge_views=True)를 사용했지만 계획/문서에 context+4tiles max로 잘못 기재했다. 실제 card_condition/edge_views.py는 True일 때 edge_view_boxes로 바깥 경계띠를 만들고 그 평균 특징을 전체 구역 평균 특징과 concatenate한다. 4tile max는 문자열 'tiles'다. 실제 전후 같은True로 실행되어 수치 비교 자체는 유지하지만, 아키텍처 설명은 철회한다.

대상: alakazam-edge-learning, alakazam-back-learning, gengar-edge-learning, gengar-corner-learning, gengar-normal-edge 20261017 연구폴더. 원시 계획해시·실행script·결과를 덮어쓰지 않고 각input-policy-correction.json 및HTML배너를 추가했다. 이전관련VALIDATION 문서의 RGB4tile 설명은 이 문서로 정정한다. 표면 mean224 실험에는 해당하지 않는다.

gengar-normal-edge 전후 연구모델을 각각 앞뒤별 mobilenet_v3_small_point_edge_views_v1/edge_input=views로 내보냈다. 기존 RegionAnalyzer.policy True·input_policy views를 확인했고, full-train fit 계산과 API점수183개(후)/182개(전)가 각각 최대1.1921e-7 차이로 일치했다. 이는 실행 경로 일치 검증이며 학습자료 정확도나 독립 일반화 증거가 아니다. side는 호출자가 명시적으로 선택한다. 운영모델은 변경하지 않았다.
