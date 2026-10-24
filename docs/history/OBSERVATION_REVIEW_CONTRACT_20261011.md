# 매물 관찰 검토 계약 일치 — 0.4.70

## 문제·수정

독립 ListingAnalyzer는 visibility_issues를 생략하면 미확인으로 보류하지만 listing-infer와 공유 listing_readiness는 get(..., [])로 제한 없음으로 처리했다. 같은 입력이 실행 경로에 따라 다르게 평가되던 오류를 수정했다.

관찰 검토 필드가 빠진 면은 구역 추론을 생략하고 observation_not_reviewed·score=null·state=unknown으로 표시한다. 명시적인 []는 호출자가 제한이 없다고 확인했다는 입력이다. 반사·그늘 등 기존 관찰 제한은 유지하고, 관찰 모델 점수로 사람 검토 누락을 자동 해제하지 않는다. 미검토는 카드 불량을 뜻하지 않는다.

## 변경 파일·핵심 diff

- card_condition/listing_inference.py: 카드/box 확인과 함께 관찰 검토 필드 존재를 확인하고 미검토 면의 구역 추론을 생략.
- card_condition/listing_readiness.py: 공통 매물 판정에서도 필드 누락을 observation_not_reviewed로 유지. comparison.py와 독립 API 호출자도 같은 계약 적용.
- tests/test_listing_inference.py·test_listing_readiness.py: 같은 입력의 누락 검토/명시적 검토 구분, 원본 불변과 점수 보류 검증.
- tests/test_tile_max.py: 검토 완료를 전제하는 정상 fixture에 visibility_issues=[]를 명시. 실제 사람 라벨을 변경하지 않았다.
- pyproject.toml·README.md·본 문서·마스터 TODO·artifacts/observation-review-20261011/.

## 실행 검증

수정 전 재현 테스트2개가 실패했다: 추론 구역23개가15개로 줄어야 하나 그대로였고, 미입력 앞면이 미확인으로 보류되지 않았다. 수정 후 관련 테스트 통과. 전체 첫 실행에서는 관찰 검토를 생략한 tile-max fixture의16구역 추론 전제가 실패해 명시적 검토 입력을 추가했다. 이후 전체142테스트 통과(46.967초). 저장소 밖 설치본11테스트 통과(17.861초), wheel52개 Python/HTML파일 소스 byte 일치.

실제 frozen source의15매물·160구역·27관찰 면을 MPS로 수정 전후 재추론했다. predictions·listing_readiness·observation_evidence가 정확 일치했다. 현재 실제 검증 면27개는 모두 관찰 검토 필드가 있었다. 이는 반복 검증 자료의 경로 일치 확인이며 독립 성능 측정이 아니다.

별도 진단 스냅샷에서 d 앞면 visibility_issues만 생략했다. 원본 라벨과 source는 보존했다. 백업 코드에서는 미검토 앞면8항목에 점수를 냈고, 새 코드에서는 앞면21항목을 미확인으로 보류했다. 전체 추론160→152로8구역을 생략했다. 동일 입력을 독립 ListingAnalyzer로 실행해 해당 매물의 predictions/readiness가 정확 일치했다. 관찰 모델27면 신호를 병행하지만 누락 검토를 해제하지 않았다.

근거: before.json·after.json, one-review-omitted.jsonl, omitted-before.json·omitted.json·omitted-api.json, omission-check.json, checks.json. 원본/source/live 및 두 선택 모델 해시 불변 확인. 실제 정확도 상승 미측정·모델 변경 없음·Gemini절감0건·기반4/6단계(67%, 정확도 아님).

## 리스크·롤백

관찰 검토 필드를 생략한 오래된 입력은 이제 더 많이 보류된다. 자동으로 []를 채워 보류를 해제해서는 안 되며, 실제 검토 여부는 호출자가 확인해야 한다. 비교 보고의 완료 구역 수가 바뀔 수 있지만 결함 정답이나 모델 점수가 바뀐 것은 아니다. 이 계약은 자동 반사 검출이나 운영 Gemini 생략을 제공하지 않는다.

후속 수정 여부를 확인한 뒤 .backups/observation-review-0470/의 두 실행 파일·세 테스트·pyproject.toml·README.md를 복원하면0.4.69로 돌아간다. 기록 artifacts는 보존 가능하다. 사람 라벨·모델·운영 서버는 수정하지 않아 데이터 롤백이나 재시작이 필요 없다.

에튜: missing과 empty는 다르다. 키가 없으면 확인하지 않았다는 뜻이고 []면 확인했으나 제한이 없다는 뜻이다. get(key, [])로 합치면 그 차이가 사라지므로 두 경로에서 키 존재를 먼저 검사했다.
