# 앞뒤 대표 기준 분리 검증 — 0.4.46

사전 계획 SIDE_CENTROIDS_PLAN_20261011.md. 같은576차원·box·이미지·라벨·0.5판정에서 train centroid만 front/back별로 분리했다. 기본 꺼짐, 면을 추론 입력으로 명시해야 한다.

| 지표 | 기존 공통 centroid | 앞뒤별 centroid |
|---|---:|---:|
| 관찰 제한 FP/FN | 7/4 | 2/3 |
| AUROC | .487395 | .873950 |
| AP | .426233 | .775733 |
| 균등 BCE | .698560 | .689083 |
| 같은 FP예산7의 최대 TP(사후) | 3 | 7 |

사전 연구 채택 기준을 통과했다. 운영 승인은 아니며 기본 모델/Gemini 호출 경로는 유지한다. 실제 호출 절감0건. 같은24면을 반복 개발에 사용해 독립 일반화나 통계적 우위를 주장하지 않는다. 낮은 점수도 사람의 관찰 제한 라벨을 덮어쓰지 않는다.

면별 val: front13면/13실물 FP1/FN2·AUROC .861111, back11면/11실물 FP1/FN1·AUROC .875000. 전체14실물이다. train front25면(명시적 비제한20/제한5), back21면(12/9). 앞뒤 면별 수를 더해 실물 수로 해석하지 않는다. 제한과 비제한 양쪽 자료가 없는 면은 fit 전에 거절한다.

변경: visibility_model.py(선택 side_aware·면별 train centroid·명시적 side 검증·면별 진단), cli.py(--side-aware, visibility-predict --side), tests/test_side_centroids.py 신규3개, pyproject.toml0.4.46, README·본 문서·TODO. 0.4.45의 표준화 후보와 혼합하지 않는다. 기존 단일 head checkpoint는 기존 방식으로 동작한다.

검증: 전체100테스트, 후보·복귀 모델 각24면 MPS 재추론 최대차이0.0, source/사진/live/합의문/기존 모델 SHA 불변, wheel39파일 소스 바이트 일치. 근거 artifacts/observation-side-centroids-20261011/report.json·comparison.json·recovery.json·verify.py.

리스크: front/back 출처가 틀리면 잘못된 기준이 적용될 수 있다. 따라서 side를 추측하지 않고 명시하지 않으면 fallback을 요청한다. 점수는 교정된 확률이 아니며 앞뒤의 미세한 점수 차이를 상태 차이로 읽지 않는다. 모델이 무늬를 제한으로 오인할 가능성은 남아 있다.

롤백: --side-aware 생략, 기존 artifacts/observation-geometry-20261011/model.pt 사용. 코드 복원은 .backups/side-centroids-0446의4파일을 원위치로 복원하고 tests/test_side_centroids.py만 제거. 완료 라벨·실험 기록은 보존한다.

다음: train 실물 단위 leave-one-group-out 진단으로 한 실물을 통째로 빼고 공통/면별 기준을 대조한다. 기존 val/test는 읽지 않고, 후보의 새 임계값이나 재학습 epoch을 선택하지 않는다. 이 진단도 이미 개발에 쓰인 train 자료이므로 최종 성능 보증은 아니다.
