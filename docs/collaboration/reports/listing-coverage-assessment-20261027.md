# 실제 매물 결과의 E2 coverage 집계 — 2026-10-27

개발 진척률 **30/100 (usable-card-analysis-v1.0, 직전 대비 +0%p)**. 이번 성과는 동결한 정답·릴리스·요청·저장 결과를 연결해 실제 보류 coverage를 계산할 API/CLI를 구현한 것이다. 실제 자료의 E2 coverage와 모델 성능은 아직 측정하지 않았다.

검증 소스 SHA: `ddd07698feceb40606e34eebe913bc386a2792f3`. 모델 학습·사진 추론·외부 AI 호출·사람 라벨 수정은 수행하지 않았다. 합성 시연은 정답과 구역 점수를 명시적으로 구성한 입력 계약 검증이며 실제 성능 결과가 아니다.

## 변경 파일과 핵심 diff

- `card_condition/listing_coverage.py`: 읽기 전용 집계 API와 모듈 CLI. 기존 point_rows(grid=True)의 정답 투영을 이용하며 학습·추론을 실행하지 않는다. 질문/앞뒤별 10개 집계와 사례별 셀·제외 이유·보류 이유를 출력한다.
- `card_condition/listing_coverage_inputs.py`: bundle·원래 요청/결과 SHA, 사진·카드영역·관찰 확인·릴리스와 주/보조 모델 SHA를 대조한다. 저장된 구역 점수로 기존 listing_readiness 정책을 재계산해 state/reason/summary가 다르면 거절한다.
- `tests/test_listing_coverage.py`: 기존 ListingAnalyzer 생산 코드에 Mock 구역 점수를 주입해 만든 저장 결과로 분모 보존, 70% 경계, 미확인/부분 반사, 변조 거절과 CLI의 실제 연결을 확인한다.
- `docs/collaboration/tasks/listing-coverage-assessment-20261027.md`: 정확한 허용 파일·입출력·분모·검사·인계 계약.
- `docs/collaboration/reports/listing-coverage-assessment-20261027.md` 및 `.html`: 이 보고서와 로컬 HTML.

기존 listing API·정책·학습·모델·평가·라벨링 UI·PokeCollector 코드는 수정하지 않았다. 기존 CLI를 바꾸지 않고 `python -m card_condition.listing_coverage` 진입점을 제공한다.

## 고정 분모와 완료 판단

각 카드의 필수 셀은 앞뒤 각각 모서리4·엣지8·표면9·센터링1·관찰 제한1, 총46개다. 이 중 명시적 정답, 확인된 카드 영역(box_reviewed), 명시적 관찰 확인이 있는 셀을 분모에 둔다. 부분 반사는 해당 구역을 제외하며 전체면 질문은 전체 관찰 가능할 때만 포함한다. 정답·영역·관찰 확인이 부족한 셀은 사유별로 공개한다. 이 부분집계만으로 A3/E2가 충족되는 것은 아니다.

분자는 이 분모 중 실제 API state가 normal 또는 defect인 셀이다. unknown·미지원·누락 사진·결과 미제공은 분모에서 빼지 않는다. 원본에 알려진 관찰 가능 셀이 있는데 요청에서 사진을 빼면 분자는0이 될 수 있어도 그 셀의 분모는 유지된다.

전체면 정상을 지역 정상으로 이식하지 않는다. review_record의 ground_truth=false를 평가 정답으로 승격하지 않는다. manifest의 정답·실물 그룹은 입력 주장이고 이 도구가 사람 정답의 진실성이나 실물 동일성을 인증하지는 않는다. 동일 디코딩 사진의 중복 계수는 거절한다.

coverage는 판정 정확도가 아니다. 70% 수치 조건과 실제 사용자 검토 완주는 별개이며, e2_verified/production_ready는 계속false다. C의 FN/FP 분모·threshold·수용 기준은 변경하지 않는다. 현재 API가 제공하지 않는 센터링·전체면 관찰 모델 판정은 계속 보류다.

## 실행 검증

- 격리 worktree의 관련23개 검사 OK(8.433초).
- main 통합 후 동일23개 검사 OK(9.508초). 신규 검사는5개이며 나머지는 기존 매물/보류/전체면 검토/릴리스 회귀다.
- 명령: `PYTHONPATH=tests .venv/bin/python -m unittest test_listing_coverage test_listing_model test_listing_readiness test_listing_review_whole_scope test_release`
- 정본 로그: `artifacts/listing-coverage-assessment-20261027/tests.log`.
- git diff --check·컴파일 통과. AST 함수 수: 집계2, 입력3, 검사7. 주요 소스 경로 assess→checked_case→listing_readiness/photo_request→validate_annotations→validate_defect_points 최대4전이.
- 집계 단계에서 RegionAnalyzer 생성/추론이 없음을 확인했다. checkpoint는 release SHA와 supported 메타데이터 확인용으로 읽을 뿐 모델 객체를 만들거나 forward하지 않는다.
- 이미 있는 출력은 덮어쓰지 않고 기존 공통 atomic writer를 사용한다. CLI 실행 전후 합성 입력 파일 SHA가 같았다.

### 합성 CLI 시연 — 실제 성능 아님

