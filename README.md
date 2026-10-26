# Pokemon Card Condition — experimental

과거 개발 보고서와 이동 목록은 [문서 보관함](docs/history/README.md)에 있습니다. 동결 기록의 기존 링크가 필요한 보고서는 루트에 유지합니다.

## 로컬 경로 설정

이 문서와 과거 보고서의 명령은 현재 저장소 루트에서 실행합니다. 내부 경로는 `data/`, `artifacts/`, `./review`처럼 상대경로를 사용합니다.

외부 PokeCollector와 연동하는 수집 작업에만 아래 경로를 설정하세요. 예제 경로는 실제 로컬 위치로 바꿉니다.

```sh
export POKECOLLECTOR_ROOT="/path/to/pokecollector"
```

이 변수는 셸에서 기존 `--consumer-root "$POKECOLLECTOR_ROOT"` 옵션에 전달하는 값이며, 프로그램이 자동으로 읽는 새 설정은 아닙니다. 개인 경로는 저장소에 커밋하지 말고 셸 설정 또는 WebStorm 실행 설정에 보관하세요.

기본 사진 수집에는 DB가 필요하지 않습니다. 외부 비전 선별을 명시적으로 실행할 때만 `POKECOLLECTOR_QUOTA_DB`를 실제 쿼터 SQLite 파일 경로로 설정하고 `--quota-db "$POKECOLLECTOR_QUOTA_DB"`로 전달하세요. 과거 보고서의 `${POKECOLLECTOR_ROOT}`도 이 로컬 설정을 뜻합니다.


실사용 진척률 **30%(고정 기준 v1.0, 2026-10-24 최초산정)**. 현재점수 정본은 [개발 진척 JSON](development-progress.json), 완료조건과 배점은 [고정 진척 기준](PROGRESS_CRITERIA.md)을 따른다. 아래 과거67%는 개발기반 이력이며 현재전체진척과 비교하지 않는다. 최신점수는 JSON/history를 우선한다.


연속 결함점 입력(2026-10-23): 위치 확인은 공용 라벨 화면에서 여러 점을 연속 클릭하고 한 번 저장한다. 대표 한 점만 받는 과거 별도 화면은 새 작업에 사용하지 않는다. 저장된 `defect_points` 전체가 `point_rows`의 학습 입력이 되며, 미클릭 구역은 정상으로 만들지 않는다. 엣지는 위치, 마모·화이트닝은 흔적의 형태다. Codex가 종류를 구분해 제안하되 애매한 종류만 확인하고, 승인되지 않은 AI 제안은 정답으로 바꾸지 않는다. 학습은 공통 실행기로 검증하며 저장만으로 운영 모델을 교체하지 않는다. [실험·다중점 검증·롤백](artifacts/raichu-confirmed-point-20261023/REPORT.md).
Gemini 교차 검토는 `./review` 한 번으로 최신 자료를 기본 1회 검토하고 다음 할 일을 자동 저장합니다. 같은 자료·모델·프롬프트는 기존 결과를 재사용하며 다시 호출하지 않습니다. 추가 검토가 필요할 때만 `./review --interactive`에서 r을 선택하며 검토 전체 최대 3회입니다. q는 저장, Enter는 토론 종료입니다. 결과의 `next_steps.md`를 Codex에 전달하면 됩니다. 제안은 자동 실행하지 않습니다. [사용법·검증·변경·롤백](docs/history/DEFAULT_ONCE_REVIEW_20261019.md).

자동 연결은 `./review --auto`로 실행합니다. Codex CLI가 코드·실패 이력을 검증해 실험 하나를 채택하면 토론을 끝내고 구현·공통 실행기 평가로 이어갑니다. Gemini 기본1회·최대3회, Codex CLI 별도 사용량을 기록합니다. [자동 연결·토큰 비교·검증](AUTO_DEVELOPMENT_20261020.md).
독립 Python 모델 패키지. PokeCollector 코드/DB를 import하지 않는다.
새 실험은 `./experiment --plan 계획.json -- 실행명령`으로 계획·판정 기준·코드 diff·완료/실패/중단 상태를 공통 기록합니다. 기존 `./review`는 공통 기록을 우선 읽으며 과거 기록도 지원합니다. [공통 실험 기록 사용법](COMMON_EXPERIMENT_RECORDS.md).
실제 카드 라벨로 기준 모델 실험을 진행 중이다. 운영 정확도 검증은 아직 통과하지 않았다.

2026-10-15 피카츄 표면6점·뒷면 영역 확인을 반영해 표면4구역만 보강. 같은 val38구역 누락10/19·오탐2/19 전후 동일로 미채택. [검증·변경·롤백](docs/history/PIKACHU_SURFACE_VALIDATION_20261015.md).

0.4.99: 승인된 야도란·뮤츠·고우스트 정상 표면6구역을 기존 train 레코드에 반영. 동일 val38구역 세 초기값 모두 누락1~2곳 감소·오탐 유지. 추가 train-only 수렴 로지스틱 후보는 오탐 증가로 미채택. OpenCV 실험은 사용자 요청으로 복구. [검증·변경·롤백](docs/history/SURFACE_BATCH_VALIDATION_20261015.md).

0.4.98: 망나뇽 표면 정상2승인을 기존 train 레코드에만 반영(실물 중복 추가0), 세 초기값에서 개선 근거 미달. train 전용 가중 ridge 적합을 고정 정규화1.0으로 별도 비교해 누락9→5/19·오탐3→8/19로 미채택. 기존 모델 유지·검증으로 계수/정규화 학습 안 함. [검증·변경·롤백](docs/history/DRAGONITE_SURFACE_VALIDATION_20261015.md).

0.4.97: 꼬렛 승인 표면 정상2·기스1구역을 train에 보강해 세 초기값에서 누락 감소를 확인했지만 한 초기값의 오탐 증가로 미채택. 고정 표면 선형 분류기의 선택 `--zero-init-head` 비교는 초기값 불변이지만 FN14/FP12로 악화해 미채택. 기본 초기화·기준 모델 유지. [검증·변경·롤백](docs/history/RATTATA_SURFACE_VALIDATION_20261015.md).

0.4.96: `point-experiment --surface-input context|tiles`로 표면 전용 입력 비교와 기존 마지막 공간 블록 미세조정을 연결했다. 엣지 경로·기본값 유지, 표면 타일 체크포인트를 독립 API/구역 CLI/point 최종평가가 읽는다. [실험·검증·리스크·롤백](docs/history/SURFACE_INPUT_VALIDATION_20261015.md).

0.4.95: 동일 자료에서 train 전용 특징 표준화·8차원 비선형 분류기·focal loss를 별도 비교했다. 비선형은 같은 보강 자료 대조군 대비 누락2→1·오탐6→5이나 유지 기준0/5 미달이라 미채택. 선택 옵션이며 기본 모델과 추론 계약은 유지한다. [검증·변경·롤백](docs/history/EDGE_METHODS_VALIDATION_20261015.md).

0.4.94: 기본 라벨 화면을 영역·센터링·클릭·AI 확인·저장으로 줄였다. 중복 갤러리·관리 폼·좌표/구역 상세는 접고 검토자는 공통 입력 하나를 사용한다. 일반 저장은27칸 구역폼을 자동으로 열지 않는다. 라벨/모델은 변경하지 않았다. [검증·영향·롤백](docs/history/SIMPLE_REVIEW_VALIDATION_20261015.md).

0.4.93: AI 초안은 `<작업파일 stem>.drafts.json`에 분리하고, 클릭 검토 화면에서 사람이 여러 구역을 승인·거절해 저장할 수 있다. 승인 전에는 학습 라벨이 아니며 사진/영역 변경·기존 사람 정답 충돌·test 자료는 승인하지 않는다. 승인 출처·검토 기록은 export에도 보존된다. 꼬렛의 정상 엣지14구역은 Codex 제안이며 사용자의 확인 전에는 미확인이다. [검증·리스크·롤백](docs/history/AI_DRAFT_REVIEW_VALIDATION_20261015.md).

후속 실제 실행: 사용자 확인 꼬렛 정상14·손상1 엣지를 train에 추가한 후보는 같은 val에서 누락0→2/15·오탐5→6/12로 악화해 미채택했다. AI 보조 정답 생성과 실제 모델 성능은 별개로 검증한다. 다음 꼬부기·피카츄 후보는 사람 확인 전이다. [시각화·판단·롤백](docs/history/RATTATA_APPROVED_VALIDATION_20261015.md).

캐이시 일부 오염 클릭 보강(2026-10-15): 미표시 구역은 정상/결함으로 추정하지 않고 직접 찍은 엣지2구역만 기준 모델에 보강했다. 같은 val의 누락0/15·오탐5/12 전후 동일로 미채택. 부분 클릭 회귀 포함26테스트 통과. 다음 신규 꼬렛의 정상·결함 정답은 사람 확인 단계다. [시각화·검증·롤백](docs/history/ABRA_PARTIAL_LABEL_VALIDATION_20261015.md).

0.4.92: 마그마 표면 결함 36점을 train 14구역으로 보강한 비교에서 같은 val 표면38구역의 누락10/19·오탐2/19가 유지되어 미채택했다. 앞뒤 동일 실물은 미확인으로 보존한다. eBay 뒷면 검증 v3는 확대 삽입 합성도 별도로 거부하며 구형 계약 캐시를 새 검증으로 간주하지 않는다. 해결된 뒷면 검증의 과거 오류 표시도 해제한다. [검증·시각 보고·롤백](docs/history/MAGMAR_SURFACE_VALIDATION_20261015.md).

0.4.91: eBay 사진 선별에서 판매자 상태 예시·확대 삽입 합성 사진과 실제 로고 없는 뒷면을 구분하도록 입력 계약을 보강했다. 호출 한도에 막히면 명시적인 사람 확인을 사진 해시에 묶어 저장하고 확인한 후보만 내보낼 수 있다. 사진 경계 확인은 정상/결함 정답이나 동일 실물 확인을 대신하지 않는다. [검증·한계·롤백](docs/history/EBAY_ELIGIBILITY_HUMAN_FALLBACK_VALIDATION_20261015.md).

0.4.90: 사람 라벨 eBay 5매물의 엣지 정상16/손상11구역을 train에 추가해 비교했다. 같은 val에서 누락0→2/15·오탐5/12 유지로 미채택. `point-experiment --balance --side-balance`는 앞면/뒷면×정상/손상 네 셀을 train 안에서만 동등하게 가중하는 연구 옵션이다. 같은 자료에서 누락5/15·오탐6/12, 입력448 비교도 누락3/15·오탐11/12로 미채택했다. 기본 학습·운영 모델 변경 없음. 자동 수집의 뒷면 검증 대기 수와 캐시 재개 상태도 표시한다. [실험 근거·검증·롤백](docs/history/EBAY_LABELLED_LEARNING_VALIDATION_20261014.md).

0.4.89: `tools/collect_ebay_dataset.py`는 별도 자료 확보 도구다. 기존 eBay 연결로 매물의 전체 사진을 가져와 Gemini로 단일 카드 앞뒤를 자동 선별하고, 선택된 뒷면의 로고·네 변·모서리 가림을 묶음 재검증한다. 통과한 원본 두 장만 learn의 실물 후보 폴더로 내보낸다. 모호한 사진은 보류하고 정상/결함 정답은 생성하지 않는다. 재실행은 판독 캐시를 재사용한다. 이 도구만 소비 프로젝트의 API 연결과 기존 호출 한도 장부를 재사용하며, 모델 패키지의 추론 경로는 독립이다. [실행 방법·검증·리스크·롤백](docs/history/EBAY_AUTO_INTAKE_VALIDATION_20261014.md).

0.4.85: 클릭으로 결함점·면 라벨 동시 기록, 정상/미확인 구역 클릭·반사 보호. 기존 라벨 보존·165테스트 통과. OpenCV 보류, 다음은 새 실물 자료 보강. [검증·리스크·롤백](docs/history/CLICK_LABELS_VALIDATION_20261012.md).

0.4.84: 엣지 누락 우선 선택 재검토 API/CLI. 동일27구역 누락3→1·오탐4→7, 기존 검출 유지. 불량 확정/운영 변경 없음. [검증·리스크·롤백](docs/history/EDGE_RECALL_VALIDATION_20261012.md).

0.4.82: 프테라 보강 후 동일24면 실물 제외 검증에서 관찰 제한 누락4→2·오탐5→3. 타일 교체는 재사용 val에서 누락0→1로 기각하고 데이터만 보강한 앞면 연구 후보를 고정했다. 자동 정상 통과 정책 미채택·운영절감0. [근거·검증·롤백](docs/history/RECALL_CONSULT_VALIDATION_20261012.md).

