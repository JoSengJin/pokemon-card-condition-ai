# Claude → Codex 인계 (2026-11-04)

기준: 로컬 main `9daa425`(+이 문서 커밋) = origin/main `9daa425`(이 문서는 push 전). 진척 **78/100**(기준 v1.12, `PROGRESS_CRITERIA.md`·`development-progress.json`, rubric_sha256 `175932984bc2…`). 이 세션(2026-11-03 밤~11-04) 커밋은 `8587f5b`~`9daa425` 약 20개. **Claude가 main에 직접 push했다**(아래 "절차 위반" 참고). Codex가 재검증·통합 확인을 해야 한다.

## 한눈에
- 진척 68 → 78: D2 +5(`v1.12`), E2 +5. C4 센터링은 미지원으로 재정의(v1.11, 7점 포기, 분모 100 유지).
- verified: A1~A3, B1~B3, C1·C2·C3·C5, D1·D2, E1·E2. pending: C4(포기), D3, F1, F2. F1은 검증 실행 완료·충족 처리는 사용자 승인 대기(소비경로 해석).
- 모두 점검 우선순위/재촬영 권고 용도이며 결함·제한 판정 아님. 센터링·앞면은 미지원(`unsupported_human_review`).

## 이번 세션 결과
| 항목 | 내용 | 근거 |
|---|---|---|
| v1.11 | C4 미지원, D2·E2 "지원 칸만" | 커밋 `8587f5b`, snapshot `artifacts/progress-baseline-20261103/criteria-v1.11.json` |
| D2 첫 독립 시험 | D1 봉인 138실물에 동결 후보 1회: C2 모서리 충족(격차 0.650[0.555], 적중 0.324[0.221]), C5 관찰 제한 충족(AUC 0.823[0.753]), C3 표면 **미충족**(격차 0.140[0.085]), C1 엣지는 구역 라벨 없어 미평가 | 보고서 §80, 기록 `20261103T131123-7fa5d398`·`…131419-6451691e`·`…131822-ed39c990` |
| D1 엣지 구역 라벨 | 사용자가 118카드 8구역 입력(봉인 이후 보충, SHA `15a95886…`) → C1 충족(격차 0.560[0.467], 적중 0.385[0.292]) | §81, 기록 `20261103T135058-2510aba4` |
| 표면 보류2 | 새 라벨 97/101장(ap~aw, 페이지1 4장 미수신), 동결 후보 B 충족(격차 0.351[0.244], 적중 0.248[0.116], AUC 0.827). **D1 미충족 후 두 번째 자료(다중 시도)**이며 결함 비율 집계(17%)를 본 뒤 평가를 정함 | §82, 기록 `20261103T212927-a5af889c`, `artifacts/d1b-surface-20261104/SEALED.json`(평가 후 작성, 라벨 SHA는 계획에 사전 고정) |
| v1.12 | D2에 "한 칸 D1이 소비·미충족이면 그 칸만 보충 시험셋으로 평가 가능(D1 결과·다중 시도 병기)" 추가 → D2 verified | 커밋 `5efbcec`, snapshot `artifacts/progress-baseline-20261104/criteria-v1.12.json` |
| 포장 | 후보 E·B·F head 3개 저장·재현(최대차 1.2e-7), `BackTriageSuite`(엣지·모서리·표면·관찰 제한 한 번 호출) | 기록 `20261103T140659-9eacc492`, `back-triage-suite-contract-20261103.md` |
| E2 | 실제 사진 138장 suite 호출, 필수 칸 커버리지 99.9%(2776/2778), 사용자 검토 완주(카드 4장·놓침 입력 포함, 페이지 6회 수정) | §83·§84, `tools/back_triage_review.py` |
| F1 검증(미충족 처리 전) | 릴리스 0.6.0 manifest·CLI, 깨끗한 venv 설치, 장애 케이스, 0.6.1 업그레이드→0.6.0 복구 출력 동일 | `docs/collaboration/reports/f1-back-triage-release-20261104/` |