| 사례 | 비보류/알려진 관찰 가능 | coverage | 70% 수치 조건 | E2 완료 |
|---|---:|---:|---|---|
| 기본 |9/23|39.13%|false|false|
| 저장 결과 누락 |0/23|0%|false|false|
| 요청 사진 누락 |0/23|0%|false|false|
| 경계값 |7/10|70%|true|false|

시연 원본/요청/저장 결과/bundle/CLI 산출물을 사례별 독립 폴더에 보존했다. `artifacts/listing-coverage-assessment-20261027/demo.json`, `index.html`과 각 사례의 `coverage.json`에서 재검토할 수 있다. 마지막 사례는 알려진 셀만 가진 별도의 합성 모집단이며, 앞 세 사례와 성능 개선으로 비교하면 안 된다.

첫 시연의 생성 프로세스와 CLI 실행 위치가 달라 설치 패키지 메타데이터 버전이 불일치했고 release 검증이 거절했다. 이 합성 입력은 metadata-mismatch-baseline에 보존했다. 같은 checkout에서 새 합성 입력을 생성해 CLI를 확인했으며 버전 검사를 해제하거나 기존 릴리스를 고치지 않았다.

## 사용법과 필요한 실제 입력

```text
python -m card_condition.listing_coverage MANIFEST RELEASE BUNDLE OUTPUT --bundle-sha256 SHA256
```

bundle의 외부 SHA를 명시해야 한다. 형식은 다음과 같다(해시는 실제 원래 파일 SHA로 채운다).

```json
{
  "schema_version": 1,
  "manifest_sha256": "<frozen manifest SHA256>",
  "release_sha256": "<release manifest SHA256>",
  "cases": [
    {
      "id": "example-id",
      "request": {"path": "request.json", "sha256": "<original SHA256>"},
      "report": {"path": "report.json", "sha256": "<original SHA256>"}
    }
  ]
}
```

입력은 val 또는 test 하나의 명시적 모집단만 허용한다. train/혼합 split은 거절한다. bundle에 사례를 빼도 원본 모집단의 알려진 셀이 분모에 남는다. 요청/결과 경로는 bundle 기준이며 결과가 임의로 사진이나 영역을 바꾸면 받아들이지 않는다.

다음 실제 집계에는 Claude가 보완한 자료의 동결 정답·사진/영역 감사, 같은 릴리스의 원래 요청·저장 결과와 SHA가 필요하다. 이 자료를 대신 만들거나 현재 미완료 자료를 정상으로 처리하지 않았다. 독립 시험의 사용 이력도 별도 감사가 필요하다.

## 성능·진척·운영 한계

이번에 실제 모델 성능을 새로 평가하지 않았다. 정확도/FN/FP/%p 변화는 미측정이며 독립 일반화와 운영 개선도 미확인이다. 기존 참고 수치인 20261027T132418-8a5aa6ae의 기준선 재생은 FN16/94·FP18/53·typed FN21/51, 변화0%p였다. 이후 정상 그룹 목적식 실험20261027T133213-807fae2a는failed이며 after가 없다. 이 과거 수치를 이번 성과나 최신 실패의 대체 결과로 쓰지 않는다.

개발 진척은 PROGRESS_CRITERIA.md/development-progress.json의 고정30/100을 유지했다. 이번 코드는 E2 측정을 준비한 것이고 전 범위 사용자 시나리오를 완주했다는 증거가 아니다. 실제 E2 coverage는 아직 미측정이다.

## 리스크·롤백·원격·정리

- 입력 묶음의 사진·manifest·release·원래 결과가 달라지면 출력하지 않는다. release와 설치 패키지 메타데이터가 같은 실행 환경이어야 한다.
- 저장 점수와 state의 일치 검사는 원래 추론 계산이나 사람 정답의 진실성까지 인증하지 않는다. 전체면 API 지원이 없으므로 해당 질문은 계속 보류다.
- 롤백: `./develop -- git revert ddd07698feceb40606e34eebe913bc386a2792f3` 후 위 관련 검사와 일반 push. 새 모듈/검사만 제거되며 원본 데이터·모델·기존 결과 복구는 필요 없다.
- 코드 main/origin ddd07698feceb40606e34eebe913bc386a2792f3 일치를 확인했다. 보고 문서는 후속 커밋으로 일반 push한다.
- 이전 Codex normal-group-objective checkout은 고유2커밋의 main 대응·clean·비차단 잠금·고유lock 증거 SHA 보존 후 일반 worktree remove로 정리했다. 브랜치/이력과 실험 기록은 보존했다. 최근 listing-coverage-assessment checkout을 롤백용으로 유지한다. Claude 데이터/미통합/부분통합 checkout과 다른 Codex checkout은 그대로 두었다.
- 정리 감사: `artifacts/listing-coverage-assessment-20261027/worktree-cleanup/audit.json`.

## HTML 열기

성과 HTML과 합성 시연 HTML 모두 Codex 브라우저 열기도구가 queued를 반환했다. 열기 요청은 전달됐고 실제 렌더는 미확인이다. 정적 HTML과 Markdown 본문 일치, 외부 스크립트·홈 절대경로가 없음을 확인했다.

## 에튜 포인트

coverage와 정확도는 다른 분수다. 예를 들어 알려진10셀 중7개를 모델이 보류하지 않으면 coverage는70%다. 그7개가 맞았는지는 FN/FP로 따로 확인해야 한다. 이번 코드는 저장 state로 coverage만 집계하고 기존 정확도 분모를 바꾸지 않도록 분리했다.
