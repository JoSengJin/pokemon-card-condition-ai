개발 진척률 78/100 · D-LOC 결정표 ④ — 첫 추천 구역이 12/22장에서 A 결함과 일치해 다음 개발 과제 선정은 보류한다.

탐색 자료 · 새 추론 없음 · 독립 시험 아님

기본 표시 A에서 결함인 카드 26장 중 임계 0.5에서 경보가 뜬 카드는 24장이다. 첫 구역에서 A 결함을 확인한 카드는 12장, A 정상은 10장, 세 판정이 모두 갈린 카드는 2장이다. 첫 구역이 A 결함이었던 12장을 포함해, 경보 구역을 모두 점검하면 16장에서 한 곳 이상 A 결함이 나온다.

결정표는 주 임계 0.5의 분자로만 적용했다. 12장은 사전등록한 혼재 구간 9~13장에 든다. surface-a-target-swap-70card-cv-20261114는 §4 검토 자격에 해당하지 않아 보류한다. 0.8은 기존 제품 개발 보고의 기본 운영점이다.

## 지표와 분모

| 임계 | L1 첫 구역 일치 (95%) | L2 경보 중 한 곳 이상 (95%) | L3 A 결함 구역 회수 (95%) |
|---|---|---|---|
| 0.5 | 12/22 · 54.5% (34.7%–73.1%) | 16/24 · 66.7% (46.7%–82.0%) | 33/45 · 73.3% (52.8%–86.5%) |
| 0.8 | 11/16 · 68.8% (44.4%–85.8%) | 11/18 · 61.1% (38.6%–79.7%) | 26/45 · 57.8% (33.3%–75.4%) |

L1·L2는 경보 카드에 조건을 둔다. 구간은 Wilson 양측 95%다. L3는 미경보 카드까지 포함해 실물 카드 26장을 복원추출하고 매번 결함 구역 분자와 분모를 다시 합산했다(2,000회, 시드 20261114, 백분위 95%). 모든 집계는 비가중이다.

| 임계 | 경보/결함 카드 | 첫 구역 판정 가능/경보 | unknown | split | 미경보/결함 카드 | 우연 기준 |
|---|---|---|---|---|---|---|
| 0.5 | 24/26 | 22/24 (91.7%) | 0 | 2 | 2/26 | 21.46% |
| 0.8 | 18/26 | 16/18 (88.9%) | 0 | 2 | 8/26 | 24.48% |

우연 기준은 L1 대상 카드마다 A 결함 구역 수를 실제 존재하는 모든 구역 수(미판정 포함)로 나눈 값의 평균이다. L1과의 차이는 기술적 참고값이다. 0.8에서 L1은 높지만 미경보가 2장에서 8장으로 늘고 A 결함 구역 회수도 33곳에서 26곳으로 줄었다.

| 임계 | 첫 구역 사람 라벨 | A 결함 | A 정상 |
|---|---|---|---|
| 0.5 | defect | 11 | 6 |
| 0.5 | normal | 1 | 4 |
| 0.8 | defect | 10 | 5 |
| 0.8 | normal | 1 | 0 |

| 임계 | 카드 밖 표시 있음 L1 | 표시 없음 L1 | 최고점 동점 카드(경보) |
|---|---|---|---|
| 0.5 | 1/5 | 11/17 | 0 |
| 0.8 | 1/3 | 10/13 | 0 |

| 임계 | 최고 구역 집합 | 후보 판정 있음 | 사람 결함 | 사람 정상 | 사람 판단불가 | 후보 판정 없음 |
|---|---|---|---|---|---|---|
| 0.5 | 경보 전체 | 7 | 6 | 0 | 1 | 17 |
| 0.5 | L1 대상 | 6 | 5 | 0 | 1 | 16 |
| 0.8 | 경보 전체 | 3 | 3 | 0 | 0 | 15 |
| 0.8 | L1 대상 | 2 | 2 | 0 | 0 | 14 |

70장(A 결함 26·정상 40·미확정 4), 615구역(A 결함 45·정상 527·unknown 35·split 8), 최고점 동점 0장. 카드 밖은 최고 구역의 마스크 표시다. 후보 판정은 오류 중심으로 골라 70장 전체를 대표하지 않는다.

A는 기본 표시 이미지에 대한 AI 합의이며 판정자 공통 오류가 가능하다. 같은 개발 자료의 작은 표본이고 클릭 좌표가 0건이므로 구역 안 실제점은 위치 판정 불가다. 사람과 AI가 같은 자국을 봤는지 알 수 없다. 표면 이외 엣지·모서리·관찰 제한에는 적용할 근거가 없다. 모델 교체 전후 FN·FP·AUC 변화와 독립 일반화 개선은 미측정이다.

