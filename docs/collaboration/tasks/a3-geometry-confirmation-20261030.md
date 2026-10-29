# A3 카드 영역 확인 반영과 전체 표면 검증

- owner: Codex
- status: integrated
- base_sha: dcd39d16fe9b32aeb9d5c30eb6979dfd33171946
- branch: codex/a3-geometry-confirmation-20261030
- approval: 2026-10-30 현재채팅의7면파란카드영역확인질문에사용자“정상”응답. 기존정상/손상라벨변경승인이아니다. 승인된개발검증계속.
- goal: 원본156행에서지정7면의box_reviewed만true로한새버전동결·감사·평가입력준비후기존두후보를전체알려진표면분모에비교.

allowed_files: tools/experiments/a3-geometry-confirmation-20261030/worker.py, plan.json; tests/test_a3_geometry_confirmation.py; docs/collaboration/tasks/a3-geometry-confirmation-20261030.md; docs/collaboration/reports/a3-geometry-confirmation-20261030.md 및.html. ignored artifacts/a3-geometry-confirmation-20261030/ 및development-manifest-20261030a/와새공통실험. 원래frozen자료·모델·worker·정답·실물분할·진척기준·소비코드·DATA_INVENTORY 수정금지.

7면: d앞뒤/i뒤/w앞/ㄱ앞뒤/ebay-2731907577fb29뒤. box좌표/point/region_labels/visibility/labels/제외상태/기타모든필드불변을dict대조. 응답원문·질문범위·사진SHA·이전manifestSHA보존. 새수량/분모는모델점수보기전실제coverage로고정한다.

기존719crop의features와token maps는원본SHA·row identity로재사용해재추론하지않는다. 새지원crop만동일한고정backbone/head/readout/.5로추론한다. 같은새분모에서이전/후보를비교하고원래147/51/11cohort와새로동결한4회귀묶음을동일후보로재생한다. 새학습·외부AI0. 원래전체품질기준/새오류금지/点누락보호유지. 모델과대조의계수만차이,후보채택조건완화0.

구조: 신규worker최대7함수,새cache매핑/재사용검증과실행단계분리,함수전이최대4. 기존실행함수호출시경로대조. 합성검사: 동일id다른box/photo/정답이면재사용거절,새row만추론,동일patch/point점수재생,필수평가누락거절. main관련회귀후 ./experiment로1회실행.모델사진HTML·JSON/SHA대조·열기/렌더상태보고. 롤백source통합SHA revert·새manifest미사용으로원본복귀(데이터삭제없음).

구현worker5함수/테스트2함수,합성·회귀73개OK. 확인반영후표면분모758/648불변·미지원0,기존719특징재사용/39개신규. E2준비분모1678(coverage실측아님). 기존11+새4필수guard계획에고정. 7면flag외원본dict불변검증.

main0b0e912·73검사OK·새동결b69df7816e4c646bcf0314518cd655e8d4ad08799fbfe44ff7231512ec5cb426·공통20261029T203620-18f694cb completed/acceptancefalse·15guard유지. source일반push완료/최신checkout1개보존. 실제결과·HTML·미검증·롤백은동명reports.