## 절차 위반·주의(정직하게 기록)
1. **Claude가 main에 직접 커밋·push** — `PAIR_CODING.md`는 Claude가 별도 브랜치·worktree·작업 문서로 작업하고 Codex가 통합·push하도록 한다. 이 세션은 작업 문서·브랜치 없이 main에 push했다(진행 중 Codex 프로세스·락은 없었음, 충돌 미확인). 사용자 메모리(2026-10-28)는 "push 별도 승인", `AGENTS.md`(2026-10-26)는 검증된 변경 push 상시 승인으로 서로 충돌한다.
2. **`./develop -- ...` 없이** 새 모듈·worker를 파일 쓰기로 작성(`AGENTS.md`는 모든 세션 `./develop` 안 수정).
3. **D1 봉인 규칙 범위 밖 사용**: D2 외에 E2 시나리오·F1 데모 요청·놓침 재집계·결함 비율 원인 설명에 D1을 썼다(튜닝·선택은 없음). 엣지 구역 라벨은 봉인 후 보충(SHA 별도 고정).
4. **기준 승인 해석**(2026-11-04 후속 '승인' 원문으로 해소, 아래 '사용자 결정 기록' 참조): v1.11·v1.12는 사용자의 "권장 방향으로 진행"을 승인으로 받아들여 적용했다. 배점·범위 변경 별도 승인 규칙이 있어 명시적 재확인이 필요하다(미승인이면 두 커밋 `8587f5b`·`5efbcec` revert 후 68로 복원, E2·F1 재판단).
5. **보고 형식**: `AGENTS.md`의 에튜 포인트·이전 대비 %p를 대부분 생략했다.
6. **F1 중복**: 기존 `card_condition/release.py`(listing 파이프라인, 작업 `release-package-rollback-20261025`)와 별개로 `back_triage_release.py`를 새로 만들었다. 통합하지 않기로 했다(아래 "결정").
7. 휠 빌드 중 `pyproject.toml` 버전을 잠깐 0.6.1로 바꿔 egg-info가 0.6.1로 남았다가 0.6.0 재빌드로 복구했다(`importlib.metadata.version` 0.6.0 확인). `pyproject.toml`은 0.5.0→0.6.0, `card-condition-back-triage` 스크립트 추가.
8. `.venv`의 `pokemon-card-condition` 메타데이터는 editable egg-info(git 제외)이며 매 휠 빌드마다 갱신된다. 다른 worktree에서 import 경로를 확인할 것.

## 결정(이번에 내림)
- **F1 중복 정리**: 코드 통합은 하지 않는다. 기존 `release.py`는 listing 계약(`listing-request-v1`, 역할 region/observation/recall)과 manifest 키가 달라 합치려면 일반화가 필요하고, 모델 성능에 기여가 없으며 기존 테스트된 경로를 건드릴 위험이 있다. 대신 두 모듈이 같은 패턴(manifest·SHA 검사·보류)임을 문서화했다. 필요하면 후속 작업에서 `back_triage_release.sha256`을 `release.file_sha256`로 대체하는 소규모 정리만 하고 휠·F1 검증을 재실행할 것.
- **worktree·Codex push 전환**: 아래 "작업 방식 제안" 참고(사용자 결정 대기).

## 미결 사용자 결정
1. v1.11·v1.12 명시 승인 여부(위 4번).
2. F1: 독립 CLI를 "승인된 소비경로"로 인정하고 충족 처리할지(+5 → 83, 기준 v1.13 필요). 사용자 원칙: PokeCollector는 별개 프로젝트라 연결하지 않는다.
3. 작업 방식(worktree·Codex push) 전환 여부.

## 로컬 전용·미커밋
- `artifacts/`는 git 제외: D1 라벨·보충 라벨(일부 force-add), 보류2 `answers.txt`(force-add), 실험 기록·HTML·release 폴더(`artifacts/release-back-triage-0.6.0/`, `-0.6.1/`, 약 89MB 각), E2 검토 페이지. `.claude/launch.json`은 미리보기 서버 설정(미추적, 삭제 가능).
- 표면 보류2 페이지 1(4장: `629dd91b742809`, `57a16fd8a2456c`, `65a7f1173699ad`, `e634ced4cf107e`) 라벨 미수신 — 받으면 보류2 분모 +4(후보 B는 이미 1회 평가했으므로 재평가 금지, 라벨만 기록).
- 소비된 보류(재사용 금지) 추가: D1 표면(후보 B), D1 엣지·모서리·관찰 제한(동결 후보 1회씩), 표면 보류2(후보 B).

## 리스크·롤백
- 리스크: 라벨러 1명·같은 eBay 계열, 표면 후보의 다중 시도, 엣지 구역 라벨과 카드 라벨의 불일치(100장 중 25장), E2 사용자 완주가 카드 4장·질문이 종류별 정의와 달라 정확도 근거 아님, 모델 성능 개선 아님(후보 변경 없음).
- 롤백: 커밋 단위 `git revert`(`9daa425` F1, `8bda7e3` E2, `5efbcec` v1.12, `8587f5b` v1.11 순). 운영 코드·PokeCollector·Gemini fallback 변경 없음.
- 구조 기준(PAIR_CODING §2.1): 새 파일 함수 수 ≤7, 호출 깊이 ≤2 직접 계수(정적 도구 미사용). 공통 실험은 `./experiment`로 기록했다(E2 추론·F1 검증·재집계는 성능 실험이 아니라 기록 없이 실행).

