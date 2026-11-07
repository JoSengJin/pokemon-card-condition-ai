# surface-label-consistency-20261107

owner: Codex
status: integrated
base_sha: f2fd68a34ad824c204e1f2190d16864e24e9e9bd
branch: main
goal: 사람 답 한 구역을 별도로 보존하고 동일1776구역 원라벨/재판정라벨 학습을 사전기준으로 한 번 비교한다.

allowed_files:
- tools/experiments/surface-label-consistency-20261107/worker.py
- tools/experiments/surface-label-consistency-20261107/metrics.py
- tools/experiments/surface-label-consistency-20261107/plan.json
- tests/test_surface_label_consistency_20261107.py
- docs/collaboration/tasks/surface-label-consistency-20261107.md
- docs/collaboration/reports/surface-label-consistency-20261107.md
- docs/collaboration/reports/surface-label-consistency-20261107.html
- ignored artifacts/surface-label-consistency-20261107/ 및 artifacts/surface-label-audit-20261107/ 새 응답/인계 파일

forbidden_files: 기존 사람 답·라벨·모델·D1/표면보류2 봉인/소비자료·운영 소스·PokeCollector·fallback·다른 작업 파일.

contract: sr1107z1=결함 별도 저장, 원판정 오류로 단정하지 않음. §93 원판정 유지(사용자 선택). §97 완료259+새1만 판정뷰에 반영. 불가15는 양쪽 제외. 새 Gemini/Codex 호출0. 사진/그룹별5fold, 원라벨179/1597·새라벨370/1406을 각각 같은1776 ID에서 비교. 비교는 개발/모델선택 자료이며 독립 검증 아님.

structure: worker 신규 함수0(실행 블록), metrics 신규 함수4, tests 신규 메서드3. 변경한 자체 호출 metrics→auc/paired_bootstrap→auc 최대2전이. worker 실행→fit_detail_head→closure→detail_bag_loss→point_bag_loss는4전이(기존 all-eBay 가중치 식은 호출 지점에서 동일하게 계산); PyTorch optimizer의 동적 closure 호출과 기존 라이브러리 내부 깊이는 전체 인증과 구별하고 기존 구현은 수정하지 않는다.

experiment: surface-label-consistency-20261107, 계획 artifacts/surface-label-consistency-20261107/plan.json. 새라벨 AUC차≥0.03·사진그룹95%하한>0 AND 공통 실행기FN≤95 FP≤112 (0.5, 저장된 원학습 점수에서 결과전 산정). 새 증거는 §98 미확인 z152 한 구역의 사람 답. §98을 성공으로 간주하지 않고 신규 한 번만 수행한다.

checks: 합성 unittest3개(라벨 보존/불가제외/미확인 거부/동률·가중AUC/짝지은 그룹bootstrap), 소스·입력 SHA, train/val 실사진 해시·그룹 분리, 공통 ./experiment 실행, record/result/evaluation 대조, 사진 위 HTML/report.html 생성·열기(렌더 미확인 분리), git diff --check.

handoff: 실행 후 기록. 모델 비교 실패 시 운영 미채택, 새 코드/실험 근거 보존, 기존 모델 복원 불필요. 롤백은 신규 추적 파일을 커밋 단위 git revert 및 새 ignored 학습 산출물 별도 제거.


## 실제 인계

공통 실행 record: artifacts/experiments/20261106T210640-0eb1bdc0/record.json completed. AUC 기준false·공통 acceptancefalse, 운영 미채택. 원답/기존 모델 불변. 합성3검사 재실행 통과,10적합 수렴 및 각 그룹/실사진 중복0. record/계획 입력SHA 검증통과. HTML artifacts/surface-label-consistency-20261107/report.html(204개발사진·평가1776구역·불가15구역) 생성/내용대조 완료. 열기/렌더·원격 동기화는 후속 기록. 전체테스트/독립시험/운영 적용 미실행.

Codex 직접 코드/계획/실측 검토 완료. 신규 worker/metrics/test 함수 수0/4/3 검산. 사진 HTML 파일 열기 요청 queued, 실제 렌더 미확인(기존 CUA file URL정책 차단 우회 없음). 입력/원라벨 불변 재확인. 원격 fetch 후 HEAD와origin/main 기준 일치 확인; 이번 통합 커밋을 일반push하며 최종 SHA는 세션 및 ignored sync.json 인계. 다른 작업 .claude/는 미포함.
