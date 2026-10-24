# Round17 — 최초 정상 뒷면 엣지 학습 실물

사용자가 ㅂ 뒷면 바깥 테두리 전체를 충분히 확인했고 정상이라고 명시했다. 이 확인에 근거해 중앙을 제외한8구역의 edge_defect만0으로 기록했다. 다른 종류/앞면/전체 상태/같은 실물 확인은 null 또는 기존 값 유지. 저장만으로 정상 정답을 추측하지 않았다.

## 데이터와 실행 검증

- data/learn-review.jsonl의 ㅂ region_labels 및 사람 확인 메모만 변경. 기존 다른58행 불변 단언 통과.
- 원본 백업: data/learn-review-before-b-normal-confirmation-20261010.jsonl.bak.
- artifacts/point-evidence-20261010-round17.jsonl 동결 SHA256: 17b9d934d44e2559c43a9152dba980cb250bdbb9550dc36b1f3f32d0f00a0f3d.
- point_rows(grid=True) 검산: train111→119, val50동일. 기존 입력·좌표·검증 라벨 전체 동일, 신규8구역은 back/edge0만 포함. artifacts/point-evidence-round17-receipt.json 참고.
- 정상 뒷면 엣지 학습 실물0→1. 8구역은 한 실물이며 독립8표본이 아니다.
- 실행 중 localhost:8766/api/review에서 ㅂ 정상 엣지8구역 반환 확인. API 키/토큰 값 출력 없음.

## 동일 검증 데이터 비교

224px·20epoch·seed42·사전학습 특징 고정·선형 head 학습. 기존 region_experiment의 ResNet18 지원도 재사용해 추가 의존성/제품 코드 변경 없이 비교했다.

| round17 모델 | 모서리 FP/FN | 엣지 FP/FN | 표면 FP/FN |
| --- | --- | --- | --- |
| MobileNet 기본 | 6/0 | 12/0 | 19/0 |
| MobileNet 보정 | 2/1 | 4/6 | 11/8 |
| ResNet18 기본 | 6/0 | 12/0 | 18/1 |
| ResNet18 보정 | 4/1 | 5/4 | 4/17 |

round16 MobileNet 보정 엣지5/5, 표면11/9. 정상 보강 후 엣지 오탐은 하나 줄고 누락은 하나 늘었다. ResNet18 보정은 엣지 누락을 줄이지만 표면 누락17로 악화한다. 모든 결함에서 일관된 개선이 아니므로 운영 교체·자동 Gemini 생략 보류, 실제 호출 절감0건.

근거: artifacts/point-grid-{augmented,balanced}-round17-comparison-20261010.json 및 artifacts/point-grid-backbone-round17-comparison-20261010.json. 이번 val은 반복 모델선택 자료이며 최종 성능 증거가 아니다. 정상인 ㅂ 학습 구역에 잘 맞는다는 사실을 일반화 성능으로 보고하지 않는다.

## 변경·위험·다음 의존성·롤백

변경 파일은 data/learn-review.jsonl, 백업, 분리된 round17 snapshot/receipt/모델/report/comparison, 본 문서와 마스터 CONDITION_ANALYSIS_TODO.md. 제품 Python/HTML 코드는 변경하지 않았다. 따라서 기존 제품 회귀검사·wheel 빌드를 불필요하게 반복하지 않고 실제 입력 검산·4학습·동일 검증 비교·실행 API 확인을 수행했다.

조건부 기술 선택 검토 결과: 기존 PyTorch/torchvision의 ResNet18만으로 비교 가능하며 새 프레임워크 도입 근거가 없다. 한 정상 뒷면 실물만으로 부분 미세조정 확대를 결정하지 않는다. 다음에는 서로 다른 정상 뒷면 실물 최대2장이 필요하다. 신규 자료의 용도는 모델 결과 노출 전에 고정하며 검증 자료를 학습으로 이동하지 않는다. 완료한 카드 재확인은 요청하지 않는다.

라벨 롤백은 백업의 ㅂ 행과 현재 행을 비교해 이번8개 엣지0/확인 메모만 되돌린다. 전체 파일 백업 덮어쓰기는 후속 저장을 잃을 위험이 있어 피한다. 새 모델은 분리 산출물로 운영 모델 복구는 불필요하다.
