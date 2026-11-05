# 자료 확보 전략·후속 문서 통합 검증

- task_id: data-acquisition-integration-20261025
- owner: Codex
- status: integrated (문서 검증 완료; HTML 렌더/390px 확인은 이후 Claude 대행으로 완료 — 보고서 후속 절)
- base_sha: e7cdfe5 (Claude 두 커밋을 순서대로 cherry-pick한 main; 전체 SHA는 최종 보고서에 기록)
- goal: d coverage·문서 20행 대조, 두 HTML의 390px/기본 폭 렌더 확인, 평가 정답 절차와 D1 비노출 집계 설계를 보완한 뒤 main 일반 push.
- authorization: 사용자 인계의 Codex 할 일 1·2·4·5. 라벨 요청·협력자 연락·다운로드·학습·추론·자동 검토는 금지.

## allowed_files

- docs/collaboration/tasks/data-acquisition-integration-20261025.md
- docs/collaboration/tasks/a3-data-intake-batch-20261025.md
- docs/collaboration/reports/data-acquisition-pilot-plan-20261025.md
- docs/collaboration/reports/pilot-comparison-rules-20261025.md
- docs/collaboration/reports/data-acquisition-pilot-sheet-20261025.csv
- docs/collaboration/reports/card-photo-labeling-guide-draft-20261025.md
- docs/collaboration/reports/gold-example-candidates-20261025.md
- docs/collaboration/reports/data-acquisition-strategy-20261025.md
- docs/collaboration/reports/data-acquisition-strategy-20261025.html
- docs/collaboration/reports/data-acquisition-followup-20261025.html
- docs/collaboration/reports/data-acquisition-integration-20261025.md
- ignored: artifacts/data-acquisition-integration-20261025/ 아래 검사 결과·재계산 coverage·스크린샷

## contract / checks / handoff

모델·worker·판정 로직·라벨·manifest·과거 artifacts·진척 기준과 점수는 변경하지 않는다. 제품 코드 변경0으로 함수 수/호출 깊이 제한은 해당 없음. 기존 coverage_report로 d를 재계산하고, 원래 coverage와 manifest 위치만 구별해 비교한다. 표20행·모바일 표시·CSV·로컬 링크·비밀/개인 경로·git diff --check를 확인한다. 이력은 추기로 보존하며 실행 전 측정 규칙의 오류는 결과를 보기 전에 정정한다. 새 수치 기준을 승인하지 않는다.

최종 handoff는 reports/data-acquisition-integration-20261025.md와 두 HTML에 기록한다. D1은 설계만 하고 실제 자료·건수를 탐색하지 않는다. 검증 후 git push origin main을 실행하고 원격SHA 일치를 확인한다. 롤백은 보완 커밋→후속→전략의 역순으로 git revert하고 일반 push한다(force 금지).

## 실제 handoff

- Claude 통합: `975556a`, `e7cdfe5` 순서. 제품 소스·기준·점수 변경0.
- d 재계산/보고표20행·예제34개/22실물·모서리 정상24단위 미확인·round2 무응답 대조 통과.
- HTML2개 태그·리소스·링크·표/CSV 정적 검사와 `git diff --check` 통과. 실제 화면 열기는 `file://` URL 정책으로 거부됐으며 렌더/390px 확인 미완료. 우회하지 않음.
- A3 문서에 d 현행 기준과 과거c 이력 구분. 평가 정답의 AI 비노출·사진/box 고정, 파일럿 분모/시간 일치, D1 비노출 집계 설계만 보완.
- 새 사진/정답·학습·추론·외부 AI 호출·사람 라벨 요청·연락·다운로드0. 파일럿 기준/동의서 승인과 협력자 확보는 사람 의존으로 남음.