0.4.34: `--edge-input tiles-max`는 전체 구역 평균을 유지하고 세부 타일 공간 특징만 최댓값으로 집계한다. 같은 round21에서 FP/FN4/3→5/5·AUROC0.822→0.656으로 악화돼 운영 채택하지 않는다. `--backbone resnet18` 동일 평균 타일 비교도 누락3→6으로 채택 보류했다. 기본 평균 타일·기존 모델은 유지한다. img_1 두 모서리 사용자 정정은 별도 반영하고 img_2 라벨은 유지했다. [검증·리스크·롤백](docs/history/TILE_MAX_VALIDATION_20261010.md).

0.4.33: `--edge-input tiles --fine-tune-spatial` 선택 실험을 추가했다. 고정된 입력·데이터로 마지막 공간 블록만 학습해 round21 FP/FN4/3→3/4, 별도ㅅ FP1→2로 운영 채택 보류. input-review는 실제 고정 타일의 native/224/448도 제공한다. [검증·한계·롤백](docs/history/TILE_SPATIAL_VALIDATION_20261010.md).

0.4.32: 기존 고정 보류 실험에 실물별 판정·보류·오탐·누락·미확인 분모를 추가했다. 판정0개 실물의 오류율은 null로 유지한다. 최신 후보의 오류0/판정7구역 중6개가 d에 집중하고, 정답 있는7실물 중5실물이 전부 보류임을 확인했다. 재학습·임계값 변경·Gemini 자동 생략 없음. [근거·검증·롤백](docs/history/GROUP_ABSTENTION_VALIDATION_20261010.md).

0.4.31: point-grid 학습 보고서에 epoch별 정상/결함 가중 BCE·유효 질량·오탐·누락을 기록한다. `--balanced-selection`은 train을 그대로 유지하고 val 모델선택에만 class/실물 균등 가중을 쓰는 기본 비활성 실험이다. round20 tiles의 전부 결함 판정12FP/0FN→5FP/3FN, AUROC0.756→0.828로 개선됐지만 이전 모델보다 누락 증가가 남아 운영 채택하지 않는다. [근거·검증·리스크·롤백](docs/history/SELECTION_VALIDATION_20261010.md).

0.4.30: 비교 보고서에0.5 기준 예측 분포·한쪽으로만 판정하는 경고·균형 정확도를 추가했다. ㅇ 뒷면 엣지 정상7/결함1 반영 뒤 round20 tiles가 검증 정상12개를 모두 결함으로 판단해 새 모델은 채택 보류했다. 누락0을 성공으로 오해하지 않도록 표시하며 임계값/자동 라우팅은 변경하지 않는다. [라벨·실험·리스크·롤백](docs/history/IEUNG_ROUND20_VALIDATION_20261010.md).

0.4.29: `listing-infer <manifest> <checkpoint> <새 report.json> --device mps`는 val 매물의 지원 구역 전체를 실제 추론하고 매물별 정상/결함 점수·보류·반사·사진 부족·미지원 항목을 집계한다. 사람 정답/결함 점으로 구역을 선택하지 않으며 train/test 사진을 읽지 않는다. 14매물/152엣지 구역 실행과 기존 보고서41구역 점수 일치를 검증했다. 학습 라벨·자동 Gemini 분기는 변경하지 않는다. [실행 결과·리스크·롤백](docs/history/LISTING_INFERENCE_VALIDATION_20261010.md).

0.4.28: `point-experiment <snapshot> <새 폴더> --balance --edge-input tiles --epochs 20`은 전체3×3구역 특징과 구역을 고정2×2로 나눈 타일의 max 특징을 합치는 엣지 전용 선택 실험이다. 타일 정답 복제/사람 결함 좌표 입력 없이 구역당 한 loss만 사용하며 probe/benchmark도 동일 전처리를 재사용한다. PSA10 자료는 사용자 확인한 뒷면 엣지24구역만 정상으로 추가했다. 동일 검증 누락4→2·AUROC0.706→0.800, 오탐5→6·추론 약4.7배 증가로 운영 채택 보류. [자료·실험·리스크·롤백](docs/history/PSA10_TILES_VALIDATION_20261010.md).


0.4.25: `point-benchmark <snapshot> <checkpoint> <새 report.json> --device mps`는 최근 구역/좌표/테두리 확대 체크포인트의 val 구역 추론 시간을 측정한다. 기존 추론과 같은 로더·전처리를 사용하며, 1회 준비 후 구역마다 3회 측정한다. 이미지 읽기부터 CPU 결과 복사까지 포함해 GPU 비동기 실행 완료를 기다린다. 초기 로딩은 별도 기록한다. 최종시험·학습·모델선택·라벨 변경·Gemini 호출은 없다. 구역 시간은 매물 전체 시간으로 해석하지 않는다. 메모리·동시 부하는 미측정이다. [실측과 롤백](docs/history/POINT_BENCHMARK_VALIDATION_20261010.md).

0.4.19: `region-review-plan --skip-card ID`를 반복 지정하면 완료 카드와 같은 실물 그룹을 후보에서 제외한다. 제외 목록은 계획 JSON에 기록하며 라벨·학습 자료는 삭제하지 않는다. 검토 화면도 같은 종류의 유효한 결함 좌표가 저장돼 있으면 위치 재입력을 요청하지 않는다. round11 학습 결과와 롤백은 docs/history/POINT_ROUND11_VALIDATION_20261010.md 참고.

0.4.17의 `point-experiment ... --balance`는 실물별 기본 가중치를 계산한 뒤 train의 정상/결함 유효 가중치 합으로 양성 보정 비율을 정하는 선택 실험입니다. val/test로 비율을 배우지 않고 val 모델선택 loss는 기존 실물 가중 BCE 그대로 유지합니다. 최종 학습 가중치는 클래스 보정을 포함하므로 실물별 총합이 서로 같다고 해석하면 안 됩니다. 기본값은 꺼져 있고 운영 모델/임계값을 자동 교체하지 않습니다. [실험 결과·검증·롤백](docs/history/POINT_BALANCE_VALIDATION_20261010.md).

## 0.4.15 — 신규 검증 카드의 고정 모델 비교

0.4.16의 `point-compare <snapshot> <새 결과.json> <report1.json> <report2.json> --reference <이전 snapshot>`은 좌표 보강 학습 전후의 동일 val 입력을 검사하고 혼동행렬·실물별/앞뒷면별 오류·기준별 지표를 검산합니다. 기존 region-compare와 분리하며 point_validation 보고서만 받습니다. 사진 해시·실물 그룹·구역·좌표·정답이 달라지면 비교를 차단하고, train만 바뀐 snapshot은 허용합니다. 기준과 모델을 자동 선택하지 않습니다. [ㄴ 학습 결과](docs/history/POINT_ROUND10_VALIDATION_20261010.md).

`point-probe`는 새 val 카드에 저장한 사람 지점/구역 라벨로 기존 구역 모델과 좌표 보강 모델을 같은 고정3×3 입력·기준0.5에서 비교합니다. CPU 전용 진단이며 학습·모델선택·최종시험·Gemini 호출은 수행하지 않습니다. 전체 `gradable`이 null이어도 관찰한 위치만 채점하며, null/반사로 제한된 정상 구역은 정상으로 추정하지 않습니다.

```sh
.venv/bin/card-condition point-probe artifacts/point-evidence-20261010-round9.jsonl artifacts/new-point-probe.json artifacts/region-baseline-20261010-round6-epochs20/model.pt artifacts/point-grid-augmented-20261010-round8-epochs20/model.pt --card ㄱ --history data/baseline-20261008.jsonl --history data/expanded-20261008.jsonl --history data/sides-20261008.jsonl --history artifacts/regions-labeled-20261010-round8.jsonl
```

새 카드마다 `--card`를 반복하고, 해당 카드가 처음 등장하기 **전**의 모든 개발 manifest를 `--history`로 제공하세요. 이력의 ID·실물 그룹·디코딩 이미지 해시 또는 체크포인트의 개발 이력과 겹치면 차단합니다. 이미 진단한 ㄱ을 같은 조건으로 재현한 결과는 새로운 독립 검증으로 세지 않습니다. 같은 실물의 다른 사진은 사람이 같은 group을 지정해야 합니다. test 분할 사진은 읽지 않으며 기존 산출물을 덮어쓰지 않습니다. 진단 결과를 본 카드는 최종시험용으로 옮기지 않습니다.

실물 수와 구역 수는 별도 기록합니다. 출력은 보정된 신뢰도/전체 상태 점수/구매 판단이 아니며, 운영 모델을 자동 교체하지 않습니다. [검증·리스크·롤백](docs/history/POINT_PROBE_VALIDATION_20261010.md).

## 0.4.3 — 구역 모델 비교

0.4.5는 후보 확대 화면에 `이 항목 검토 완료 · 미확인도 완료로 저장 가능` 체크를 추가한다. 정답과 별도의 `region_reviews` 기록이며 미확인을 정상으로 바꾸거나 학습 정답으로 사용하지 않는다. 완료한 면/종류는 추가 정상 후보에서 제외한다. 카드 영역을 바꾸면 완료 기록을 초기화한다. [검증 기록](docs/history/REVIEWED_UNKNOWN_VALIDATION_20261009.md).

0.4.4의 `region-review-plan <manifest> <checkpoint> <새 plan.json>`은 train의 면별 정상 후보 중 아직 구역 확인을 끝내지 않은 항목만 점수화한다. 앞뒷면/종류별 정상 실물 수가 부족한 쪽, 그 안에서는 출력0.5와 가까운 구역을 우선해 최대3실물을 고른다. 관찰 제한과 이미 완료된 항목은 제외하며 정답은 자동 변경하지 않는다. 결과의 `review_query`를 라벨 화면 주소 뒤에 붙이면 해당 구역 확대와 입력칸으로 이동한다. [검증·사람 확인 목록](docs/history/REGION_ACTIVE_REVIEW_VALIDATION_20261009.md).

`region-experiment <snapshot> <새 디렉터리> --backbone resnet18 --epochs 20`으로 기존 MobileNet과 특징 추출 모델만 비교할 수 있다. 기본 모델은 MobileNet이며 구형 체크포인트도 그대로 읽는다. `--group-balance`는 train 실물 그룹별 영향력을 균등화하는 별도 선택 옵션이다. 두 옵션 모두 운영 모델을 자동 교체하지 않는다.

`region-compare <snapshot> <새 결과.json> <report1.json> <report2.json> ...`는 같은 val 사진 해시·구역·정답·지원 출력인지 검사하고 오탐/누락을 다시 계산한다. 실물 그룹·앞뒷면별 오류 목록을 함께 제공한다. 모델이나 정답을 자동 선택/수정하지 않는다. [비교 결과와 검증](docs/history/REGION_BACKBONE_VALIDATION_20261009.md).

정상 보강 화면은 train의 결함 종류·실물 다양성에 더해 앞면/뒷면별 정상 사례가 부족한 쪽을 우선한다. 한 번에 최대3실물이며 저장된 정답은 유지한다. 모델 불확실성 기반 능동학습은 아직 아니다.

## 구현된 범위

- 앞면/뒷면 각각 MobileNetV3 Small 특징을 추출하고 결합해 5개 이진 출력 학습.
- `gradable`: 사진 묶음에서 상태를 평가할 수 있는지. 나머지 4개: 센터링/모서리/엣지/표면의 관찰 가능한 결함 유무.
- 첫 기준선은 ImageNet backbone을 고정하고 분류 head만 전이학습한다.
- 누락된 면, 미확인 라벨(null), 그룹/동일 이미지의 split 누출을 처리한다.
- 검증 loss가 가장 낮은 epoch를 저장한다. 일반 면별 실험은 train/val만 처리하며 시험 지표는 자동 계산하지 않는다.
- 추론은 항상 `requires_gemini: true`. 검증되지 않은 softmax/sigmoid 수치는 보정된 신뢰도가 아니다.
- 점수 0–100, 결함 위치, 공식 등급, 진위·동일 실물 판정은 아직 구현하지 않았다.

## 설치 및 실행

