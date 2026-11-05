# A3 동결 검증·main 인계 — 2026-10-28

개발 진척 **35/100 (usable-card-analysis-v1.0, 30 대비 +5%p)**. A3 verified 유지. 모델 성능 변화 미측정, 독립시험 D1 미충족. 학습·추론·외부 AI 호출 0회.

## 검토 범위와 결과

검증 source SHA: `9f024cab9b0f101b5a5e29d1c75a36f84dede964`. 검토 커밋 `79cecdb`, `9f024ca`, 기준 `9b98168`. fetch 이후 origin/main은 이 기준과 동일했고 main만 2커밋 앞이었다. Claude가 기본 checkout main에 직접 작성한 것은 PAIR_CODING.md의 구현 worktree 원칙과 다르다. 이번 요청에 따라 현재 diff를 검증했으며 이후 구현은 분리한다.

변경 파일/핵심 diff:
- `tools/freeze_dev_manifest.py`: 기존 채택본 SHA 확인, 검토 val 결합, ID/그룹 분리 확인, 기존 coverage 투영, 좌표 감사·동결표 생성.
- `tests/test_freeze_dev_manifest.py`: 출처 SHA/분할 위반 거절과 좌표 종류/면/정상구역 충돌 검사 2개.
- `development-progress.json`, `PROGRESS_CRITERIA.md`: A3 pending→verified, 30→35점 및 history. 이전 JSON과 전체 milestone ID/배점/완료조건, rubric SHA를 대조해 불변 확인.
- 이 인계 문서 추가, Git 제외 `artifacts/development-manifest-20261028a/REPORT.html`에 검증 정보 보완. 소스·사람 라벨 수정 없음.

## 구조 기준

AST 집계: 신규 도구 함수 0→4개(combine/audit/table/freeze), 테스트 함수 0→4개(face/write/두 테스트). 파일별 7개 이하.

프로젝트 함수 기준 최장 경로는 `freeze → coverage_report → point_rows → validate_annotations → validate_defect_points` 또는 `validate_visibility_points`: **4전이**. `freeze → coverage_report → point_rows → load_manifest`는 3전이. `coverage_report` 내부 put은 freeze에서 2전이이며 추가 하위 프로젝트 호출이 없다. 모듈의 `if __name__ == '__main__'`는 함수가 아니므로 시작 함수 freeze 이전의 함수 전이로 세지 않는다. 모듈 dispatch까지 화살표로 그리면 5개지만 함수 호출 깊이 기준은 4다. 외부 라이브러리 내부 구현은 구조 기준의 프로젝트 함수 경로와 구분했다.

## 실제 실행 검증

`tests/`에서:
- `../.venv/bin/python -m unittest test_freeze_dev_manifest test_data_coverage`: 10개 OK.
- `../.venv/bin/python -m unittest test_data_coverage_provenance test_data_coverage_projection_contract test_data_coverage_output_safety test_data_coverage_photo_consistency test_point_dataset test_regions test_region_dataset`: 38개 OK.
- `git diff --check 9b98168..HEAD`: 통과.

읽기 전용 Python 재검산: ADOPTION의 base SHA와 5 source SHA/행수/제외수를 재확인했다. combine 결과가 동결 manifest 156행과 동일, SHA `7bec9d7e6dbf1e513e87bd81e2893e7c95fc51d4aff698771e6127dbecc15ab3`. coverage_report 결과 전체가 coverage.json과 동일, audit 결과 전체가 audit.json과 동일, table 결과가 FROZEN_TABLE.md와 동일. coverage의 사진 hash·그룹/분할·면/구역 validation이 실제 입력을 통과했다. HTML parser로 10행 양성/정상 단위·실물·미확인 수를 coverage.json과 대조해 일치했다.

영역확인된 자료만 재집계한 양성/정상 (단위/실물):

