# s 사람 결함 지점 보존과 진단 — 2026-10-10

## 실제 저장 결과

s/back에 surface_defect 지점4개 저장 확인. 원본 좌표는 그대로 보존했으며 기존 면/구역 정답과 카드 영역을 바꾸지 않았다. 별도 `artifacts/regions-labeled-20261010-round7.jsonl` snapshot 및 `artifacts/region-round7-snapshot-receipt.json`으로 원본 해시·이전 snapshot 해시·분할 변경0을 기록했다. 미지정 t는 원본에서 그대로 두고 학습 사본에서 제외했다.

`point-audit`는 사람 지점을 기존3×3 구역 정답과 대조하는 읽기 전용 CLI다. 구역 정답1과 일치(matches_positive), 정답0과 충돌(conflicts_with_normal), null/누락(region_unknown)을 구분한다. null을 정상으로 채우거나 점 개수만큼 학습 정답을 생성하지 않는다. 내부 경계는 우측/아래 구역, 바깥 경계는 카드 안으로 분류하며 기존 region_box와 같은 경계 계산을 사용한다.

```sh
.venv/bin/card-condition point-audit artifacts/regions-labeled-20261010-round7.jsonl artifacts/point-evidence-audit-20261010-round7.json
```

| 지점 | 구역 | 종류 | 기존 구역 정답과 관계 |
|---|---|---|---|
| 1 | 좌측 상단 | 표면 | 결함1과 일치 |
| 2 | 우측 중간 | 표면 | 구역 미확인 |
| 3 | 상단 중앙 | 표면 | 구역 미확인 |
| 4 | 상단 중앙 | 표면 | 구역 미확인 |

정상 라벨과 충돌0건. 여러 점이 같은 구역에 있어도 서로 다른 실물이나 독립 학습 표본이 아니다. 사용자가 확인한 지점은 다시 라벨 재확인을 요구하지 않는다. 기존 구역 학습 입력 round6/round7의 region_rows 반환값 전체가 동일(127구역=train89/val38)이므로 동일 모델 재학습을 반복하지 않았다. 새로운 점 주석을 쓰는 학습 방식과 적절한 정상 비교 표본이 마련되기 전에는 위치 학습 성능을 주장하지 않는다.

## 변경과 검증

- card_condition/point_audit.py 신규, card_condition/cli.py에 point-audit 등록.
- tests/test_point_audit.py: 원본 불변, 구역 경계/카드 가장자리, 정상 충돌·미확인·결함 일치, test의 잘못된 사진/주석을 읽지 않는 격리, 출력 덮어쓰기 거부 검증.
- README.md, pyproject.toml0.4.11, 이 기록, 소비 프로젝트 CONDITION_ANALYSIS_TODO.md 업데이트.
- Python 전체46개 통과. 0.4.11 wheel 빌드 및 point_audit.py/cli.py 소스 일치 확인. 신규 환경 설치 및 위치 학습은 미실행. 기존 운영/Gemini 호출 경로 변경 없음, 실제 절감0건.
- 리스크: 점의 종류와 위치는 사람의 관찰 근거이며 크기·심각도·진위나 실제 상태를 자동 보증하지 않는다. 구역 미확인은 사람이 찍은 결함을 부정하는 뜻이 아니다. 현재 학습은 구역 라벨만 사용한다.
- 롤백: 신규 CLI 분기·point_audit.py 및 테스트/문서/버전 변경만 되돌린다. 0.4.10도 defect_points 저장을 지원하므로 사람의 좌표 데이터는 유지한다. 기존 모델과 실험·라벨은 되돌리지 않는다.
