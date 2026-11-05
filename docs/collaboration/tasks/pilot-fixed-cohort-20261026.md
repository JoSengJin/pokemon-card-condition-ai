task_id: pilot-fixed-cohort-20261026
owner: Codex
status: integrated
base_sha: ed1932b6437a40a6bbcee808651628a1b0304c6b
branch: codex/pilot-fixed-cohort-20261026
goal: 릴리스이름만같은다른가중치/manifest·장치/모델입력크기/배치설정을합쳐F2지연/시범조건이통과하는것을막는다.
allowed_files:
- card_condition/pilot_summary.py
- tests/test_pilot_summary.py
- tests/test_pilot_fixed_cohort.py
- docs/collaboration/tasks/pilot-fixed-cohort-20261026.md
- docs/collaboration/reports/pilot-fixed-cohort-20261026.md
- ignored artifacts/pilot-fixed-cohort-20261026/index.html
forbidden_files: producer/CLI등다른소스/실제usage로그/라벨/사진/모델/기존실험/진척/기준/소비서비스/Claude소유파일
contract:
- 기존release_id별합계는label진단값으로유지한다. full release(package_version/input_contract/manifest_sha256/checkpoint_sha256)일관성과성공model_sha256대응을별도로검사한다. 같은이름에다른full identity면conflict이고F2수치조건은False, 정보부족/실패시release=None등정확한실패릴리스정보가없으면조건None(미측정)이다. label만으로실패manifest를추정하지않는다.
- 모든성공기록의device(cpu/mps)/image_size224또는448/batched_views(bool)가같아야합산warm앞뒤p95를평가한다. mixed이면p95값None/조건False, 누락이면None/조건None. 구성별n/p95는진단만표시하고가장좋은구성을고르지않는다. device문자열은하드웨어실물ID확인이아니며원본사진치수도미기록임을공개한다.
- schema1 legacy자료는읽되없는identity/config를기본값으로채우지않는다. 완료조건을None으로남긴다. 유한하지않은/음수시간, bool숫자,모순timing/잘못된상태·cellcount는ValueError로거절한다. producer와과거기록은변경하지않는다.
- 기존분모·카드request_id proxy·독립성/정상카드오탐미측정·pilot_certified=false 유지. 지표값과증거충분성을혼합하지않는다. F2진척점수상향/실제운영성능주장없음.
structure: pilot_summary기존5→최대7함수. validate_usage/configuration_state각1개, 신규검사파일<=7함수. main→summarize→release_group→configuration_state→p954전이,wrapper/재귀없음.
checks: 수정전mixed SHA/device/size그룹p95met=True재현. 고정구성정상boundary/identity충돌/누락/error불명/장치·크기·배치혼합/잘못된숫자·count거절,기존pilot및이전85개회귀. 기존test helper는producer의full identity/config를명시하는정상합성fixture로보완하되임곗값기존assert는유지한다. AST/diff/HTML/main/push.
experiment: 없음,합성로그재계산만. 실사진추론/학습/외부AI0.
handoff: 실제결과/legacy결과변경리스크/원격/롤백기록.

완료: main27c6f20.91개합성회귀PASS/compileall/diff PASS. source7/기존검사7/신규검사7함수. label진단합계와full identity/config gate분리. 실제시범/진척상향미주장. 리스크/롤백/HTML은 reports/pilot-fixed-cohort-20261026.md.