이 폴더에 Python 3.12 전용 `.venv`가 준비되어 있다. 재설치 시 Python 3.11+ 사용:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/card-condition prepare /path/to/photos data/review.jsonl
# review.jsonl에서 front/back, group, split, labels를 사람이 채운 뒤 labels.jsonl로 저장
.venv/bin/card-condition validate labels.jsonl
.venv/bin/card-condition train labels.jsonl artifacts/model-v1.pt --epochs 5 --device auto
.venv/bin/card-condition evaluate labels.jsonl artifacts/model-v1.pt --device auto > artifacts/evaluation.json
.venv/bin/card-condition predict artifacts/model-v1.pt data/front.jpg --back data/back.jpg
```

`auto`는 사용 가능한 MPS 또는 CPU를 선택한다. 학습 첫 실행만 torchvision 공식 pretrained 가중치를 내려받는다. Gemini/eBay API는 호출하지 않는다. 모델 파일을 덮어쓰지 않으므로 새 버전 경로를 사용한다. `--scratch-smoke`는 무작위 backbone의 코드 테스트 전용이며 실제 모델 학습에 사용하지 않는다.

## 라벨 작성

`labels.example.jsonl`은 형식 예시로 이미지가 포함되지 않아 그대로 학습할 수 없다.
JSONL 한 줄 = 같은 실물 카드의 앞·뒷면 묶음. 경로는 manifest 기준 상대경로 또는 절대경로.

- `group`: 같은 실물/중복 매물은 같은 값. 앞뒷면이 같은 실물인지 사람이 확인한다.
- `split`: train / val / test. 같은 실물·유사 사진은 같은 split. 정확한 픽셀 중복은 코드가 검사하나 유사 사진까지 자동 검출하지 않는다.
- 모든 라벨 키를 기입. `1`=관찰됨/평가 가능, `0`=충분히 관찰한 후 없음/평가 불가, `null`=미확인.
- `gradable`은 사람이 0/1로 입력해야 한다. 1이면 서로 다른 앞뒷면 이미지가 필수다.
- 낮은 해상도/반사/슬리브로 안 보이는 부분을 결함 없음(0)으로 라벨링하지 않는다.
- 예: 뒷면 우측 하단에 빛이 반사됐다면 해당 결함 항목은 `null`(미확인)로 남긴다. 다른 위치에서 같은 결함이 분명히 보인다면 그 항목은 `1`로 기록하고, 관찰 근거에 두 위치를 구분해 적는다. 반사만으로 결함 있음(1), 상태 불량 또는 구매 제외를 정답으로 만들지 않는다. 반사 위치를 적고 해당 면의 `visibility_issues`에 `glare`를 선택한다.
- `gradable=0`은 사진으로 신뢰할 만한 전체 상태 평가가 어려움을 뜻할 뿐 카드 상태가 나쁘거나 구매 가치가 없다는 뜻이 아니다. 보이는 부분이 양호한 매물은 추가 각도 사진이나 사람 검토 대상으로 남길 수 있다.
- defect는 위치/정도 없이 사진 묶음 단위 유무만 다룬다. severity와 센터링 허용치 기준을 사람이 일관되게 정의한 뒤 라벨링한다.
- train에서 두 클래스가 모두 존재하는 항목만 학습한다. 해당 항목은 val에도 두 클래스가 필요하다.
- Gemini 답변은 비교 데이터일 뿐 사람 정답으로 복사하지 않는다.

## 독립 사용 계약

구역 모델은 사람이 지정한 카드 영역과 위치를 입력한다:

```python
from card_condition.region_model import RegionAnalyzer
model = RegionAnalyzer("artifacts/region-baseline-20261009-next/model.pt")
result = model.analyze("photo.jpg", [0.05, 0.05, 0.95, 0.95], "lower_right",
                       unknown_labels=["surface_defect"])
