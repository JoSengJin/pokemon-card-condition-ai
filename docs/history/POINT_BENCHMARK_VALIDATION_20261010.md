# 구역 추론 시간 측정 — 2026-10-10

사람 라벨 추가 없이 진행 가능한 TODO의 추론 시간 측정 작업을 수행했다. 최신 실험 체크포인트를 지원하는 `point-benchmark`를 추가하고, point-probe의 검증된 로더와 patch_features를 재사용했다. 신규 프레임워크와 의존성은 없다.

## 입력과 결과

고정 round17 snapshot(train119, val50/8실물), 동일 MobileNet 엣지 전용 기준선/확대 모델. val50구역을 각 3회 실행하고 준비 1회는 제외했다. 테스트 종료 후 순차 측정한 보고서를 사용한다.

| MPS 모델 | 중앙값/구역 | p95/구역 | 초기 로딩 |
|---|---:|---:|---:|
| 전체 3×3 기준선 | 23.95ms | 40.08ms | 130.36ms |
| 전체 3×3 + 테두리 확대 | 50.80ms | 109.50ms | 132.59ms |

근거: artifacts/point-edge-context-timing-quiet-20261010.json, artifacts/point-edge-views-timing-20261010.json. 첫 기준선 측정은 테스트와 겹쳐 별도 보존했으며 위 비교에 쓰지 않았다.

이미지 읽기·전처리·head/sigmoid·CPU 결과 복사를 포함한다. 확대 모델은 여러 입력을 추론하므로 시간이 증가했다. OS 캐시·다른 프로세스·발열 영향이 있으며, 매물 전체 지연이나 메모리 측정은 아니다. 기존 정확도 미달 결론과 운영 모델은 변경하지 않았다. 실제 Gemini 절감0건.

## 검증과 변경 범위

- Python 전체59개 통과: /private/tmp/condition-point-benchmark-tests.log. 기존 누수 차단·학습/추론 출력 일치·최종시험 사진 미열람 검사에 두 입력 방식의 측정/덮어쓰기 차단 검사를 추가했다.
- 0.4.25 wheel 빌드 및 point_benchmark.py/point_probe.py/cli.py와 wheel 소스 일치 검사 통과.
- 원본60개 라벨 SHA256 10f42fb3b40799c3041dcef4380d7f8146277e9444813cbfbf81809ee3995e74 유지.
- 변경: card_condition/point_benchmark.py, point_probe.py, cli.py, tests/test_edge_views.py, pyproject.toml, README.md, 이 기록 및 PokeCollector의 마스터 TODO. 소비 앱 실행 코드·DB·운영 체크포인트는 변경하지 않았다.

## 다음 의존성과 롤백

정상 뒷면 엣지 train 실물은 ㅂ 한 장뿐이다. ㅅ은 검증 전용으로 유지한다. 미등록 폴더2개(ebay-8add86afe03253, ebay-5083bd3e54da1c)는 모두 비어 있어 신규 사진0개였다. 일반화 개선을 판단할 다음 실험에는 서로 다른 정상 뒷면 실물과 사람이 확인한 정상 구역이 필요하다. 완료한 카드를 재라벨하거나 검증 자료를 학습으로 이동하지 않는다.

롤백: point-benchmark CLI 분기와 새 모듈·관련 검사·문서 추가를 제거하고, point-probe의 load_probe_model 내용을 기존 probe_model 앞부분으로 되돌린다. 패키지 버전을0.4.24로 복원한다. 측정 JSON만 제거해도 라벨·모델은 영향을 받지 않는다.