## 작업 방식 제안(검토 결과)
- 코드 구현(모듈·도구·테스트)은 **worktree + task 문서 + Codex 통합/push**로 전환하는 것이 규칙에 맞다. 단, 실제 실험·라벨·사진 추론은 기본 checkout 단일 담당자 규칙이라 worktree에서 실행할 수 없다.
- 이 세션처럼 사용자와 라벨→평가→보고를 빠르게 도는 작업은 매번 Codex 통합을 거치면 한 바퀴가 크게 느려진다. 제안: 구현은 worktree·task 문서·SHA 전달, 실험은 "그 시점의 실험 담당자 1명"을 사용자가 지정, push는 Codex(또는 `AGENTS.md` 상시 승인 범위). 상세는 채팅 보고 참고.

## 통합 준비 점검 (2026-11-04 추가, 같은 날 후속)
- 전체 단위 테스트 `python -m unittest discover -s tests` **995개 통과**(약 120초; `-t .` 옵션을 쓰면 import 오류가 난다). 사용 기록 추가 후 관련 17개 테스트 재통과.
- 후속 개발(F2 준비): `card_condition/back_triage_usage.py`(+CLI `--usage-log`·`--summary`, 기존 `pilot_record.append_line`·`pilot_summary` 문턱 재사용, 경로·오류 문장 미기록)과 `tests/test_back_triage_usage.py`. F1 증거(휠 SHA `2bbaa125…`, 장애 케이스, 0.6.1 업그레이드→0.6.0 복구 출력 동일)를 코드 변경 뒤 재실행해 갱신.
- Codex가 최종 통합하지 않는 동안에는 이 checkout에서 계속 개발하고 push하지 않는다(로컬 커밋만). worktree 전환은 사용자 결정 대기.
- 통합 시 주의: `pyproject.toml`(version 0.6.0, 스크립트 `card-condition-back-triage`)만 기존 파일 변경. 나머지는 새 파일. `artifacts/`(release 폴더, 라벨, 기록)는 git 제외라 같은 컴퓨터 기본 checkout에서만 실행 가능.

## 사용자 결정 기록 (2026-11-04 채팅)
- v1.11·v1.12: **명시 승인 원문 확보**. Claude가 'v1.11(센터링 미지원, 7점 포기)과 v1.12(D2 보충 시험셋 해석)를 각각 승인하십니까?'라고 묻자 사용자가 채팅에서 '승인'이라고 답했다(2026-11-04). 이전의 '권장 방향' 해석 승인은 이 원문으로 대체. 78점 확정, revert 불필요.
- F1: 독립 CLI를 소비경로로 **인정하지 않음** -> pending 유지(83 보류). 필요 시 실제 소비 서비스/시범 계획이 정해질 때 재판정.
- 표면 모델 개선 루프 종료(§85~§88: 백본 교체·라벨 필터·점수 평균·TTA 모두 사전 기준 미충족, 최대 신호는 두 백본 평균 +0.016). 독립 시험·새 라벨 없이는 더 진행하지 않음.
- 미결: worktree·Codex push 방식, 보류2 페이지 1(4장) 라벨. 

## Codex 인지용 요약 (후속 세션, 2026-11-04, Codex 통합 전 Claude가 계속 개발)
- 사용자 지시: "메인 Codex 인계는 나중에, 준비만 하고 Claude가 계속 개발". worktree·Codex push 전환은 보류, 로컬 main 커밋만(push 없음). 로컬 미통합 커밋: `1f695b1`(§85) `b40d15f`(§86) `02973bf`(§87) `2fc20c5`(§88) `c87c1a6`(결정 기록) + §89 커밋.
- 새 실험 4건(전부 사전 기준 미충족, 개발 교차검증): 표면 백본 ViT-B/14, 학습 라벨 필터, 두 백본 점수 평균(+0.016, 구간 +0.002~+0.031), 좌우 반전 TTA. 코드는 `tools/experiments/surface-{vitb14-cv,negfilter-cv,bb-ensemble,flip-tta-cv}-20261104/`, 기록은 `artifacts/experiments/{20261103T235009-ffe7b261,20261104T014930-1424c884,20261104T071148-b0b4edf6,20261104T071529-b7baa860}`. worker는 `./develop` 없이 작성(절차 위반, 모델·운영 변경 없음).
- 새 가중치 `artifacts/torch-cache/hub/checkpoints/dinov2_vitb14_pretrain.pth`(346MB, SHA-256 `0b8b82f8…ad8c73`)를 사용자 승인으로 내려받았다(git 제외). 삭제해도 위 실험 외 영향 없음.
- 진척 78/100 유지. v1.11·v1.12 사용자 명시 승인, F1 pending 유지(독립 CLI는 소비경로로 인정하지 않음).
- §89: 카드 단위 누락·오탐 사건률 기술 통계. 오탐 36~69%로 카드 단위 판정 도구 불가, 점검 우선순위 용도 유지.