개발 진척 근거는 PROGRESS_CRITERIA.md와 development-progress.json의 usable-card-analysis-v1.13(직전 대비 0%p)이다. 사전등록 b2dc3bfdeeb4ef5571d568d4fd06a21db761fc67 · 적용 코드 SHA-256 e4ddc65509f94bdfbfb67d6df96cc788257c91064a986e1a1f9baba34fa60c3a (커밋 전 실행본). 입력별 SHA-256과 원점수는 로컬 results.json에 있다.

## 카드별 추적

같은 카드의 구역 ID는 group ID + /back/surface/ + 구역 이름이다. 점수 표시는 소수 여섯 자리이며 순위와 임계는 저장 원정밀도를 사용했다.

| group ID | 카드 A | 최고 구역 | OOF 점수 | 사람 구역 | 구역 A | 카드 밖 | 후보 상자 |
|---|---|---|---|---|---|---|---|
| ebay-pair-01973015865fc2 | 결함 | upper_left | 0.367664 | 정상 | 정상 | 예 | 판정 없음 |
| ebay-pair-02cf89f941ba8a | 결함 | upper_right | 0.811911 | 결함 | split | 예 | 판정 없음 |
| ebay-pair-093bd3aaa8e539 | 결함 | middle_left | 0.950352 | 결함 | 결함 | 아니오 | 판정 없음 |
| ebay-pair-0bc1ecbeb8d0ff | 결함 | middle_left | 0.967822 | 결함 | 결함 | 아니오 | 결함 |
| ebay-pair-108fc310f2d309 | 결함 | upper_right | 0.579651 | 결함 | 결함 | 아니오 | 판정 없음 |
| ebay-pair-1b3d59291cab08 | 결함 | lower_right | 0.967204 | 결함 | 결함 | 아니오 | 판정 없음 |
| ebay-pair-277c6c5590e4ee | 결함 | center | 0.662948 | 정상 | 정상 | 아니오 | 결함 |
| ebay-pair-2d2c1744fa35ee | 결함 | lower_right | 0.863374 | 결함 | 결함 | 아니오 | 판정 없음 |
| ebay-pair-3578d1170b7ed7 | 결함 | center | 0.609130 | 정상 | 정상 | 아니오 | 결함 |
| ebay-pair-55b480939fd41c | 결함 | upper_right | 0.800062 | 정상 | split | 예 | 결함 |
| ebay-pair-634cd6dca67c62 | 결함 | middle_right | 0.915775 | 결함 | 결함 | 아니오 | 판정 없음 |
| ebay-pair-6866caaf70d7c8 | 결함 | middle_left | 0.964071 | 결함 | 정상 | 아니오 | 판정 없음 |
| ebay-pair-6f68b149da97c9 | 결함 | upper_center | 0.847625 | 결함 | 정상 | 예 | 판정 없음 |
| ebay-pair-742c04c1c08794 | 결함 | middle_left | 0.870178 | 정상 | 결함 | 아니오 | 결함 |
| ebay-pair-8b712018d115e4 | 결함 | upper_left | 0.834589 | 결함 | 정상 | 아니오 | 판정 없음 |
| ebay-pair-8f73d488e2832d | 결함 | middle_right | 0.827064 | 결함 | 정상 | 아니오 | 판정 없음 |
| ebay-pair-92fa211c4425da | 결함 | upper_right | 0.935438 | 결함 | 결함 | 아니오 | 판정 없음 |
| ebay-pair-99f37ff9cfa79a | 결함 | upper_right | 0.791046 | 결함 | 정상 | 예 | 판정 없음 |
| ebay-pair-aad0e546e928ba | 결함 | center | 0.901588 | 결함 | 결함 | 아니오 | 판정 없음 |
| ebay-pair-b64f4291446d70 | 결함 | upper_center | 0.804201 | 결함 | 결함 | 아니오 | 판정 없음 |
| ebay-pair-bb02e59b8f0e6b | 결함 | upper_right | 0.971796 | 결함 | 결함 | 예 | 판정 없음 |
| ebay-pair-d3c4501fb863eb | 결함 | upper_right | 0.874750 | 결함 | 정상 | 예 | 판정 없음 |
| ebay-pair-d6d3029a25ae55 | 결함 | lower_right | 0.386948 | 정상 | 정상 | 아니오 | 판정 없음 |
| ebay-pair-d757a7a0e8fe52 | 결함 | upper_right | 0.597894 | 정상 | 정상 | 아니오 | 결함 |
| ebay-pair-f0938cad09b48f | 결함 | upper_left | 0.972584 | 결함 | 결함 | 아니오 | 판정 없음 |
| ebay-pair-f9fbd5669f2646 | 결함 | lower_center | 0.538007 | 정상 | 정상 | 예 | 판단불가 |
| ebay-pair-02170c802a45b2 | 정상 | lower_left | 0.457472 | 결함 | 정상 | 아니오 | 결함 |
| ebay-pair-032a88efe49212 | 정상 | upper_right | 0.742861 | 결함 | 판단불가 | 아니오 | 판정 없음 |
| ebay-pair-03be29eb65f6e2 | 정상 | upper_right | 0.638293 | 정상 | 정상 | 아니오 | 결함 |
| ebay-pair-0bfd194e23ca2b | 정상 | upper_right | 0.803868 | 결함 | 정상 | 예 | 판정 없음 |
| ebay-pair-155bd341312fe4 | 정상 | upper_right | 0.407024 | 정상 | 정상 | 아니오 | 판정 없음 |
| ebay-pair-1d0c2cb1c23ce7 | 정상 | upper_left | 0.241306 | 정상 | 정상 | 아니오 | 판정 없음 |
| ebay-pair-1fb8627a4b5711 | 정상 | upper_left | 0.700109 | 결함 | 정상 | 아니오 | 판정 없음 |
| ebay-pair-21ea0ba197b927 | 정상 | upper_center | 0.841468 | 결함 | 정상 | 아니오 | 결함 |
| ebay-pair-2432a32ee8c6b5 | 정상 | middle_right | 0.712244 | 정상 | 정상 | 아니오 | 결함 |
| ebay-pair-28771349820995 | 정상 | upper_left | 0.707643 | 정상 | 정상 | 예 | 정상 |
| ebay-pair-2ea06a1e89a680 | 정상 | lower_left | 0.465228 | 정상 | 정상 | 아니오 | 판정 없음 |
| ebay-pair-32360d6efb961c | 정상 | upper_left | 0.170389 | 정상 | 정상 | 아니오 | 판정 없음 |
| ebay-pair-4d7aa49cb6abda | 미확정 | middle_right | 0.791446 | 결함 | 정상 | 아니오 | 결함 |
| ebay-pair-5eb308b036ff51 | 정상 | upper_center | 0.480174 | 결함 | 정상 | 예 | 결함 |
| ebay-pair-626f5aef46f96d | 정상 | center | 0.411263 | 정상 | 정상 | 아니오 | 판정 없음 |
| ebay-pair-6edf93a803d9d7 | 정상 | middle_right | 0.766081 | 결함 | 정상 | 예 | 판단불가 |
| ebay-pair-73068033ea88aa | 정상 | middle_left | 0.177143 | 정상 | 정상 | 아니오 | 판정 없음 |
| ebay-pair-7651a8031657aa | 정상 | upper_left | 0.329814 | 정상 | 정상 | 아니오 | 판정 없음 |
| ebay-pair-76817f05bd4c8f | 정상 | lower_right | 0.623551 | 결함 | 정상 | 아니오 | 판단불가 |
| ebay-pair-7761b8eeef0e95 | 정상 | lower_right | 0.244288 | 정상 | 정상 | 아니오 | 판정 없음 |
| ebay-pair-7a57296def2a55 | 정상 | upper_left | 0.550023 | 정상 | 정상 | 아니오 | 판단불가 |
| ebay-pair-7ee67279cbb53b | 정상 | upper_right | 0.702105 | 결함 | 정상 | 아니오 | 판정 없음 |
| ebay-pair-858f5a4f342cec | 정상 | lower_left | 0.471143 | 정상 | 정상 | 아니오 | 판정 없음 |
| ebay-pair-8ef2f67b46146c | 정상 | upper_left | 0.155988 | 정상 | 정상 | 아니오 | 판정 없음 |
| ebay-pair-8f4dba6a9c52eb | 정상 | center | 0.428130 | 정상 | 정상 | 예 | 결함 |
| ebay-pair-9b0ed0ff515d89 | 정상 | upper_right | 0.322907 | 정상 | 정상 | 아니오 | 판정 없음 |
| ebay-pair-9d3e6b22db7bad | 정상 | lower_right | 0.483408 | 결함 | 정상 | 아니오 | 결함 |
| ebay-pair-a180b1c225a70b | 정상 | lower_left | 0.259104 | 정상 | 정상 | 아니오 | 판정 없음 |
| ebay-pair-a425cd17da7b4c | 정상 | upper_center | 0.309618 | 정상 | 정상 | 아니오 | 판정 없음 |
| ebay-pair-a60610c3a2c9b6 | 정상 | upper_right | 0.324759 | 정상 | 정상 | 아니오 | 판정 없음 |
| ebay-pair-a9bf3a847d72ba | 정상 | upper_right | 0.601585 | 정상 | 정상 | 아니오 | 판단불가 |
| ebay-pair-afafb32bfa975a | 정상 | upper_left | 0.530007 | 정상 | 정상 | 아니오 | 정상 |
| ebay-pair-b563bf39ede9bc | 미확정 | upper_right | 0.769924 | 정상 | 판단불가 | 예 | 정상 |
| ebay-pair-bb5189e374013f | 정상 | upper_center | 0.164781 | 정상 | 정상 | 아니오 | 판정 없음 |
| ebay-pair-bdd7d27e0e93dd | 정상 | lower_right | 0.879526 | 정상 | 정상 | 아니오 | 결함 |
| ebay-pair-c0ea73b0af132c | 정상 | upper_left | 0.714428 | 결함 | 정상 | 아니오 | 판정 없음 |
| ebay-pair-c50e2d784b00e5 | 정상 | upper_center | 0.260945 | 정상 | 정상 | 아니오 | 판정 없음 |
| ebay-pair-ddae08dbcf1ef9 | 정상 | upper_right | 0.207615 | 정상 | 정상 | 예 | 판정 없음 |
| ebay-pair-e47f4fe2753f4e | 정상 | upper_center | 0.402784 | 정상 | 정상 | 아니오 | 판정 없음 |
| ebay-pair-e7d7987b6879d2 | 정상 | lower_left | 0.744872 | 결함 | 정상 | 아니오 | 판정 없음 |
| ebay-pair-e816acdb4b945f | 정상 | middle_left | 0.835766 | 결함 | 정상 | 아니오 | 결함 |
| ebay-pair-e9632a6f6973a7 | 미확정 | upper_right | 0.877149 | 결함 | 정상 | 예 | 판정 없음 |
| ebay-pair-f5fcd9c05e6d2d | 정상 | upper_right | 0.758909 | 정상 | 판단불가 | 아니오 | 판단불가 |
| ebay-pair-fb29e2064d5396 | 미확정 | center | 0.760510 | 정상 | 판단불가 | 아니오 | 결함 |