# 가려진 표면은 null + observation_limited. requires_gemini는 항상 True.
```

```sh
.venv/bin/card-condition region-predict artifacts/region-baseline-20261009-next/model.pt photo.jpg --card-box 0.05 0.05 0.95 0.95 --area lower_right --unknown surface_defect
```

관찰 제한은 호출자가 지정한다. 반사는 자동 검출하지 않는다. 구역에 적용되지 않는 항목과 미학습 항목도 null이며 사유를 반환한다. 반환 확률은 보정된 신뢰도·전체 상태 점수·등급이 아니다. 입력/모델 오류는 예외이므로 소비자는 Gemini fallback으로 처리한다.

```python
from card_condition.model import Analyzer
analyzer = Analyzer("artifacts/model-v1.pt")
result = analyzer.analyze("front.jpg", "back.jpg")
# probabilities: 학습한 항목만 0~1, 학습하지 않은 항목은 None
# requires_gemini: 현재 항상 True
```

입력/모델 파일 오류는 예외를 발생시킨다. 소비자는 오류와 `requires_gemini`를 Gemini fallback으로 처리해야 한다. 아직 PokeCollector worker에 연결하지 않았다. SQLite/네트워크/소비 앱의 정책을 모델 패키지에 넣지 않는다.

## 평가 및 현재 한계

`evaluate`는 항목별 TP/TN/FP/FN, miss rate, false positive rate, 샘플별 지연을 기록한다. `hypothetical_call_reduction`은 사용자가 정한 확률 임계값의 **가상 정책**일 뿐 실제 절감 실적이 아니다. `unsafe_candidates`와 미라벨 후보 수를 함께 확인해야 한다. 모델 확률은 아직 calibration하지 않았다. 실제 절감량은 항상 0으로 보고한다.

224px 전체 사진 기준선은 미세한 스크래치/백화를 놓칠 수 있다. 기존 PokeCollector의 타일은 이미지 중앙을 카드라고 가정하므로 경계 검증 없이 이식하지 않았다. 다음 단계는 실제 데이터로 이 한계를 측정한 뒤 영역/고해상도 처리 여부를 정하는 것이다.

## 남은 TODO

- [ ] 사용자 실매물 데이터 경로 확인 및 라벨 일치도 점검
- [ ] 사람 라벨과 실제 Gemini 결과로 기준선 확보
- [x] 실제 데이터 head 학습과 회귀평가 실행 (운영 성능은 미달)
- [x] MobileNet 마지막 특징 블록 부분 미세조정을 고정 특징 기준선과 비교 (운영 채택 보류; [결과](docs/history/FINE_TUNE_LAST_VALIDATION_20261009.md))
- [x] 면별 반사 위치 라벨 저장·내보내기 지원 (모델 적용 전 데이터 준비; [검증](docs/history/GLARE_LOCATION_VALIDATION_20261009.md))
- [x] 반사 위치별 검증 오류·미확인 라벨 수·위치 미지정 목록 집계 (재학습 없이 기존 예측 재사용; [결과](docs/history/GLARE_SLICE_VALIDATION_20261009.md))
- [x] 항목별 임계값·precision/recall 비교: 누락을 없애면 오탐 증가, 임계값만으로 해결되지 않음 ([결과](docs/history/THRESHOLD_VALIDATION_20261009.md))
- [x] 면별 모델 독립 추론 API/CLI, ResNet18 비교, validation 보고서 비교·실제 추론 속도 측정 ([결과](docs/history/BACKBONE_INFERENCE_VALIDATION_20261009.md))
- [x] 3×3 구역별 명시적 결함 라벨 및 학습 준비 감사 ([검증](REGION_DATA_VALIDATION_20261009.md))
- [x] 구역 라벨68개로 MobileNet 고정 특징+head 기준 실험 ([결과](docs/history/REGION_EXPERIMENT_VALIDATION_20261009.md)); 정상 사례 보강은 [사람 확인 목록](docs/history/REGION_HUMAN_REVIEW_20261009.md)
- [x] 구역 추론 API/CLI, 새 라벨96개 재실험 ([검증](docs/history/REGION_INFERENCE_VALIDATION_20261009.md))
- [ ] 결함별 위치/세부 영역 모델 실험, 필요 시 backbone 미세조정
- [ ] validation에서 routing 임계값 결정 후 test에서 오류와 절감 효과 측정
- [ ] 모델 버전별 성능 근거 확보 후 PokeCollector adapter 및 재시작/fallback 검증

원본 계획: PokeCollector의 `CONDITION_ANALYSIS_TODO.md`. 이 패키지는 그 계획의 구현 시작점이다.

## 구역별 결함 라벨 — 사람 확인 단계

면별 카드 영역을 지정한 뒤 `앞면/뒷면 구역별 결함 위치 (선택 사항)`을 펼친다. 선택한 카드 영역을 가로·세로 3등분한다. 모서리는 네 귀퉁이, 엣지는 중앙을 제외한 구역, 표면은 모든 구역에서 기록한다.

- 결함이 실제 보이면 `이 구역에서 결함 관찰됨`. 해당 면의 같은 결함도 관찰됨이어야 저장된다.
- 해당 항목을 충분히 확인한 구역만 `결함 없음`. 빛 반사로 가린 항목은 `미확인`으로 유지한다. 한 구역에서도 항목별 관찰 가능성이 다를 수 있다.
- 앞면/뒷면 전체의 결함 있음으로부터 나머지 구역이 정상이라고 추정하지 않는다. 카드 영역을 바꾸면 위치 라벨을 재확인한다.
- 위치 라벨은 `side_annotations.<side>.region_labels.<area>`에 저장된다. 미지정은 정상 학습 자료가 아니다. 현재 면별 모델은 이 위치 라벨로 자동 재학습되지 않는다.

저장·내보낸 새 snapshot의 준비 상태 확인:

```sh
.venv/bin/card-condition region-audit data/new-snapshot.jsonl artifacts/new-region-audit.json
.venv/bin/card-condition region-experiment data/new-snapshot.jsonl artifacts/new-region-model --epochs 5 --device auto
```

train/val의 명시적 라벨만 구역 자료로 만들고 test는 읽지 않는다. 출력의 `positive_faces_without_region_labels`는 사람 확인이 필요한 면/결함 목록이다. `ready_for_experiment`는 클래스 존재 조건이며 정확도 보증이 아니다. 사람이 사진을 판단해야 하는 단계에서는 확인할 자료를 준비하고 응답을 기다리며, 관련 없는 테스트·도구 작업은 계속한다.

구역 모델 최종평가는 개발에 노출되지 않은 별도 test-only manifest로 실행한다:

```sh
.venv/bin/card-condition region-evaluate data/unseen-test.jsonl artifacts/region-baseline-20261009-complete/model.pt artifacts/region-final.json --history artifacts/regions-labeled-20261009-complete.jsonl
```

`--history`는 모든 이전 개발 snapshot마다 반복한다. 카드 ID·실물 그룹·원본 사진의 디코딩 해시가 개발 자료와 겹치면 보고서를 생성하지 않는다. 분할 미지정 자료는 개발 이력 검사에서 제외되며, 다른 사진으로 찍은 같은 실물은 사람이 그룹으로 연결해야 한다. 최종평가에서 학습·임계값 조정은 하지 않는다. 미확인 정답은 채점에서 제외한다. 현재 새 독립 test 자료가 없어 실제 최종평가는 아직 수행하지 않았으며, 학습/모델선택 자료를 test로 옮기지 않는다.

## 근거

- https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.mobilenet_v3_small.html
- 기존 `pokecollector/worker.py:281`: Gemini 호출 및 저장 경계
- 기존 `pokecollector/providers.py:307`: 앞뒷면/상태 결과 계약
- 기존 `pokecollector/card_image_tiles.py`: 중앙 영역 가정의 crop 처리

롤백: 모델 소비 앱에는 변경이 없다. 이 독립 프로젝트 디렉터리를 보관하거나 삭제하면 된다.

## 제공된 learn 사진

`data/learn-review.jsonl`에 원본 경로·크기와 빈 라벨을 준비했다. `learn/a`는 전체 앞면과 별도 확대 사진이며 뒷면이 없다. 서로 일러스트레이터 표기도 달라 같은 실물로 묶으면 안 된다. b/c는 각각 앞뒷면 후보이나 동일 실물 확인은 사용자에게 필요하다. 뒷면의 빨간 사각형은 주석 오버레이로 보이므로 손상 라벨에 포함하지 않는다. 세 폴더만으로 학습/검증/테스트의 클래스 균형이나 일반화 성능을 주장할 수 없다.

## 0.2 — 로컬 라벨 검토 화면

```sh
.venv/bin/card-condition review data/learn-review.jsonl --port 8766
```

http://127.0.0.1:8766 에서 사진을 확대하고 앞면/뒷면, 동일 실물 확인, 5개 라벨, split, 검토자, 관찰 근거를 입력한다. 불확실한 결함은 미확인으로 남긴다. 제외 체크한 묶음은 export에서 빠진다. 수정 후 저장하면 원본 JSONL 옆에 시각별 `.bak` 백업을 남긴다. 다른 화면에서 저장한 뒤 이전 화면이 덮어쓰려 하면 충돌로 막는다.

저장된 라벨을 검증한 후 JSONL 내보내기를 누르면 별도 타임스탬프 파일을 만든다. 잘못된 이미지 경로·누락 라벨·동일 실물 split 누출은 export를 차단한다. 유효한 부분 데이터는 내보낼 수 있지만 train/val 클래스가 부족하면 학습 준비 완료로 표시하지 않는다.

```sh
.venv/bin/card-condition check data/내보낸파일.jsonl
.venv/bin/card-condition train data/내보낸파일.jsonl artifacts/model-v2.pt
```

`check`와 `train`은 같은 클래스 검증 규칙을 사용한다. 클래스가 모두 존재해도 충분한 표본이나 정확도가 보장되지는 않는다. 초기 3개 묶음은 라벨링 연습/자료 정리에 적합하며, 클래스 균형을 갖춘 독립 train/val/test 자료를 추가해야 한다. 서버는 loopback에서만 실행하며 Ctrl+C로 종료한다. 데이터는 외부에 전송하지 않는다.

0.2 롤백: 서버 종료 후 `.backups/step2/`의 data.py/model.py/cli.py를 card_condition/에, pyproject.toml을 루트에 복원하고 0.1을 재설치한다. 라벨 JSONL은 최신 파일과 `.bak`를 보존한다.

## 추가 라벨로 재실험하기

원본 라벨을 보존하고 이전 실험의 분할을 우선해 고정합니다. 제외 체크된 자료는 빠집니다. `--unassigned train`은 미지정 자료를 실험 파일에서만 학습용으로 지정합니다.

```sh
.venv/bin/card-condition snapshot data/learn-review.jsonl data/next-experiment.jsonl --reference data/expanded-20261008.jsonl --unassigned train
```

출력 JSON의 split_changes와 readiness를 확인한 뒤 train/evaluate를 실행하세요. 새 이름으로 저장하며 기존 파일은 덮어쓰지 않습니다. 다른 촬영의 동일 실물은 같은 group을 지정해야 합니다. 실제 결과는 EXPERIMENT_20261008_EXPANDED.md 참고.

## 앞뒤별 관찰과 카드 영역
라벨 화면의 새 기능 항목을 펼치고 선택된 앞면/뒷면에서 카드 전체를 감싸는 좌상단과 우하단을 차례로 클릭하세요. 숫자 0~100% 입력도 지원합니다. 면별 평가 가능 여부와 결함을 별도로 기록하고, 반사·흐림·가림·잘림·저해상도·비스듬한 촬영 등 관찰 제한 사유를 복수 선택한 뒤 저장하세요. 빛 반사를 선택하고 카드 영역을 지정하면 반사 때문에 확인하기 어려운 위치를 3×3 구역에서 여러 곳 고를 수 있습니다. 위치 선택은 선택 사항이며 기존 라벨은 그대로 유효합니다. 반사가 있는 위치는 결함이나 정상으로 자동 판정하지 않고, 다른 위치에서 실제 보이는 결함은 별도로 기록할 수 있습니다. 이 위치 정보는 현재 기록·검토용이며 모델 입력이나 Gemini 호출 분기에 아직 쓰이지 않습니다. 기존 전체 라벨은 복사/변경하지 않습니다. side_annotations는 JSONL 내보내기와 snapshot에 보존됩니다. 기본 train은 사진 묶음 라벨을 사용하고, side-experiment는 면별 라벨/영역을 사용합니다. 기울어진 카드의 원근 보정/결함 위치 박스는 다음 단계입니다.

`side-experiment`의 `visibility_counts`와 `visibility_validation_metrics`는 train/val 관찰 사유의 분포와 검증 오류를 보여주는 진단 수치다. 관찰 사유 자체를 학습하거나 자동 상태 판단에 사용하지 않는다. 최신 실험과 남은 데이터 보완 사항은 `docs/history/VISIBILITY_SLICE_VALIDATION_20261009.md` 참고.

`glare_area_counts`와 `glare_area_validation_metrics`는 반사 위치별 train/val 수와 val 오류를 보여준다. `glare_location_coverage`는 위치 미지정 면을 표시하고, `glare_area_unknown_labels`는 해당 위치의 미확인 정답 수를 따로 센다. 미확인은 정상으로 계산하지 않는다. 여러 위치를 선택한 면은 각 위치에 포함되므로 위치별 수치를 합산하면 중복된다. 위치 정보는 모델 입력에 사용하지 않으며, `reslice-visibility`로 기존 예측을 재집계할 수 있다.

관찰 제한 사유만 추가했다면 기존 모델을 재학습할 필요 없이 검증 오류를 다시 집계할 수 있다. `reslice-visibility <이전 snapshot> <새 snapshot> <이전 report.json> <model.pt> <새 report.json>`을 실행한다. 학습·검증 면, 이미지 픽셀, 박스, 정답이 기존 체크포인트와 다르면 중단한다. test는 읽지 않고 모델 가중치와 예측은 그대로 둔다. 새 보고서는 여전히 개발용이며 Gemini 호출을 줄이지 않는다.

`routing-audit <snapshot> <validation report.json> <새 결과.json>`은 앞·뒷면이 모두 있는 매물에서 두 면의 `gradable` 예측과 결함 예측을 함께 검사한다. 여러 문턱값에서 **가상의** Gemini 생략 후보, 사람이 확인한 위험 후보, 미확인 후보를 집계할 뿐 호출 경로를 변경하지 않는다. 현재 데이터 결과는 [매물 단위 라우팅 검증](docs/history/ROUTING_AUDIT_20261009.md)에 기록했다.

같은 명령의 `per_label_threshold_analysis`는 미확인 정답을 제외하고 각 항목의 출력값 경계에서 TP/TN/FP/FN, precision/recall, 누락률·오탐률을 비교한다. `zero_miss_candidate`와 `zero_false_positive_candidate`는 val에서 찾은 비교 후보이며 운영 설정이 아니다. 양성·음성이 모두 없는 항목은 후보를 제공하지 않는다. 최대 출력 바로 위의 경계는 전부 음성으로 판정하는 경우를 표현하며 1보다 클 수 있다. 선택한 임계값은 새로운 독립 최종평가를 거쳐야 한다.

### 학습 라벨 보강 전후 비교 (0.4.6)

`region-compare <새 snapshot> <비교.json> <이전 report.json> <새 report.json> --reference <이전 snapshot>`은 학습 자료가 바뀐 실험도 비교합니다. 두 snapshot의 val 이미지 픽셀 해시·실물 그룹·구역 좌표·정답이 모두 같아야 하며, 보고서 지표를 예측에서 다시 계산합니다. `--reference`는 여러 번 지정할 수 있습니다. 검증 자료가 달라지면 비교를 거부하며 모델을 자동 교체하지 않습니다. y의 새 표면 결함 라벨 반영 결과는 [재학습 검증 기록](docs/history/REGION_ROUND2_VALIDATION_20261009.md)을 참고하세요.

`0.4.7`의 구역 비교 결과에는 `by_group`과 `group_error_rates_at_05`가 추가됩니다. 앞뒷면 구역을 같은 실물 그룹에 합친 후 실물마다 같은 비중으로 오탐률·누락률을 평균합니다. 해당 정상/결함 정답이 없는 그룹은 그 평균에서 제외하고 분모인 실물 수를 표시합니다. 이는 전체 카드 등급 정확도가 아닙니다. 최신 보강 결과와 앞뒷면 자료 편향은 [3차 검증 기록](docs/history/REGION_ROUND3_VALIDATION_20261010.md)을 참고하세요.

`0.4.8`의 `region-audit`는 `group_class_counts_by_side`로 train/val 앞뒷면별 정상0·결함1 실물 수를 표시하고 `coverage_gaps`에 빠진 클래스를 기록합니다. 같은 실물의 여러 구역은 한 번만 세며, null과 검토 완료 표시는 정상 정답으로 세지 않습니다. 이는 진단 정보이며 기존 학습 가능 조건이나 사람 정답·분할을 변경하지 않습니다.

`0.4.9`의 `region-compare`는 검증을 통과한 보고서에 `threshold_analysis`를 추가합니다. 고정 기준0.1~0.9별 혼동행렬, 정밀도·재현율·오탐률·누락률, 앞뒷면별 오류와 실물 동등 가중 오류율을 비교합니다. 정답이 null인 구역은 제외하며 분모가 없으면 비율은 null입니다. 기준과 같은 값은 결함으로 셉니다. 학습/최종평가 데이터를 사용하거나 최적 기준·운영 모델을 자동 선택하지 않습니다. [실험 결과와 변경 파일](docs/history/REGION_THRESHOLD_VALIDATION_20261010.md).

`0.4.10`의 검토 화면은 앞/뒷면별 **결함 지점 여러 곳 찍기**를 지원합니다. 결함 종류를 선택하고 클릭 모드를 켜면 사진을 누를 때마다 번호가 붙습니다. 개별 삭제 또는 키보드 가로·세로% 입력도 가능합니다. 라벨 저장으로 원본 이미지 기준0~1 좌표 `{label,x,y}` 목록을 `side_annotations.<side>.defect_points`에 보존합니다(EXIF 방향 적용). 좌표를 찍는 것만으로 기존 결함 정답을 변경하지 않으며 기본 구역 학습은 이 점을 사용하지 않습니다. 카드 영역을 바꾸면 점이 삭제되고, 사진을 바꾸면 해당 면 주석이 초기화됩니다. [검증·리스크·롤백](docs/history/DEFECT_POINTS_VALIDATION_20261010.md).

`0.4.11`의 `point-audit <manifest> <새 보고서.json>`은 train/val의 사람 지점을 카드 영역 기준3×3 구역으로 매핑하여 기존 구역 정답1과 일치 / 정상0과 충돌 / 구역 미확인을 구분합니다. test는 읽지 않으며 원본 정답·분할·학습 입력을 변경하지 않습니다. 한 구역의 여러 점을 독립 학습 표본으로 세지 않습니다. [s 실제 좌표 검증](docs/history/POINT_AUDIT_VALIDATION_20261010.md).

`0.4.12`의 `point-dataset <manifest> <새 디렉터리>`는 지점 주변(카드 가로·세로의 각1/3)을 별도 `patches.jsonl`로 만듭니다. 해당 면도 결함1인 사람 지점만 양성으로 사용하며 다른 결함 항목은 null입니다. 정상은 사람이 명시한 구역0만 사용하고, 같은 종류의 지점이 있는 구역이나 관찰 제한 구역은 제외합니다. 실물별 클래스 수와 train/val 부족 클래스를 `report.json`에 기록합니다. 학습 실행 기능은 아니며 기존 `region-experiment`의 입력을 교체하지 않습니다. [실제 자료·검증·제약](docs/history/POINT_DATASET_VALIDATION_20261010.md).

`0.4.13`의 `point-experiment <manifest> <새 디렉터리> --epochs 20`은 선택적 좌표 보강 학습입니다. 고정3×3으로 정상/결함 모두 같은 형상으로 자르고, 기존 사람 구역 라벨에 사람 지점의 해당 결함1을 합칩니다. 같은 구역·종류의 점은 한 번만 사용하며 미확인은0으로 채우지 않습니다. 점과 정상 구역 라벨이 충돌하면 중단합니다. train/val 실물별 동등 가중치, val 모델선택, test 격리, 입력 명세·별도 point_grid_v1 체크포인트를 제공합니다. 당시에는 자동 연결하지 않았으며, 현재 추론 및 최종평가 연결은 아래 0.4.67 절을 참고하세요. 원본 라벨은 변경하지 않으며 개발 결과로 운영 모델을 교체하지 않습니다. [실험·대조 결과](docs/history/POINT_GRID_VALIDATION_20261010.md).

`0.4.14`의 위치별 근거 처리(point-dataset/point-experiment)는 전체 카드의 `gradable`이 null이어도 명시적 지점/구역 라벨을 사용할 수 있습니다. 전체 평가 가능 여부를0/1로 채우거나 동일 실물 앞뒤 확인으로 간주하지 않습니다. 기본 load_manifest와 전체 카드·기존 구역 학습/최종평가의 필수 조건은 유지합니다. 모든 라벨 타입, 실물 그룹·이미지 해시 분할 누수, 사진 읽기와 주석 검사는 유지합니다. 면 정상0만으로 구역 정상0을 생성하지 않습니다.

## 데이터 누수 방지: 개발 / 회귀 / 최종평가

- `side-experiment`는 train/val만 특징 추출·학습·지표 계산한다. test 사진이나 정답을 바꿔도 학습 가중치·모델선택 결과는 같아야 한다.
- 화면의 test는 별도 평가 후보일 뿐이다. 이미 본 g/r/z는 회귀평가이며 새 최종시험이 아니다.
- `side-evaluate --kind regression`은 모델선택이 끝난 뒤 필요할 때만 실행한다. 반복 결과를 최종 성능으로 주장하지 않는다.
- `--kind final`은 test만 있는 별도 manifest와 **모든 과거 개발 manifest**를 --history로 제공해야 한다. 학습/val 및 과거 회귀 자료와 id/group/정규화 픽셀 해시가 겹치면 예측 전에 차단한다.
- 누수 검사 metadata가 없는 구형 면별 모델은 새 학습 명령으로 다시 생성해야 한다. 기존 파일은 덮어쓰지 않는다.

```sh
# 개발: 모델선택용 결과만 반환
TORCH_HOME=artifacts/torch-cache .venv/bin/card-condition side-experiment data/sides-20261008.jsonl artifacts/new-development
# 명시적 회귀평가
.venv/bin/card-condition side-evaluate data/sides-20261008.jsonl artifacts/new-development/model.pt artifacts/new-regression.json --kind regression
# 새 실물만 담긴 final-only.jsonl을 확보한 뒤 실행 (현재 준비되지 않음)
.venv/bin/card-condition side-evaluate data/final-only.jsonl artifacts/new-development/model.pt artifacts/new-final.json --kind final --history data/baseline-20261008.jsonl --history data/expanded-20261008.jsonl --history data/sides-20261008.jsonl
```

`--history`를 누락하거나 불완전하게 제공하면 과거 노출을 전부 검사할 수 없다. 다른 촬영·리사이즈·크롭으로 나온 같은 실물은 사람이 같은 group을 지정해야 한다. 최종 결과를 보고 다시 개발하면 그 시험셋은 회귀 자료로 전환하고 새 최종자료를 확보한다. 현재 crop 평가는 사람 지정 영역을 전제로 하며 자동 카드 검출 성능은 포함하지 않는다. 기존 pair용 evaluate는 회귀평가 결과임을 명시하며 최종평가 경로로 사용하지 않는다.

### 전체 카드 + 확대 타일 실험
`side-experiment ... --tiles`는 사람이 지정한 영역 전체와 중첩된 네 구역을 함께 학습합니다. `--crop`과 동시에 사용할 수 없습니다. train/val만 사용하며 기본 입력 모드는 바뀌지 않습니다. 현재 실험에서 결함 검출 개선이 없어 운영 적용을 보류했습니다. 결과·검증·롤백: [TILES_VALIDATION_20261008.md](TILES_VALIDATION_20261008.md).

### 학습 클래스 불균형 실험
`side-experiment ... --balance`는 train의 음성/양성 수로 학습 가중치를 계산합니다. unknown은 제외하고 val의 모델선택 loss는 기존대로 유지합니다. 기본값은 비활성입니다. 결함 검출과 오탐이 함께 증가했으므로 운영 채택하지 않았습니다. [결과·변경·롤백](BALANCE_VALIDATION_20261008.md).

`side-experiment ... --fine-tune-last`는 기존 고정 특징 기준선과 비교하기 위한 별도 실험 옵션입니다. MobileNet의 마지막 특징 블록과 분류 head만 학습하며 기본값은 비활성입니다. 현재 데이터에서는 평가 불가 오판/결함 누락이 줄지 않아 운영 채택하지 않았습니다. [비교 결과](docs/history/FINE_TUNE_LAST_VALIDATION_20261009.md).

## 0.3 — 면별 모델 독립 추론과 모델 비교

```python
from card_condition.side_model import SideAnalyzer
analyzer = SideAnalyzer("artifacts/visibility-baseline-20261009/model.pt")
result = analyzer.analyze(front="front.jpg", back="back.jpg")
# sides.front/back: 학습된 출력값, 미학습 항목은 None
# 누락된 면은 None + missing_sides에 표시. requires_gemini는 항상 True.
```

crop/tile 모델에는 사람이 확인한 정규화 카드 영역 `[left, top, right, bottom]`을 `front_box`/`back_box`로 제공해야 합니다. 좌표는 원본을 EXIF 방향에 맞춰 표시한 이미지의 0~1 범위입니다. 전체 사진 모델은 영역 없이 추론할 수 있습니다. 반환값은 보정된 신뢰도나 상태 점수가 아니며, 반사·뒷면 누락으로 정상 또는 결함을 추정하지 않습니다. 잘못된 입력/체크포인트는 예외가 발생하므로 소비 앱은 기존 Gemini fallback으로 처리해야 합니다.

```sh
.venv/bin/card-condition side-predict artifacts/visibility-baseline-20261009/model.pt --front /path/front.jpg --back /path/back.jpg
# 모델 종류만 바꾸는 별도 개발 실험. 기존 기본 모델/파일 유지.
TORCH_HOME=artifacts/torch-cache .venv/bin/card-condition side-experiment artifacts/visibility-complete-20261009.jsonl artifacts/new-resnet --backbone resnet18
.venv/bin/card-condition compare-validation artifacts/visibility-complete-20261009.jsonl artifacts/new-comparison.json artifacts/glare-location-audit-20261009.json artifacts/new-resnet/report.json
.venv/bin/card-condition benchmark-validation artifacts/visibility-complete-20261009.jsonl artifacts/new-resnet/model.pt artifacts/new-speed.json
```

`--backbone`은 기본 MobileNetV3 Small 또는 ResNet18입니다. ResNet18은 공식 torchvision ImageNet 가중치와 고정 특징 + head 학습만 비교합니다. `--fine-tune-last`와 ResNet18을 함께 쓰면 차단합니다. 구형 MobileNet 면별 체크포인트도 추론할 수 있습니다.

`compare-validation`은 동일 snapshot·같은 면/정답인지 검사하고 보고서의 혼동행렬을 예측에서 다시 검산합니다. final/regression 보고서는 개발 비교에서 차단합니다. 모델이나 임계값을 자동 선택하지 않습니다. `benchmark-validation`은 val만 사용해 한 번 준비 실행 후 각 면을 3회 측정합니다. 중앙값·p95는 이미지 읽기/전처리/추론을 포함하며 모델 초기 로딩은 별도 기록합니다. 메모리는 측정하지 않습니다. 모든 산출물은 새 경로로 저장합니다.

### 학습 횟수 비교 기록
`side-experiment ... --epochs 30`으로 학습 길이를 지정할 수 있습니다(기본5). 보고서/체크포인트는 `selected_epoch`, `best_validation_loss`를 기록하고 보고서는 선택 모델의 `training_metrics`도 제공합니다. 학습 지표는 진단용이며 성능 보증이 아닙니다. [5회/30회 비교 및 롤백](EPOCH_VALIDATION_20261008.md).

## 0.4.26 — 입력 진단과 순위·보류 평가

`input-review MANIFEST NEW_DIRECTORY --card ID`(반복 가능)는 **train 사진만** 원본 구역/224/448 비교 페이지로 내보냅니다. `point-experiment --image-size 448`은 별도 고해상도 실험이며 기본224를 유지합니다. checkpoint의 크기를 probe와 benchmark에도 적용합니다.

`point-compare`는 같은 입력/정답을 검산한 뒤 all-positive/all-negative 기준선, PR/ROC, AUROC/AP, 고정 문턱값의 보류율·오류를 기록합니다. 정답 미확인은 제외하고, 판단0건의 오류율은 null입니다. 구역 coverage는 매물 완료율이나 Gemini 절감률이 아닙니다. 이번448 실험은 오탐·누락이 증가해 채택하지 않았습니다. [실험·변경 목록·리스크·롤백](docs/history/CONSENSUS_IMPLEMENTATION_20261010.md).

## 0.4.27 — 매물별 범위 진단과 공간 블록 미세조정

`point-compare`/`region-compare`의 각 모델에 `listing_readiness`가 추가됩니다. 모든 비제외 val 매물을 분모로 사용하고, 앞뒤 42개 필수 구역 항목에서 정상·결함·보류·사진 부족·관찰 제한·미평가·미지원 사유를 보존합니다. 사람의 관찰 제한 기록을 사용하므로 자동 반사 검출이 아닙니다. 센터링/전체 관찰 가능성/동일 실물 검증을 제공하지 않아 현재 로컬 완료 후보는 항상0이며, 실제 라우팅을 바꾸지 않습니다.

`point-experiment ... --edge-input context --fine-tune-spatial`은 MobileNet 마지막 공간 블록만 추가 학습하는 선택 실험입니다. 기본 고정 backbone 경로는 유지하며, BatchNorm 통계는 고정하고 선택 epoch의 backbone과 head를 함께 저장합니다. 이번 실험은 누락이 늘어 채택 보류했습니다. [검증·변경·롤백](docs/history/LISTING_SPATIAL_VALIDATION_20261010.md).


## 0.4.35 — 관찰 제한 자동 판정 기준 모델

`visibility-experiment <manifest> <새 폴더> --epochs 20 --device mps`는 면별 관찰 제한 여부를 별도 학습한다. 명시된 visibility_issues가 있으면1, 명시적 빈 목록이고 면 gradable=1이면0이다. 미기입/미확인은 제외하며 결함 정답과 분리한다. 인간 box로 crop한224px 사진만 모델에 넣고 사유/gradable/결함 라벨을 특징으로 넣지 않는다. train/val만 읽고 클래스→실물 균등 BCE로 학습·모델선택한다. 점수0은 정상 카드나 완전한 관찰 가능성을 뜻하지 않는다.

`visibility-predict <checkpoint> <사진> --box <left> <top> <right> <bottom> --device mps`는 observation_limit_score만 반환한다. 사람 관찰 제한을 자동 해제하거나 상태/구매/운영 라우팅에 연결하지 않는다. 최초 실제 검증24면에서 제한 누락6/7·오탐3/17로 채택 보류했다. 기존 엣지 모델과 사람 라벨은 불변이며 실제 절감0건이다. [결과·변경·리스크·롤백](docs/history/OBSERVATION_MODEL_VALIDATION_20261010.md).


## 0.4.36 — 그늘·어두움 관찰 제한

면별 관찰 제한에 shadow(그늘·어두움)를 추가했다. 기존 glare(빛 반사)나 blur(흐림)로 잘못 분류하지 않는다. 기존 데이터는 그대로 유효하다. 제한의 구체적 위치를 제공하지 않는 shadow는 현재 면 전체 판정을 보류하므로 부분 관찰 가능성이 있어도 그 면의 모든 결함이 존재한다는 뜻은 아니다. 슬리브 착용 자체는 관찰 제한 정답이 아니다. [신규 자료 확인·검증](docs/history/JIEUT_DATA_VALIDATION_20261010.md).


## 0.4.37 — 관찰 제한 고정 타일 비교와 ㅈ 자료 반영

사용자가 확인한 ㅈ의 그늘·반사·슬리브 3실물 6사진을 train에 등록했다. 구체적인 상태 결함 라벨은 미확인으로 유지한다. `visibility-experiment --tiles`는 기존 고정 2×2 타일 특징을 재사용하며 사진당 정답 하나를 유지한다. checkpoint에 `input_policy`를 보존하고 `visibility-predict`도 같은 입력을 사용한다. 기존 정책 필드가 없는 checkpoint는 context로 읽는다.

동일 val 24면에서 사진 보강만으로 FN6→5/FP3→6, 별도 타일 변경은 FN5→3/FP6→15로 채택 보류했다. 관찰 가능성을 확정하거나 기존 사람 제한을 해제하지 않는다. [자료·실험·검증·롤백](docs/history/JIEUT_OBSERVATION_VALIDATION_20261011.md).

## 0.4.38 — 관찰 제한 점수 이동 진단과 단순 분류기 비교

`visibility-compare <reference report.json> <candidate report.json>`는 동일 검증 사진·box·그룹·정답·해시를 확인하고 무정보 BCE/AUROC/AP, 클래스별 점수, 동일 FP 예산의 TP를 재계산한다. 누락 감소만으로 개선을 선언하지 않는다. FP 예산은 reference의 0.5 오탐 수이며 이 사후 진단으로 운영 임계값을 정하지 않는다.

`visibility-experiment ... --centroid`는 기존 이미지 특징에서 train의 클래스·실물 균등 대표 특징만 계산한다. validation으로 epoch/임계값을 선택하지 않는다. 기존 Linear checkpoint 추론을 그대로 사용하며 score는 교정된 확률이 아니다. `epochs=0`, `selected_epoch=null`이고 history 한 행은 적합 후 측정이다. 옵션 없는 기존 학습 경로도 유지한다.

동일 24면에서 FP7/FN4, AUROC .4874로 무정보 기준 미달이므로 채택하지 않았다. 모든 결과는 Gemini fallback을 유지하고 사람 관찰 제한을 해제하지 않는다. [모의 컨설팅 합의·실험·롤백](OBSERVATION_CONSENSUS_20261011.md).

## 0.4.39 — 관찰 제한 입력 가설·사유별 진단

`visibility-experiment --interior`는 box 양끝5%를 제외하는 중앙90% 입력 실험이다. 전처리 정책을 checkpoint에 저장하고 동일 추론을 적용한다. 기본은 전체 box이며 기존 checkpoint도 그대로 읽는다. 자동 배경 분할이 아니고 외곽 제한 단서까지 제거하므로 탐색 전용이다.

`reason_diagnostics`는 사람 사유별로 학습/검증 실물 수와 제한 누락을 집계한다. 종류 예측 모델이 아니며 사유 중복이 있을 수 있다. train 지원0과 val 지원0을 구분하고 val이 없으면 recall=null이다. 동일 centroid에서 AUROC .487→.395로 악화해 후보를 채택하지 않았다. [실제 검증·기술 판단·롤백](docs/history/OBSERVATION_INPUT_VALIDATION_20261011.md).

## 0.4.40 — 카드 영역 휴먼인루프

`visibility-geometry-review <manifest> <새 폴더>`는 train 사진 중 관찰 제한 사유가 있고 전체 사진 box만 지정된 후보를 최대3실물로 묶는다. 기존 결함 지점/구역 라벨이 있는 사진은 제외한다. 검토 링크는 `geometry=<front|back>`와 사진 경로로 묶이며 기존 화면의 두 번 클릭 영역 지정 기능을 사용한다.

`box_reviewed`는 사람의 카드 영역 확인만 저장한다. 상태/결함/완전 관찰 여부를 뜻하지 않는다. box를 바꾸면 확인은 해제되며 확인 체크 후 저장해야 다음 사진으로 넘어간다. 확인한 사진은 다시 요청하지 않는다. 이번 대상은ㅈ 3실물6사진이다. 원본이 사진에 잘렸다면 보이는 범위만 지정하고, 결함과 관찰 제한 사유는 유지한다. 정확한 원근 보정/분할 기능은 아직 없다.


### 0.4.41 영역 검토 재개
미완료 영역은 새로고침해도 검토 큐에 남으며, 완료 사진은 건너뛴다. 영역 변경 시 원본 사진 기준 결함 지점을 유지한다. 첫 앞면 완료, 나머지5사진 사람 확인 대기. 상세: docs/history/GEOMETRY_REVIEW_VALIDATION_20261011.md.


### 사람 확인 box 비교 완료
ㅈ 6사진 확인 완료 후 학습box만 바꾼 동일 검증 비교에서 FP7/FN4·AUROC0.4874로 개선이 없었다. 운영 모델 교체 없이 연구 기록을 보존했다. 상세: docs/history/OBSERVATION_GEOMETRY_VALIDATION_20261011.md.


### 0.4.42 DINOv2 비교·합의안 복귀
선택 옵션 --backbone dinov2_vits14를 추가했다. 기본 MobileNet과 기존 체크포인트 호환은 유지한다. 동일 검증에서 AUROC0.4874→0.5294, FP7/FN4 동일·BCE 악화로 채택하지 않았다. OBSERVATION_CONSENSUS 기반 입력 근거 진단으로 복귀하며 완료 라벨 재요청은 없다. 상세·롤백: docs/history/DINOV2_VALIDATION_20261011.md, artifacts/observation-dinov2-20261011/recovery.json.


### 0.4.43 OBSERVATION_CONSENSUS 입력 근거 진단
visibility-input-audit 명령은 train만 읽어 native/224px 픽셀·3x3 구역 신호를 기록한다. 반사8면 중7면의 평균 밝기가 같은 면의 관찰 제한 없음 범위와 겹쳐 단일 밝기 필터를 채택하지 않았다. 분류·라벨 변경은 없으며 상세는 docs/history/OBSERVATION_INPUT_AUDIT_20261011.md, 결과는 artifacts/observation-input-audit-0443-20261011/index.html.

### 0.4.44 국소 색·질감 입력 비교
`visibility-experiment --centroid --local-signals`는 동일 224px 입력의 3×3 구역별 밝기·질감·채도·중성 밝기 36값을 추가한다. 기본값은 꺼져 있고 MobileNet/context/centroid 조합만 허용한다. 동일 검증24면에서 FP7/FN4·순위 지표 그대로여서 후보를 채택하지 않았다. BCE 소폭 하락은 주로 차원 분모 변경에 따른 점수 완화였다. 상세·롤백: docs/history/LOCAL_SIGNALS_VALIDATION_20261011.md. 작업 지침 AGENTS.md에는 휴먼인루프·간결한 에튜 포인트를 영속 기록했다.

### 0.4.45 train-only 표준화
`visibility-experiment --centroid --local-signals --standardize`는 train 실물 균등 평균/표준편차를 저장해 val·추론에 고정 적용한다. 기본 꺼짐. 동일 val에서 AUROC는 .5630으로 올랐지만 FP7/FN4 그대로·BCE .7263으로 채택 보류. docs/history/TRAIN_SCALING_VALIDATION_20261011.md 참고.

### 0.4.46 앞뒤 대표 기준 분리
`visibility-experiment --centroid --side-aware`는 앞/뒤 각각의 train 제한·비제한 centroid를 사용한다. 추론은 `visibility-predict MODEL IMAGE --box L T R B --side back`처럼 면을 명시해야 한다. 기본 꺼짐. 동일 val FP/FN7/4→2/3·AUROC .4874→.8739로 연구 기준 통과, 운영 적용은 미승인이다. docs/history/SIDE_CENTROIDS_VALIDATION_20261011.md 참고.

### 0.4.47 실물 전체 제외 검산
`visibility-crossfit MANIFEST OUTPUT --device mps`는 train만 읽고 같은 실물의 앞뒤 전체를 제외해 공통/면별 centroid를 대조한다. 실제25fold에서 FP/FN11/5→6/4·AUROC .5022→.7835. BCE는 .6741→.6896으로 악화하므로 확률 교정 개선은 아니다. 독립 최종평가가 아니며 docs/history/GROUP_CROSSFIT_VALIDATION_20261011.md 참고.

### 0.4.48 독립 평가 준비
`visibility-heldout CHECKPOINT MANIFEST OUTPUT --expected-model-sha256 SHA --device mps`는 test만 읽고 고정 SHA와 일치하는 모델을 평가한다. 개발에 사용한 id/실물/동일 디코딩 픽셀, test 내부의 서로 다른 그룹에 중복된 픽셀, 미확인/단일 클래스 입력을 거절한다. 모델 fit/선택 없이 예측하며 운영 승인은 하지 않는다. 지금은 독립 test/새 사진이 없으므로 실제 독립 성능 평가는 미실행이다. docs/history/HELDOUT_EVALUATION_PLAN_20261011.md·docs/history/HELDOUT_EVALUATION_VALIDATION_20261011.md 참고.

### 0.4.49 매물 분석과 관찰 제한 신호의 오프라인 연결

`listing-infer MANIFEST REGION_CHECKPOINT OUTPUT --observation-checkpoint OBSERVATION_CHECKPOINT --device mps`

선택 옵션을 주면 같은 val 매물의 앞뒤 사진을 고정 관찰 제한 모델에 한 번씩 전달하고 `observation_evidence`에 별도로 기록한다. 면 정보와 카드 영역은 사람 입력을 사용한다. 사진/영역 누락은 점수 없이 사유를 남긴다. 점수가 낮아도 사람의 반사 제한을 지우지 않으며, 높아도 결함·구매 제외·추가 사진 필요를 자동 확정하지 않는다. 기존 구역 추론·readiness 정책은 그대로다. 두 체크포인트·manifest·사진의 변경을 검사하고 학습/외부 호출 없이 실행한다. 옵션을 생략하면 기존 경로를 유지한다. 실제 운영 승인이나 독립 정확도 평가를 대신하지 않는다.

### 0.4.50 고정 타일 배치 추론 실험

`listing-infer ... --batch-views`는 같은 구역 전체+고정 2×2 타일을 한 번의 백본 호출로 처리한다. 기존 타일 좌표·해상도·풀링·체크포인트는 유지하며 inference mode와 eval 백본에서만 허용한다. 기본값은 기존 순차 방식이다. `--observation-checkpoint`와 함께 사용할 수 있고 학습·판정 기준·운영 fallback을 변경하지 않는다. GPU 부동소수점 연산 때문에 미세한 점수 차이가 가능하므로 동일 입력의 구역 판정까지 비교해야 한다. 메모리·운영 동시 부하는 별도 검증 대상이다.

### 0.4.51 선택 MPS 메모리 진단

`listing-infer ... --profile-memory --device mps`를 사용하면 구역 백본의 leaf module 실행 경계에서 텐서 할당량과 Metal 드라이버 할당량을 샘플링한다. `--batch-views`와 함께 사용할 수 있다. 결과 `memory_profile`의 `max_sampled_*_bytes`는 샘플 최대치이며 실제 peak나 시스템 RAM 사용량이 아니다. driver에는 캐시 및 MPS 프레임워크 할당도 포함된다. 관찰 제한 모델 추론은 측정 범위에 포함하지 않는다. 진단 hook은 성공/실패 시 모두 제거한다. CPU에는 임의의 MPS 수치를 만들지 않고 요청을 거부한다.

메모리 진단은 기본 비활성이고 측정 오버헤드가 있다. 오류 시 부분 보고서를 성공으로 저장하지 않으며 CLI는 `requires_gemini=true`와 비정상 종료를 전달한다. 순차 경로로 다시 실행하려면 `--batch-views`를 생략한다. 자동 OOM 재시도나 실제 Gemini 호출을 수행하지 않는다.

### 0.4.52 최신 모델의 독립 구역 API

`RegionAnalyzer(checkpoint, device).analyze(image, card_box, area, unknown_labels=(), batch_views=False)`가 구형 region 모델과 point-grid/views/tiles/tiles-max 모델을 지원한다. 최신 모델은 probe/listing과 같은 검증 로더·고정 전처리를 사용하고 체크포인트의224/448 해상도를 지킨다. `architecture`, `image_size`, `input_policy`, `batched_views`를 결과에 기록한다. 사람이 지정한 관찰 제한은 `unknown_labels`로 전달하며 해당 점수는 null로 유지한다. 지원하지 않는 결함·적용 범위 밖 항목도 null이다.

```python
from card_condition.region_model import RegionAnalyzer