| 질문/면 | 양성 | 정상 |
|---|---:|---:|
| 센터링 앞 | 28/28 | 49/49 |
| 센터링 뒤 | 33/33 | 36/36 |
| 모서리 앞 | 27/11 | 136/41 |
| 모서리 뒤 | 69/30 | 72/26 |
| 엣지 앞 | 37/17 | 291/42 |
| 엣지 뒤 | 111/35 | 154/29 |
| 표면 앞 | 85/33 | 317/41 |
| 표면 뒤 | 142/44 | 175/30 |
| 관찰제한 앞 | 20/20 | 67/67 |
| 관찰제한 뒤 | 23/23 | 42/42 |

따라서 수량(각20단위·5실물), 기존 typed point/명시 정상구역 출처·사진/좌표/종류 감사, 분모/지원범위/결측표 동결을 확인했다. 센터링은 이진 면 판정이며 비율 측정이 아니다. 정상구역은 정상점 정답이 아니며 미클릭 정상화도 하지 않는다. 현재 모델이 이 전체 범위를 지원/통과했다는 판정은 아니다.

## 감사 한계·리스크

val 좌표 오류0. train의 기존 `ebay-pair-a1c1362ea21fc3`, back 점12 corner_defect/middle_right 오류1은 그대로 보존했다. 경고107(train 점/미확인영역17·typed점 없는 양성48, val 각각7·35). 영역미확인 단위를 제거한 위 표도 모두 충족하므로 A3 수량 판정을 경고 자료에 의존하지 않는다. 학습에 재사용하기 전 기존 train 오류를 사람 검토 없이 수정하지 않는다.

새 테스트는 10개 통과 중 combine의 기존 `open(base)` 미종료 ResourceWarning을 발생시켰다. 자료 검산 결과에는 영향이 없었으며 이번 검토에서 소스 수정하지 않았다. 실험·성능·외부 AI 회귀는 실행하지 않았다. 새 FN/FP/분모/%p를 측정하지 않았으며 정확도 개선을 주장하지 않는다.

## HTML 대조·열기·렌더

산출물: `artifacts/development-manifest-20261028a/REPORT.html`. 내용 대조 완료. 이번 Codex의 IAB 열기는 `file:` URL 보안 정책에 거절됐고 실제 렌더 확인은 미완료다. 다른 브라우저/서버로 우회하지 않았다. Claude의 이전 macOS open 성공 보고와 이번 결과를 구분한다. HTML 첫 화면에 source SHA와 검증 결과를 추가했다. 문서 커밋은 위 검증 코드 SHA와 별개다.

## 미추적 파일·worktree

`docs/collaboration/DATA_INVENTORY_20261028.md`는 변경/커밋하지 않았다. SHA256 `425c54b59033d05e874e1c19f66861d748ee887d08e33600d9984a5ec2451610`. 별도 Codex 세션이 이미 2026-10-28 19:04 KST에 읽고 구현 계약에서도 제외한 기존 자료임을 세션 기록으로 확인했다. 작성자 자체는 확인되지 않았다. 본문의 A3 pending/30점은 현 동결 이전 상태이므로 현재 진척 근거로 채택하지 않고 원위치 보존한다.

이번 두 커밋의 별도 구현 worktree가 없다. 기존 worktree 목록은 읽기 확인했고 이번 통합에 해당하지 않는 미통합/사용 여부 미확인 checkout은 삭제하지 않았다.

## 원격·롤백

일반 `git push origin main`으로 두 검토 커밋과 본 인계를 반영하고 로컬/원격 SHA 일치를 확인한다. 실제 push 결과는 Git 제외 `artifacts/development-manifest-20261028a/CODEX_HANDOFF.json`에 기록한다. force push/이력 재작성 없음.

기능·진척 롤백은 잠금 안에서 `./develop -- git revert 9f024ca 79cecdb`, 관련 검증 후 일반 push. 이 인계 문서는 감사 이력으로 남길 수 있다. 이전 채택본 `artifacts/development-manifest-20261025d`는 보존했다. Git revert는 Git 제외 동결 산출물을 삭제하지 않는다.
