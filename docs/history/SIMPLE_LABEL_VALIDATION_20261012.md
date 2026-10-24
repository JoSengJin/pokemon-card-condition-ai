# 클릭 중심 라벨 화면 — 0.4.87

## 동작

기본 작업은 영역 확인 → 센터링 → 손상/촬영 제한 위치 클릭 → 직접 확인한 정상 구역 → 저장이다. 전체 카드 라벨·면별 반복 입력·직접 좌표·구역별 표는 접어서 유지한다. 기존 필드 ID와 검증 이동은 유지한다.

손상: 모서리·엣지·기스·구겨짐·오염. 표면 세부 종류는 defect_points의 선택적 types=[scratch,crease,stain]에 저장한다. 같은 위치의 기스+구겨짐은 한 surface_defect 지점의 types로 병합한다. 학습은 기존 surface_defect로 묶으며 세부 종류별 검출 모델이 생긴 것은 아니다. 기존 표면 지점은 종류 미지정으로 보존한다.

촬영 제한: 빛 반사·흐림·가림·사진 잘림·저해상도·원근 왜곡·어두움. visibility_points(issue,x,y)에 위치를, visibility_issues에 면의 제한 종류를 기록한다. 빛 반사는 glare_areas에 해당 구역도 반영한다. 기존 면 전체/위치 미확정 반사 제한을 새 점 하나로 축소하지 않는다. 다른 제한은 위치를 보존하되 현재 추론 정책에서는 면 전체 보류다. 면 전체 버튼은 위치 없이도 촬영 제한을 기록한다. 촬영 제한은 손상 라벨을 만들지 않는다.

정상/미확인 모드의 표면 종류는 명시적으로 표면 전체 선택으로 바꾼다. 기스 없음만 확인하고 구겨짐·오염까지 정상으로 기록하는 것을 피하기 위해서다. 반사 가림 구역 정상 입력 차단 유지. 제한점 삭제는 면 제한을 해제하지 않고, 추가 관리에서 사람이 직접 제한을 해제하면 관련 제한점도 제거한다. 영역 밖 제한점은 빨간 필드 안내로 저장 차단한다.

## 검증

- tests/review_validation.test.cjs: 기존 검증+표면 세부 종류 병합/제한 좌표/손상 미추정/전체 반사 보존/영역 밖 제한 필드 안내 통과. artifacts/simple-label-20261012/js-tests-final.log.
- 전체 Python167테스트 통과47.855초: types·visibility_points의 저장/재로딩/내보내기 및 잘못된 데이터 거부 포함. tests-fixed.log. 첫 실행의 테스트 임시 경로 /var→/private/var 정규화 오류는 fixture를 실제 snapshot 경로에 맞춰 수정했다.
- 실제 브라우저에서 별도 ui-fixture.jsonl에 기스+구겨짐 같은 좌표, 반사 다른 좌표 입력·라벨 저장 성공. 실제 JSON의 types·visibility_points·surface1·edge미확인 검산(browser-check.json). 재열기와 정상 모드의 surface_defect 선택도 확인.
- 실제 사용자 카드 라벨에는 테스트 정답을 쓰지 않았다. 기존 ㅋ-1의 사람 저장 지점은 화면에서 유지됨을 확인했다.
- 8771·8766 서버를 새 계약으로 갱신하며 기존 브라우저 토큰을 유지했다. 미저장 탭을 강제로 새로고침하지 않았다. 개선 화면을 8771로 열었다.

## 변경·제한·롤백

변경: card_condition/review.html, card_condition/regions.py, tests/test_regions.py, tests/review_validation.test.cjs, pyproject.toml, README.md, 이 문서, 소비 CONDITION_ANALYSIS_TODO.md. 증거: artifacts/simple-label-20261012/.
기반4/6(약67%), 이번 정확도 변화0%p, Gemini절감0. 모델 학습/운영 정책 변경 없음. 새 종류별 정밀도·재현율 및 클릭 제한 위치 기반 세밀한 추론은 이번 범위 밖이다.
리스크: 새 세부 종류·제한 위치는 이전 버전 검증기가 거부하므로 구 서버를 혼용하지 않는다. 미선택을 정상으로 해석하지 않는다. 사진에 보이지 않는 손상을 추정하지 않는다.
안전 롤백: .backups/simple-label-0487/review.html을 복원해 화면만 되돌릴 수 있다. 새 regions.py 읽기/검증 호환성은 유지해 저장된 추가 메타데이터를 보존한다. 코드 전체 복귀가 필요하면 먼저 새 라벨 파일을 별도 보관하고 구 버전용 복사본에서만 선택 메타데이터를 제외한다. 실제 라벨을 삭제하거나 원본에 덮어쓰지 않는다.