analyzer = RegionAnalyzer('path/to/model.pt', device='mps')
result = analyzer.analyze('path/to/photo.png', [0.05, 0.03, 0.95, 0.97],
                          'middle_right', unknown_labels=['surface_defect'],
                          batch_views=True)
```

CLI: `card-condition region-predict CHECKPOINT IMAGE --card-box LEFT TOP RIGHT BOTTOM --area middle_right --batch-views --device mps`. `--unknown surface_defect` 등으로 관찰 제한을 전달할 수 있다. 카드 영역은0~1 정규화 좌표이며 예제 좌표를 다른 사진에 그대로 사용하지 않는다. 모델 인스턴스를 재사용하면 구역마다 모델을 다시 로딩할 필요가 없다. 이 API는 연구용 추론 계약이며 매물 전체 등급·운영 승인·Gemini 생략을 제공하지 않는다.

### 0.4.53 라벨 없이 매물 사진 묶음 추론

`ListingAnalyzer`는 앞뒤 사진을 한 요청으로 분석한다. 학습 manifest·split·정답 라벨 없이 호출하며 모델 인스턴스를 재사용한다. 현재 선택 모델은 엣지만 지원한다. 지원하지 않는 모서리/표면, 센터링, 같은 실물 여부는 확정하지 않는다.

```python
from card_condition.listing_model import ListingAnalyzer
analyzer = ListingAnalyzer('/absolute/model.pt', device='mps')
result = analyzer.analyze({
    'id': 'listing-123',
    'front': {'image': '/absolute/front.jpg', 'box': [0.05, 0.03, 0.95, 0.97],
              'visibility_issues': []},
    'back': {'image': '/absolute/back.jpg', 'box': [0.04, 0.02, 0.96, 0.98],
             'visibility_issues': ['glare'], 'glare_areas': ['lower_right']}
}, batch_views=True)
```

이 좌표는 설명용이다. 각 사진의 EXIF 방향 적용 후 카드 바깥 영역을0~1 좌표로 지정한다. `image`는 절대 경로다. CLI는 같은 요청을 JSON 파일로 저장한 뒤 `card-condition listing-predict CHECKPOINT REQUEST.json --batch-views --device mps`로 실행하고 JSON을 stdout에 출력한다. 오류는 비정상 종료와 `requires_gemini=true`를 반환한다.

사진 누락은 면 생략/null, 카드 영역 미확인은 box 생략/null로 전달한다. `visibility_issues` 생략은 관찰 검토 미완료이므로 해당 면 전체 점수가 unknown이다. 명시적 `[]`는 호출자가 관찰 제한이 없다고 확인했다는 입력 주장으로만 취급하며 AI의 정상 인증이 아니다. 반사는 지정 구역만 보류하고, 반사 위치를 생략하면 면 전체를 보류한다. 다른 제한(blur/shadow 등)은 현재 면 전체를 보류한다. 결함 정답 라벨을 요청에 넣지 않는다. 원본 파일 SHA를 기록하고 실행 중 사진 변경을 거부한다.

이 경로는 연구용 독립 추론이다. 같은 실물 연결·등급·구매 제외·실제 Gemini 호출/생략은 수행하지 않는다. `.listing_readiness`의 normal/defect는 미교정 구역 점수의 탐색 기준이며 운영 판단으로 사용하지 않는다.

### 0.4.54 독립 매물 API의 선택 관찰 제한 신호

```python
analyzer = ListingAnalyzer('/absolute/region-model.pt', device='mps',
                           observation_checkpoint='/absolute/observation-model.pt')
