# 실물 전체 제외 교차검증 — 0.4.47

GROUP_CROSSFIT_PLAN_20261011.md에 따라 train46면/25실물만 사용했다. 25fold 모두 앞/뒤의 두 클래스를 학습할 수 있었고 비교 제외0개. 각 실물의 앞뒤 사진 전체를 fit/가중치에서 제외한 후 예측했다. 모델선택 val/test는 읽지 않았다.

| 실물 제외 예측 | 공통 centroid | 앞뒤별 centroid |
|---|---:|---:|
| 관찰 제한 FP/FN | 11/5 | 6/4 |
| AUROC | .502232 | .783482 |
| AP | .310377 | .586989 |
| 클래스·실물 균등 BCE | .674077 | .689602 |

오류와 순위 개선 방향은 fixed-val과 일치한다. BCE는 공통 후보보다 나쁘지만 사전 기준 ln2=.693147 아래다. 확률 교정이 개선됐다고 말하지 않는다. 이미 개발에 쓴 train이므로 이 검산도 독립 최종 성능 보증이 아니다. 연구 후보는 artifacts/observation-side-centroids-20261011/model.pt로 유지하며 운영 Gemini fallback 유지·실제 절감0건.

변경: card_condition/observation_crossfit.py 신규, cli.py(visibility-crossfit), tests/test_observation_crossfit.py 신규2개, pyproject.toml0.4.47·README·본 문서·TODO. 모델 체크포인트를 새로 저장하지 않는다.

검증: 전체102테스트(29.253초), 같은 실물 전체 제외/제외 실물 정답 변경 시 자기 예측 불변/val·test 미접근/자료 부족 fold 제외 및 분모 기록/출력 덮어쓰기 거절. 실제 MPS25fold 실행, train입력·live·선택모델 SHA 불변, wheel40파일 바이트 일치. 근거 artifacts/observation-group-crossfit-20261011/report.json·checks.json.

리스크: 자료가 작고 train에 반사/그늘 등의 충분한 독립 실물이 없다. 불가 fold를 빼면 분모가 달라지므로 거절 사유와 수를 공개한다. 이번은 거절0이다. 관찰 제한은 구매 제외나 카드 불량이 아니다.

롤백: 새 명령을 사용하지 않으면 기존 경로 그대로다. .backups/group-crossfit-0447의3파일을 원위치 복원하고 observation_crossfit.py·tests/test_observation_crossfit.py만 제거하면 코드 복귀. 사람 라벨/원본/선택모델은 보존한다.

다음: 독립 평가 경로에 모델 SHA 고정 및 development 실물·이미지 재사용 차단을 구현한다. 사용자 답변: 새 실물 사진 없음(2026-10-11). 기존 train/val을 시험용으로 바꾸거나 완료 라벨을 다시 요청하지 않는다. 독립 성능 숫자는 새 자료가 생길 때까지 제시할 수 없다.