## 실행과 인계

기본 checkout에서 전용 worktree의 스크립트를 1회 실행했다. 실행 명령(변수는 전용 worktree 경로)과 출력은 다음과 같다.

```text
./develop -- .venv/bin/python -B "$DLOC_WORKTREE/tools/diagnostics/alarm-location-20261114/analyze.py"
completed ('④', '혼재로 판정 보류')
0.5 [24, 22, 2, 2]   0.8 [18, 16, 2, 8]
```

사전등록 커밋은 작업 계약과 prereg.json을 추가했다. 결과 커밋은 inputs.py(함수 5개, 입력/합의 검증), analyze.py(4개, 통계/결정), 이 보고서를 추가했다. 가장 긴 직접 호출은 load_cards → votes → read/check(2회)다. 이전 함수 수는 모두 0이다. 사전등록 파일과 실행 소스, 기존 규칙 소스 및 데이터 88개 파일의 SHA-256을 결과에 기록했다. 기존 평가 결과 쓰기를 수행하는 모듈은 import하지 않았다.

로컬 전용 파일은 artifacts/alarm-location-20261114/results.json 및 report.html이다. 원본 사진 없이 70장의 3×3 격자를 표시했다. 롤백은 작업 브랜치에서 결과 커밋을 먼저 revert한 후 사전등록 커밋을 revert한다. 로컬 산출물은 Git 롤백과 별도로 보관한다.