result = analyzer.analyze(request, batch_views=True)
```

CLI에서도 `listing-predict ... --observation-checkpoint CHECKPOINT`를 사용할 수 있다. 두 모델은 인스턴스 생성 시 한 번만 로딩하며 여러 매물 요청에 재사용한다. 선택 옵션이 없으면 기존 구역 분석 결과를 유지한다.

고정 릴리스는 `card-condition listing-predict REQUEST.json --release RELEASE.json`으로 실행한다. manifest는 `release_id`, `package_version`, `input_contract`("listing-request-v1"), `checkpoints`(region 필수, observation·recall 선택, 각각 manifest 기준 상대 `file`과 `sha256`)만 가진다. 설치 패키지 버전·입력 계약·파일 SHA·실제 로드한 SHA가 하나라도 다르면 추론 전에 오류로 끝나며 결과를 출력하지 않는다. 결과의 `release`에 실행한 릴리스 ID·버전·SHA가 남는다. 직접 `CHECKPOINT` 인자와 함께 쓸 수 없고, 직접 실행 결과는 기존과 같다. 이전 버전 복구는 이전 wheel을 다시 설치하고 그 릴리스의 manifest로 실행한다(`tools/release/verify_install_rollback.py`가 합성 fixture로 A→B→A를 검증). 릴리스 고정은 품질 통과나 운영 채택을 뜻하지 않는다. manifest의 `checkpoints`에 `observation`·`recall`을 두면 같은 방식으로 고정·식별되며, `listing-review`는 그 결과의 관찰 신호(면별 점수, 사람 관찰 제한)와 recall 후보(해당 칸 표시·점수)를 보조 근거로 함께 보여 주고 검토 기록에 두 모델 SHA와 후보 칸을 남긴다. 이 신호는 보정되지 않았으며 제한을 해제하거나 결함을 확정하지 않는다.

결과 검토는 `card-condition listing-review REPORT.json REQUEST.json --output PAGE.html`로 정적 페이지를 만든다. 분석한 사진과 SHA가 다르거나 다른 매물이면 만들지 않는다. 페이지는 원본 사진·사람 카드 영역의 3×3 근거 구역·릴리스와 model SHA·칸별 판정/점수/보류 이유·전체 판정 불가 사유를 보여 주고, 칸마다 confirmed/corrected_defect/corrected_normal/undecidable을 골라 JSON으로 내보낸다. `card-condition listing-review-record REPORT.json DECISIONS.json --output RECORD.json`은 같은 결과 SHA와 모든 칸을 확인해 별도 검토 기록을 쓰며, 미검토 칸이 있으면 완료가 아니다. 이 기록은 정답 라벨·학습 자료가 아니고 모델 판정을 바꾸지 않는다.

승인된 보조·shadow 사용을 측정하려면 `listing-predict ... --usage-log USAGE.jsonl`을 붙인다. 요청마다 한 줄(결과 SHA, 릴리스, 시작·총·분석 시간, 보류·결함 칸 수와 보류 이유, 실패 유형)을 O_APPEND로 쓰며 사진 경로와 오류 문장은 쓰지 않는다. 기록을 쓸 수 없으면 그 요청은 실패로 끝나 결과를 출력하지 않는다. 실패한 요청도 시도한 릴리스 manifest의 `release_id`로 귀속한다. CLI는 요청마다 새 프로세스라 항상 cold이고, 같은 `UsageRecorder`로 `start()`/`finish()`를 반복하는 API 소비자만 warm 기록을 만든다. `card-condition pilot-summary USAGE.jsonl [--reviews RECORD.json ...]`은 릴리스별로 기간·요청 수·고유 요청 id·warm 앞뒤 한 쌍 p95와 동시성·기록된 실패율·사람 정정 수를 계산해 F2 문턱과 대조한다. 계산하지 못하는 조건(정상 카드 거짓 경고율, Gemini 호출·검토 시간 변화, 승인·실물 신원)은 `not_computed`로 남기며 `pilot_certified`는 항상 false다.

관찰 모델은 앞/뒷면과 카드 영역을 받아 `observation_evidence`에 면별 점수만 추가한다. 누락 사진/영역은 점수 없이 사유를 기록한다. 미검토 면도 별도 관찰 신호는 계산할 수 있지만 사람 검토 값은 null이고 구역 판정은 미확인으로 유지한다. 낮은 점수로 반사 마스크를 해제하거나 높은 점수로 카드 불량·구매 제외를 확정하지 않는다. 사진 변경 검사는 두 모델의 실행이 모두 끝난 뒤 수행한다. 독립 최종평가와 실제 Gemini 호출 절감은 아직 없다.

### 0.4.55 모델 파일 오류 계약

손상/빈 체크포인트 또는 안전 로더가 거절하는 파일은 CLI에서 traceback 대신 `{"error":"Invalid or incomplete checkpoint; use Gemini fallback","requires_gemini":true}`와 종료 코드1을 반환한다. 정상 체크포인트 동작은 그대로이며 `weights_only=True`를 해제하거나 안전하지 않은 재로딩을 하지 않는다. 이 응답은 호출자에게 보류를 요청할 뿐 실제 Gemini API 호출을 수행하지 않는다.

### 0.4.56 확률 변환 전 수치 검사

독립 전체/단일 면/구역 API, 매물 추론, point 진단과 벤치마크는 `checked_sigmoid`를 공유한다. 변환 전 logits의 NaN/무한대를 거절한다. `sigmoid(+inf)=1`, `sigmoid(-inf)=0`이므로 변환 이후 확률만 검사하면 수치 실패가 그럴듯한 판단으로 보일 수 있기 때문이다. 정상 유한값은 원래 sigmoid와 동일하게 계산한다. 극단적이지만 유한한 값을 임의로 보정하거나 점수/임계값을 바꾸지 않는다. 오류는 기존 CLI JSON fallback/exit1로 전달하며 학습 loss/선택 기준은 변경하지 않는다.

### 0.4.57–0.4.59 관찰 제한 연구 비교

`visibility-crossfit MANIFEST NEW_OUTPUT --compare-ridge --device mps`는 기존 train 실물 제외 fold에서만 고정 λ=1 Ridge와 면별 centroid를 비교한다. 클래스/실물 균등 가중 MSE, -1/+1 목표, 비정규화 bias, CPU float64 solve를 사용한다. 임계값0.5·특징·전처리는 유지하며 교정된 확률을 제공하지 않는다. 이번 실제 비교는 오탐6→5지만 누락4→7로 채택하지 않았다.

`--compare-context`는 분류기를 유지하고 카드 crop576특징에 원본 전체 사진576특징을 붙이는 별도 입력 가설이다. 각각 같은224px 전처리와 고정 백본을 사용한다. 배경을 정답 대신 학습할 위험이 있으므로 결과가 좋아져도 독립 실물 검증을 대체하지 않는다. 두 옵션은 선택 연구 기능이며 체크포인트를 저장하거나 운영 모델을 교체하지 않는다.

교차검증 보고서의 `reason_support`는 사진을 시험할 때 같은 면·같은 제한 종류의 다른 실물이 학습에 남는지 기록한다. 지원 없음/있음 구분은 오류 해석용이며, 자료가 부족한 오류도 전체 지표에서 제외하지 않는다. 제한 여러 개가 있는 사진은 사유별 집계에 중복되므로 사유별 누락 수를 더해 전체 누락 수로 해석하지 않는다. 검증/test 사진·라벨은 읽지 않는다.

### 0.4.60 실물 단위 재표집 진단

`visibility-crossfit`의 `paired_group_sensitivity`는 같은 실물의 앞뒤 사진을 묶어 기준 후보와 비교 후보를 같은 추출로2000회 재표집한다. seed42 고정·임계값0.5의 FPR/FNR 차이를 사용하고 기존 채택 조건은 유지한다. 사진 한 장씩 독립적으로 추출하지 않는다.

`fpr_delta.observed`와 `fnr_delta.observed`는 후보−면별centroid이며 음수면 해당 오류가 감소한 것이다. `spread.empirical_p025/p975`는 고정 예측의 경험적 변동 범위로, 학습 알고리즘의 정식 신뢰구간이나 미사용 실물 정확도가 아니다. 한 정답 클래스만 뽑힌 추출은 비율을 정의할 수 없어0으로 처리하지 않고 제외 횟수를 기록한다. 재학습·임계값 선택·운영 채택은 수행하지 않는다.

### 0.4.61 BCE 분류기 고정 비교

`visibility-crossfit ... --compare-logistic`은 같은 고정576특징에서 면별 Logistic Regression을 비교한다. 클래스/실물 균등 평균BCE+λ1||w||², bias는 비정규화한다. CPU float64 LBFGS 최대100회, 학습 특징만 가중 중심화해 계산 조건을 개선한 뒤 원래 좌표의 bias로 되돌린다. 목적 함수가 같은 좌표 변환이며 특징 선택이나 검증 자료 표준화가 아니다. 최대 기울기1e-6 이하로 수렴하지 않으면 비교 보고를 저장하지 않는다. BCE 학습만으로 확률 교정이나 독립 정확도를 보장하지 않는다.

### 0.4.62 반사 대상 분리 비교

`--compare-glare-only`는 명시적 glare를 양성, 관찰 제한 없음으로 사람이 확인한 사진을 음성으로 같은 면별 centroid를 비교한다. 다른 제한만 있는 사진은 미확인으로 제외하며 정상으로 바꾸지 않는다. `glare_comparison`에 동일 대상 기준/후보, 미평가 사진, 거부fold, 실물 단위 변동 진단을 기록한다. 두 클래스가 남지 않으면 insufficient_scored_support와 null 진단으로 보고한다.

반사 후보는40면/23실물에서 FP/FN6/2→1/4, BCE 후보는46면/25실물에서6/4→5/7로 모두 미채택이다. 연구용 옵션이며 체크포인트 저장이나 운영 변경은 수행하지 않는다.

### 0.4.63 고정 view 디코딩 재사용

같은 구역의 전체/타일 입력은 원본을 한 번 읽어 생성한다. 순차·배치·frozen prefix 모두 같은 crop/pad/정규화 좌표를 사용하며 요청 간 캐시는 없다. 새 옵션이나 모델 교체 없이 기존 명령에 적용된다. 동일 MPS15매물160구역 비교에서 점수/보류 결과 일치·중앙값13.87→5.79초. 정확도/운영 처리량 개선 주장은 아니며 실제 Gemini 절감0건 유지. docs/history/VIEW_DECODE_VALIDATION_20261011.md 참고.

### 0.4.64 성능 변화 보고

기존 visibility-compare·point-compare·region 비교는 같은 사진/구역/정답 확인 후 rates_at_05와 %p 변화를 제공한다. 누락률은 FN/(TP+FN), 오탐률은 FP/(TN+FP), accuracy는 알려진 라벨의 정답 비율이다. 분모0이면 null, 미확인을 정상으로 계산하지 않는다. point 비교의 첫 report가 기준선이며 다른 모델의 rate_change_from_reference_at_05와 함께 읽는다. 0.1→0.2는 +10%p 악화다. errors_jointly_improved는 누락·오탐 모두 악화되지 않고 적어도 하나 감소했다는 뜻이며 운영 채택 조건이 아니다. 동일 검증 자료를 재사용하므로 새 카드 일반화나 전체 매물 등급 정확도가 아니다. docs/history/QUALITY_RATES_VALIDATION_20261011.md 참고.

### 0.4.65 뒷면 반사 train-only 중첩 판정 경계 실험

card_condition.observation_nested.nested_back_glare는 기존 고정 특징과 train 행을 받아 바깥 실물 제외 후 안쪽 실물 제외 예측만으로 zero-FP 경계를 정한다. 앞면/다른 제한은 제외한다. 실행 계획/재현은 artifacts/back-glare-nested-20261011/plan.json·run.py. 뒷면18실물 비교에서 누락률50→100%, 오탐률8.33%유지로 실패해 채택하지 않았다. 저장 모델/기본0.5/운영 fallback은 유지한다. docs/history/BACK_GLARE_NESTED_VALIDATION_20261011.md 참고.


### 0.4.66 최종평가 입력 보존 검사

면/구역 최종평가는 서로 다른 실물 group에 동일 디코딩 픽셀을 배정하면 거부한다. manifest·checkpoint·개발 이력·사진의 파일 SHA를 실행 전후 비교하고, 실행 도중 변경되면 성공 보고서를 저장하지 않는다. 라벨/분할/모델은 수정하지 않는다. docs/history/EVALUATION_GUARDS_VALIDATION_20261011.md 참고.

### 0.4.67 클릭 라벨·타일 모델 최종평가 연결

기존 `region-evaluate <test-only manifest> <checkpoint> <새 report.json> --history <개발 manifest> --device cpu`가 checkpoint 구조에 맞춰 입력을 선택한다. point/grid/views/tiles 모델은 학습과 같은 `point_rows(grid=True)`를 사용해 사람이 표시한 결함 점과 명시적 정상 구역을 합치며, 같은 구역의 여러 점은 한 번만 센다. 전역 gradable 미확인도 국소 정답은 평가할 수 있다. 종전 region 모델은 기존 region_rows 경로를 유지한다.

point_final 보고서의 metrics/rates_at_05는 지원되고 정답이 알려진 구역만 계산한다. 미확인은 정상으로 바꾸지 않고, 점수화 가능한 지원 라벨이 하나도 없으면 보고서를 저장하지 않는다. 모든 이전 개발 이력을 제공해야 하고 기존 train/val을 test로 옮겨서는 안 된다. 실제 미사용 test 사진은 현재0장이므로 연결 검증은 임시 fixture로 수행했으며 독립 정확도 개선 주장이 아니다. docs/history/POINT_FINAL_VALIDATION_20261011.md 참고.


### 0.4.68 최종평가의 실물별 오류

region_final/point_final은 by_group·by_group_side 혼동행렬과 group_error_rates_at_05를 함께 저장한다. 전체 rates_at_05는 알려진 구역 수 기준, group_error_rates_at_05는 해당 정답 클래스가 있는 실물별 오류율을 먼저 계산한 뒤 실물에 동일 가중치를 준 평균이다. 정상/결함이 없는 실물을 해당 클래스의 오류0으로 채우지 않는다. 두 지표의 분모가 다르므로 서로를 정확도 개선으로 비교하지 않는다. FINAL_GROUP_RATES_VALIDATION_20261011.md 참고.


### 0.4.69 평가 근거가 없는 성공 보고 차단

side-evaluate도 채점 가능한 지원 정답이0개이면 보고서를 저장하지 않는다. 정답이 일부만 알려졌다면 그 항목만 집계하며, 한 클래스가 없을 때 해당 오류율은null이다. 면/구역 평가의 개발 이력은 빈 목록·문자열·공백 ID·잘못된 SHA256을 거부한다. 최종시험 누수 검사에 필요한 실물/카드ID/이미지 해시 목록이 실제 목록이어야 하며, 목록 형식이 맞다는 사실만으로 개발 이력의 완전성이 보장되지는 않는다. docs/history/EVALUATION_PROVENANCE_VALIDATION_20261011.md 참고.


### 0.4.70 관찰 검토 미입력은 미확인

listing-infer와 공유 listing_readiness도 독립 ListingAnalyzer와 같은 관찰 계약을 적용한다. visibility_issues 필드를 생략하면 observation_not_reviewed로 보류하며, 명시적인 []는 호출자가 제한 없음을 검토했다는 뜻이다. 결함 라벨이 있거나 모델 점수가 높고 낮다는 이유로 누락 검토를 완료 처리하지 않는다. 검토가 빠진 면은 구역 추론을 생략하며 카드 상태 불량으로 단정하지 않는다. 관찰 모델의 별도 신호와 Gemini 검토는 유지한다.

실제 검토 완료15매물160구역27면은 전후 결과가 일치했다. 같은 입력에서 검토 필드 하나만 생략한 진단에서는 독립 API/검증 경로가 일치하고 앞면21항목 미확인·구역 추론8개 생략을 확인했다. 이는 정확도 개선이나 실제 호출 절감이 아니다. docs/history/OBSERVATION_REVIEW_CONTRACT_20261011.md 참고.

## 0.4.71 검증 입력 무결성

point-probe도 실행 중 사진 변경을 차단한다. 체크포인트 개발 이력의 빈값/잘못된 hash와 지원 정답0건은 성공 진단으로 저장하지 않는다. 정상 입력 추론은 동일하며 모델 정확도 개선을 뜻하지 않는다. docs/history/POINT_PROBE_INTEGRITY_20261011.md 참고.

## 0.4.72 평가 실물/이력 계약

point-probe는 복제 픽셀을 다른 실물로 집계하지 않는다. 관찰 제한 독립 평가도 공통 개발 이력 검사를 사용한다. 정상 입력 결과와 기존 모델은 유지한다. docs/history/EVALUATION_GROUP_CONTRACT_20261011.md 참고.

## 0.4.73 속도 측정 입력 고정

단일 면/타일 벤치마크도 실행 중 사진·manifest·모델 변경을 차단한다. 타이머와 모델 추론은 유지하며 정확도·속도 개선으로 간주하지 않는다. docs/history/BENCHMARK_INPUTS_VALIDATION_20261011.md 참고.

## 0.4.74 — 지점별 복수 종류 수정과 신규 독립 평가

사진 아래 지점 체크박스로 종류를 수정한다. 점과 면 정답의 불일치는 경고하며 자동 정답 변경은 없다. 새 Persian 엣지1구역 검출(TP1/FN0), 정상 정답0개라 오탐률 미측정. 관찰 평가 양성0으로 보류. 기반67%·일반화 개선 미확인·Gemini절감0. [검증·리스크·롤백](docs/history/POINT_KIND_REVIEW_VALIDATION_20261011.md).

## 0.4.75 — 전체/면별 정답 불일치 표시

전체 정상0·면별 결함1이면 경고하고 정답은 자동 변경하지 않는다. 신규 Gastly 엣지1곳 누락(0.4627); 새2실물 양성2구역 합계 TP1/FN1·정상0으로 오탐률 미측정. 모델/기준 고정·개발 기반67%·Gemini절감0. [근거·리스크·롤백](docs/history/INDEPENDENT_GASTLY_VALIDATION_20261011.md).

## 0.4.76 — 사람 표시 출처·3×3 구역 안내선

빨간 번호는 사람 입력임을 표시하고 사진별 구역 안내선을 토글할 수 있다. 안내선은 라벨/사진을 변경하지 않는다. 전체150테스트·실제 브라우저·wheel52파일 확인. 정확도 변화 없음·기반67%·Gemini절감0. [검증·리스크·롤백](docs/history/REVIEW_GUIDE_VALIDATION_20261011.md).

## 0.4.77 — 영역 확인·저장 오류 수정

일시 검증 메시지만 제거하여 영구 경고 DOM을 보존한다. image 없는 geometry 링크도 선택 사진으로 시작하며 명시한 다른 사진은 거부한다. docs/history/REVIEW_SAVE_FIX_20261011.md 참고.

## 0.4.78 — 신규 정상 뒷면·앞면 반사 경계 검증

신규 정상 엣지8구역 오탐0. 앞면 nested 실험은 학습 오탐 감소가 val 반사누락 증가로 이어져 미채택. 기존 모델/기준 유지. docs/history/CHIEUT_EXPERIMENT_20261011.md 참고.

## 0.4.79 — 독립 관찰 시험·실물별 오류

신규 반사 앞면 포함 독립3실물4면 TP0/TN3/FP0/FN1. 반사1면을 놓쳐 미채택이다. evaluate_heldout는 기존 group_error_rates를 재사용해 by_group·group_error_rates_at_05를 추가한다. 모델/기준 불변. 실제 API의 중앙 반사 마스킹·미확인 보존 확인. [근거·롤백](docs/history/CHIEUT_HELDOUT_VALIDATION_20261011.md).

## 0.4.80 — 반사 보강 실험·앞면 연구 후보 고정

추가 학습 사진 후 기존 검증11면의 centroid 반사누락1→0·오탐1유지(+9.09%p 정확도). 반면 동일 기존23학습 실물 제외에서는 누락2→3·오탐2→5로 악화해 일반화 개선을 확정하지 않는다. 최근접 다중 prototype 연구 함수는 학습상 개선됐지만 검증에서 악화해 미채택. 선택적으로 supported_sides가 명시된 관찰 체크포인트는 지원 면만 허용하고 구형 메타데이터의 기존 동작은 유지한다. 고정 연구 후보는 앞면 반사 전용·운영 미채택·기존 시험 재사용 차단. [변경·검증·롤백](docs/history/CHIEUT_GLARE_TRAIN_VALIDATION_20261011.md).

0.4.81: 시험용 카드도 명시적인 geometry 링크로 해당 면만 확인할 수 있습니다. 기본 학습 큐와 분할·정답은 그대로 유지합니다. 신규 독립 시험 준비는 docs/history/CHIEUT_INDEPENDENT_PREPARATION_20261012.md 참고.

### 구겨짐 라벨 (0.4.86)

구겨짐·접힌 자국·눌린 자국은 `surface_defect`의 관찰 가능한 결함으로 포함한다. 클릭 입력에서 표면 결함을 선택하고 확인한 위치를 여러 번 표시할 수 있다. 모서리/엣지 손상도 직접 확인한 경우에만 해당 종류를 함께 선택한다. 빛 반사·무늬만으로 구겨짐을 확정하지 않는다. 가려진 부분은 미확인이다. 기존 라벨/체크포인트는 변경하지 않으며, 기존 표면 정상 라벨을 구겨짐까지 새로 확인한 정답으로 확대 해석하지 않는다. 구겨짐 전용 출력이나 검출 성능은 아직 없다.

### 클릭 중심 라벨 (0.4.87)

영역 확인과 센터링은 기본 화면에, 반복되는 전체/면별/구역별 입력은 추가 관리에 둔다. 손상 선택은 모서리·엣지·기스·구겨짐·오염, 촬영 제한은 빛 반사·흐림·가림·잘림·저해상도·원근·어두움이다. 표면 세부 종류는 defect_points의 선택적 types(scratch/crease/stain)로 보존하고 학습 정답은 surface_defect로 유지한다. 기존 종류 미지정 표면 지점은 추정해 변환하지 않는다.
촬영 제한은 visibility_points(issue/x/y)로 좌표를 보존하며 기존 visibility_issues에도 반영한다. 빛 반사는 3×3 glare_areas, 다른 제한은 현재 면 전체의 보수적 판단 보류에 사용한다. 전체 제한 버튼도 제공한다. 제한점 삭제는 면의 제한 사실을 자동 해제하지 않으며 추가 관리에서 확인 후 해제한다. 정상 모드의 표면 선택은 모든 표면 종류를 충분히 확인했다는 뜻이다. 새로운 검출 모델이나 정확도 개선은 포함하지 않는다.

### 원근 사진의 명시적 정상 구역 (0.4.88)

사람이 카드 영역과 특정 구역의 정상 엣지를 확인했다면, 면에 `perspective` 표시가 있어도 그 **명시적 구역 0**을 패치 학습에 사용할 수 있다. 원근 표시 자체와 독립 매물 API의 판단 보류는 유지한다. 흐림·가림·잘림·저해상도·어두움이나 해당 구역의 반사가 함께 있으면 정상 학습에서 제외한다. ㅋ-5의 새 엣지 결함 2구역과 ㅋ-8의 정상 2구역을 분리해 비교한 결과·채택 판단은 [검증 기록](docs/history/KIEUK_NORMAL_EDGE_VALIDATION_20261013.md)을 참고한다.


### eBay 사진 수집 기본 동작 (2026-10-17)

`tools/collect_ebay_dataset.py`는 기본적으로 eBay 사진 수집·중복 제외·HTML 생성만 실행하며 Gemini를 초기화하거나 호출하지 않습니다. `--quota-db`는 기본 수집에 필요하지 않습니다. 외부 비전 사진 선별은 명시적인 `--screen-limit N --quota-db PATH` 옵션을 준 경우에만 실행합니다. `--screen-limit 0`은 기존 캐시/사람 확인을 API 추가 호출 없이 재개하는 경로입니다. [검증·실행·롤백](docs/history/EBAY_COLLECTION_ONLY_VALIDATION_20261017.md).


이번 이후 이 세션의 eBay 사진 저장 위치는 `./data/ebay-learn`입니다. 수집 예제:

```sh
.venv/bin/python tools/collect_ebay_dataset.py --consumer-root "$POKECOLLECTOR_ROOT" --learn data/ebay-learn --output artifacts/새수집폴더 --limit 4
```

기존 학습 자료를 일괄 이동하지 않으며, 이번 후딘부터 새 내부 경로를 사용합니다. 과거 외부 learn 경로로 작성된 명령은 당시 이력입니다.


사진 저장소를 이전했다면 수집 명령에 `--reference-learn /이전/learn`을 추가하세요. 새사진은 `--learn`에만 저장하고 이전폴더는 매물ID·디코딩픽셀 중복검사로만 읽습니다. 기본Gemini호출0은 유지합니다. 최근 연구 입력 설명의 정정은 [입력 정책 정정](docs/history/INPUT_POLICY_CORRECTION_20261017.md)을 참고하세요.


## 2026-10-17 — 선택형 엣지 추가 검토 연구 API

MobileNet + DINO 지역 특징을 결합한 별도 연구 API입니다. 기본 분석 경로에 연결되지 않습니다. 기존 모델의 의심 판정을 보존하고 새로운 의심만 `additional_review`로 표시합니다. 이것은 결함 확정이 아닙니다.

```python
from card_condition.edge_hybrid_review import HybridEdgeReview
model = HybridEdgeReview(
    "artifacts/edge-dino-fusion-20261017/back-hybrid-review.pt",
    "artifacts/torch-cache/hub/facebookresearch_dinov2_7764ea0f912e53c92e82eb78a2a1631e92725fc8",
    device="mps",
)
# box는 실제로 확인한 카드 영역, area는 3x3 테두리 구역 이름입니다.
result = model.analyze(photo_path, card_box, "middle_right", side="back")
print(result["additional_review"], result["human_review_required"])
```

가중치와 고정된 로컬 DINO 소스 캐시가 필요하며 예측 중 다운로드나 외부 AI 호출은 없습니다. 앞면은 front checkpoint를 사용하세요. 실제 score 재현성과 개발 평가 성능을 구분한 [검증·리스크·롤백](docs/history/EDGE_HYBRID_REVIEW_VALIDATION_20261017.md)을 참고하세요.

## 데이터 부족표 감사

`card-condition data-coverage <manifest> <새 JSON 경로>`는 종류·앞뒤·train/val별 명시적 정답과 실물 수를 집계합니다. 학습·추론·final-test 검사는 실행하지 않습니다. [현재 부족표·검증·휴먼인루프 일시 중지](artifacts/data-coverage-20261024/REPORT.md).
