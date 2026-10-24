# 신규 독립 앞면 반사 시험 준비

사용자가 새 실물 사진 learn/ㅊ/light/img_1.png를 제공했다. 기존 live69행·독립eBay2행·ㅊ2행 사진의 decoded RGB 비교 중복0. test분할을 예측 전에 지정하고 ㅊ-light-test로 별도 실물 등록했다. 기존 두 ㅊ행은 완전히 보존했다.

변경: data/chieut-review-20261011.jsonl에 신규1행, artifacts/chieut-heldout-20261011/{before.jsonl,registration.json,run_after_geometry.py,geometry-handoff.png}, 본 문서, 소비 TODO. 모델/기준/원본사진 변경 없음.

새 사진 관찰 제한glare는 요청한 사례로 사용자 제공한 사실만 반영했다. 반사 위치·구체적 카드결함·전체상태 정상/불량은 추정하지 않았다. full-photo box는 임시이며 box_reviewed=false. 실제 브라우저8768에서 신규카드/앞면사진/시험분할/반사라벨과 영역입력 활성 상태 확인.

영역 확인 전에 run_after_geometry.py가 추론을 거부하는 것을 실제 실행했다. 저장되면 고정 관찰모델 SHA를 강제하고 이전 독립2실물의 명시적 정상면3개와 신규 반사1면을 비교한다. 기존 ㅊ-light/train은 포함하지 않는다. 이 시험에서 모델/임계값 선택을 하지 않는다. 정식 시험은 아직 실행하지 않았다.

리스크: 소규모 시험이며 형식상 양성/음성이 있어도 일반화 승인 근거가 충분하지 않다. raw데이터는 사용자가 추가저장 중일 수 있으므로 전체 덮어쓰기 롤백 금지. 복구하려면 before.jsonl과 현재를 대조해 신규행만 격리하고 후속저장 보존. 신규사진은 학습에 사용하지 않았다. Gemini절감0, 개발기반4/6완료·품질검증진행.

## 완료 후 기록

사용자가 영역·라벨 저장을 완료해 최초 정식 시험을 실행했다. 위 준비 기록은 당시 상태다. 현재 결과는 CHIEUT_HELDOUT_VALIDATION_20261011.md를 따른다. 완료 카드 재라벨링은 필요하지 않다.