## 저장 결과 마무리 검증 (2026-11-14)

이번 인계에서는 분석을 다시 실행하지 않았다. 기본 checkout은 main의 공동 설계 기준 3cbf778e6ebb8f237684989177896f4367ebd140, 전용 worktree는 codex/alarm-location-20261114의 사전등록 b2dc3bfdeeb4ef5571d568d4fd06a21db761fc67임을 확인했다. 기본 checkout의 기존 미추적 .claude/는 보존했고, 전용 worktree의 미추적 파일은 이번 결과 커밋 대상 3개뿐이었다. 사용자 승인에 따라 main 통합·push·worktree 정리는 하지 않는다.

실제 검사 명령은 기본 checkout의 `.venv/bin/python -B /private/tmp/verify_dloc_saved.py`다. 진단 모듈은 실행·import하지 않고 JSON 읽기, SHA-256, AST, HTMLParser와 저장 카드에 대한 독립 산술 대조만 수행했으며 exit 0이었다.

- results.json의 completed·사전등록 SHA·사전등록 파일 이력을 대조했다. 사전등록/실행 소스 3개, 읽기 전용 기존 규칙 소스 1개, 입력 88개의 SHA-256 총 92개가 모두 일치했다. 결과 JSON SHA-256은 `6ef32998b8e06fff21180337af654d34dcbd1849c43cdc3de5d9386b5e226f08`이다.
- 두 임계의 L1~L3 분자·분모와 Wilson 95% 구간, 저장 카드 26장의 고정 시드 부트스트랩 95% 구간을 대조했다. 교차표 합 22/16, 우연 기준 21.46%/24.48%, 카드 밖 표시별 L1, 후보 판정 없음(absent)과 사람 판단불가(unknown)의 별도 집계를 확인했다. JSON에서 확인한 지표와 Markdown·HTML의 5개 표가 일치했다.
- 카드별 Markdown 70행의 ID·원점수 표시·사람/A 라벨·카드 밖·후보 판정을 JSON과 대조했다. HTML은 카드마다 3×3 격자 총 70개, 저장 구역 615칸·구역 없음 15칸·최고 구역 강조 70개를 위치별로 대조했다. 최고점 원정밀도 순위·동점 ID도 일치했다. 함수 수는 AST로 inputs.py 5개, analyze.py 4개를 확인했다.
- PROGRESS_CRITERIA.md와 development-progress.json을 읽고 v1.13·earned 합 78/100을 확인했다. 가산 0점이며 결정표 ④와 후속 과제 보류를 유지했다.

