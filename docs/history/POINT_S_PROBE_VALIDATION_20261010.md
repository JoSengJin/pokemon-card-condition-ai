# ㅅ 신규 정상 뒷면 검증과 라벨 도구 보강

사용자가 저장한 ㅅ 뒷면은 box지정·면별 gradable1 및 결함0이지만 region_labels는 비어 있었다. 면0을 자동으로 구역0으로 확장하지 않고 사용자에게 테두리 전체 정상 여부를 확인받았다. 명시 확인 후 테두리8구역 edge_defect0만 추가, 기존 면별 정답은 보존했다. 다른 구역 종류와 중앙은 미확인이다.

## 누수 방지와 결과

- data/learn-review-before-s-normal-confirmation-20261010.jsonl.bak 원본 백업.
- artifacts/point-evidence-20261010-s-probe.jsonl 동결 SHA256: 1b839eff4dd1072941bd7ae97c5aba8824e7c23d0d0730e465646412d79d5c81.
- artifacts/point-evidence-s-probe-receipt.json: train119불변, 기존val50불변, 신규val8구역(1실물) 추가. 기존 다른59행 불변. 재학습 없음.
- 기존 round17 동결 모델4개에 point-probe 실행. round17개발이력/체크포인트 메타데이터의 ID·실물그룹·이미지해시와 ㅅ 겹침 검사 통과. 입력과 모델 파일 SHA256 실행 전후 불변 확인.
- 결과: artifacts/point-s-new-validation-20261010.json, 실행 로그 /private/tmp/condition-s-probe.log. 종료0.

| 고정 모델 | 정상 테두리8구역 중 엣지 오탐 |
| --- | --- |
| MobileNet 기본 | 8 |
| MobileNet 보정 | 8 |
| ResNet18 기본 | 8 |
| ResNet18 보정 | 7 |

한 실물의 구역들이므로 독립8실물 성능이 아니다. 엣지 정상 사례만 평가했으므로 결함 누락·다른 종류 성능은 측정하지 않았다. ㅅ은 신규 개발검증이며 최종시험이 아니다. 오탐은 라벨 오류의 증거가 아니므로 사람에게 다시 정상 확인을 요구하지 않는다. 운영 채택·Gemini 자동 생략은 보류, 실제 호출절감0건.

## 정상 입력 도구

card_condition/review.html에 confirmNormalEdges와 사용자 확인 버튼을 추가했다. 구역별 도구에서 '테두리 전체를 확인했으며 엣지8구역 정상으로 입력'을 누르고 확인한 경우에만 입력한다. 별도 라벨 저장이 필요하다. 카드 영역 미지정, 면 엣지0 미확인, 관찰 제한/반사 위치, 엣지 결함 점 또는 구역1이 있으면 일괄 입력을 거절한다. 중앙과 모서리/표면 정답은 보존한다. 기존 정답을 자동 확장하지 않는다.

tests/review_validation.test.cjs에 정상8구역·다른 정답 보존·미확인/제한/양성 충돌 시 무변경 검사를 추가했다. pyproject.toml0.4.23. Node검사 통과, Python57개 통과(/private/tmp/condition-s-python-tests.log). wheel빌드 성공(/private/tmp/condition-s-wheel.log), 포함된 review.html과 소스 바이트 일치. 실행 화면에서 버튼과 저장된 ㅅ 정상 구역 표시 확인. /private/tmp/condition-s-normal-button.png.

변경 파일: data/learn-review.jsonl의 ㅅ만, 백업·분리된 probe입력/receipt/report, review.html, tests/review_validation.test.cjs, pyproject.toml, 본 문서와 마스터TODO. 모델 재학습이나 운영 체크포인트 변경 없음.

## 다음 의존성과 롤백

정상 학습 뒷면은 여전히 ㅂ1실물뿐이다. 추가 신규 정상 실물1장을 학습 다양성 보강용으로 확보한다. ㅅ을 학습으로 옮겨 검증 개선처럼 보고하지 않는다. 새로운 프레임워크와 미세조정 확대는 근거가 부족해 보류한다.

UI 롤백은 confirmNormalEdges·버튼·추가 테스트·버전 변경을 함께 되돌린다. 라벨은 별개로 보존한다. 라벨 복구는 백업과 비교해 이번 ㅅ 엣지8구역과 확인메모만 되돌리며, 이후 저장을 잃을 수 있는 전체 파일 덮어쓰기는 피한다.
