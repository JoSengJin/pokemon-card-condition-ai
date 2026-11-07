# surface-region-rank-hypothesis-20261107

owner: Codex
status: integrated
base_sha: de62efb2bb7ab92aea9416f5206394ee3c5ec15a
branch: main
goal: 기존 실패와 확정1776구역 저장 오류를 대조해 가설1개·단일변수·대조·성공 기준을 학습 전에 제시한다.

allowed_files:
- docs/collaboration/reports/surface-region-rank-hypothesis-20261107.md
- docs/collaboration/reports/surface-region-rank-hypothesis-20261107.html
- docs/collaboration/tasks/surface-region-rank-hypothesis-20261107.md
- ignored artifacts/surface-region-rank-hypothesis-20261107/ 신규 진단/제안 산출물

forbidden_files: 기존라벨/답/사진/모델/실험/worker/운영/PokeCollector/fallback/진척기준/다른 작업 파일. 학습/추론/모델호출/자동review/실행용plan/worker생성 금지.

contract: 최종 가설 surface-frozen-global-region-rank-20261107, 전역 train 구역쌍 순위계수0→1만 제안. 기존 백본/손실/라벨/입력/마스크/head/초기값/mass/L2/seed/5fold/threshold고정. 모든 train 양성×정상 쌍 평균, OOF오류쌍선별/held-out정답학습 금지. D1/표면보류2 새 평가/튜닝 금지. 사진내 초안은 학습전철회해 증거보존, 활성제안1개.

structure: 신규추적소스0, ignored diagnose.py4함수/refine-global.py2함수, 자체최장 main→보조함수1전이. 모델/실행기호출변경0.

checks: 기존합성5+전역합성3경로,1776최종정답·FN67/FP201·32사진/58쌍·전역520220/43360 및사진내1520/210·다른사진518700/43150 재현. ratio분모/재표집사진그룹204 명시, 5fold train쌍/그룹/해시분리, 실패3실험 실제상태 대조,205입력SHA불변,새experiment0,사진32/오류268ID 대조.

experiment: 미실행. 제안만 작성. 성공AND AUC≥0.94665065 및그룹95%차이하한>0, FN≤67/370, FP≤112/1406, threshold0.5. 기존수치조건 완화안함. 이후실행요청시snapshot/code_changes/사전계획확정후./experiment1회. 미달/실패/수렴실패 자동재시도금지.

handoff: 사진간 쌍은분모가커서 역순위도많으며 이것만으로인과를주장하지않음. 전역AUC목표와모든정상사진을직접감독하기위해 전역pair항을분리검증제안. 과거사진내정확점ranking/warmstart/FT+withinrank실패를공개. 학습/추론/모델호출/실행용계획/worker0, 진척78유지. report.html은기존OOF사진/오류/사전기준만. 열기queued/렌더미확인. 원격SHA 최종인계.

rollback:신규문서커밋만revert후일반push.원답/모델복구불필요,분석/철회초안보존.