HTML 열기 성공 여부: **미확인(이번 브라우저 열기 요청은 거부됨)**. `cua.createBrowserTab`의 file: URL 요청은 자동 보안 검토가 `The requested URL protocol is not allowed. Allowed protocols: http:, https:` 사유로 거부했다. macOS open 명령은 이번에 실행하지 않았으며, 이전 턴의 성공 여부도 확인하지 못했다. 우회 서버나 외부 전송은 사용하지 않았다.

실제 화면 관찰·렌더 확인 여부: **미확인**. `cua.getState`는 `The Mac is locked and automatic unlock could not unlock it`를 반환했고, 위 브라우저 정책도 로컬 파일 열기를 차단했다. 첫 화면 header 소스에 ‘탐색 자료 · 새 추론 없음 · 독립 시험 아님’, 12/22, 결정표 ④, 과제 선정 보류가 있는 것은 정적으로 확인했으나, 화면에 보였다고 보고하지 않는다.

변경 파일·핵심 diff는 inputs.py의 고정 입력 연결/합의 검증, analyze.py의 L1~L3/결정표 집계, 이 결과 보고서의 수치·추적·검증 기록 추가다. 실행 소스는 저장 해시를 보존하기 위해 수정하지 않았다. 로컬 report.html에는 이번 검증과 열기/렌더 한계를 덧붙였다. 원본 사진·홈 절대경로·로컬 JSON/HTML은 커밋 대상에서 제외한다. 스테이징은 이 3개 파일만 명시했다. `git diff --cached --name-only`로 허용 목록 일치를 확인했고, 보고서의 EOF 공백 1줄을 제거한 뒤 `git diff --cached --check`를 통과했다.

리스크·미검증: 작은 개발 표본과 기본 표시 A의 AI 합의에 공통 오류가 있을 수 있다. 새 모델 성능·독립 일반화·실제점 적중은 검증하지 않았고, HTML의 실제 레이아웃도 확인하지 못했다. 이번 작업은 저장 기록 검증이므로 모델·worker·운영 동작의 변경은 없다. 로컬 결과 보존은 Git 커밋만으로 보장되지 않는다. 롤백은 `git revert <결과 커밋 SHA>` 다음 `git revert b2dc3bfdeeb4ef5571d568d4fd06a21db761fc67` 순서이며, 로컬 산출물은 별도 보존한다.
