# 파일럿 검토 충돌·수량 보완

개발 진척률 30/100(usable-card-analysis-v1.0), 이번 +0점. 파일럿 검토 입력 순서에 따라 수정 수량이 달라지는 문제와 잘못된 수량을 차단했다. 모델 품질·실사용 진척 개선은 미측정.

검증 코드 main 225cce0 / 원본 계약 d319d65·구현 7ad5872.

## 변경 파일과 핵심 diff
- card_condition/pilot_summary.py: completed counts를 결과 SHA별 대조. 동일 counts 중복은 한번, 상충 counts는 입력 순서와 관계없이 ValueError. 미완료는 따로 집계하고 완료 기록을 덮지 않음.
- counts의 두 correction key 필수, 제공된 모든 count는 bool 아닌 비음수 정수, report SHA는 nonempty string, 완료 flag는 bool. missing을 0으로 추정하지 않음.
- tests/test_pilot_review_conflicts.py: 동일중복/양방향충돌/미완료/잘못된수량/식별값/CLI 6검사. task·이 보고서 추가.

## 실제 검증
- 수정 전 동일 결과 검토 파일의 순서만 반대로 넣어 corrected_cells=-1 또는2 재현.
- stdlib worktree venv에서 테스트 helper가 cli/Pillow를 import하여 초기 5개 import error. 이후 기본 checkout의 설치된 Python interpreter로 동일 worktree의 합성 JSON 단위5개 PASS0.013s. 새 의존성 설치/실사진 추론 없음.
- main PYTHONPATH=tests .venv/bin/python unittest runner: 기존108+신규6=114 PASS8.636s, torch threads1. 신규 CLI는 오류 exit1/stdout empty 확인.
- source/test AST 각각7/7함수, 새 호출깊이 증가 없음. compileall/diff check PASS.
- 기존 회귀에 합성 랜덤 모델 forward와 mock metadata 평가 포함. 새 학습·실사진 평가·외부AI 호출 없음. 실제 FN/FP·검토시간·Gemini 절감 미측정.

## 리스크·미완료
- 과거 손작성 검토가 correction key를 빠뜨렸거나 bool/음수를 썼다면 이제 거절한다. 정본 listing_review.review_record 출력은 두 key와 비음수 정수를 제공한다.
- 상충 완료 검토의 우선순위를 자동 선택하지 않는다. 사용할 기록 하나를 명시해야 한다. 원본 검토/로그는 고치지 않았다.
- F2 기준·release/config 진단·region 수정 의미 유지. 추가 face_counts는 합산하지 않는다. pilot_certified=false 유지.
- 별도 사람 provenance·실사용 시간·정상카드 오탐 조건 미충족. progress 수치/배점 불변.

## 롤백
main 구현 git revert 225cce0 후 관련 회귀 재실행/일반 push. 실제 로그·정답·모델 불변.

HTML: artifacts/pilot-review-conflicts-20261026/index.html. 열기 요청과 렌더 확인을 분리 기록한다.

열기 도구 queued: 요청 전달, 실제 렌더 미확인.
