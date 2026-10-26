task_id: listing-loaded-checkpoint-20261026
owner: Codex
status: integrated
base_sha: 2732efbb912e20967548bfc08d5d1de3db25eb3c
branch: codex/listing-loaded-checkpoint-20261026
goal: validation listing 추론도 사전고정 checkpoint SHA와 실제 읽은 모델 바이트를 결속하고 observation 모델 불일치를 사진 analyze 전에 거절한다.
allowed_files:
- card_condition/listing_inference.py
- card_condition/listing_observation.py
- tests/test_listing_inference.py
- tests/test_listing_loaded_checkpoint.py
- docs/collaboration/tasks/listing-loaded-checkpoint-20261026.md
- docs/collaboration/reports/listing-loaded-checkpoint-20261026.md
- ignored artifacts/listing-loaded-checkpoint-20261026/index.html
forbidden_files: 다른 소스·실사진/라벨·기존 기록·checkpoint·기준/진척·Claude 소유 파일
contract:
- region load_probe_model에 checkpoint 경로 재개방 대신 사전hash와 대조한 BytesIO를 제공한다. 기존 helper의 filelike 지원을 재사용한다. mismatch는 load/infer 전 거절한다. 최종 unchanged 검사는 유지한다.
- observation_evidence에 optional expected_model_sha256만 추가한다. 주입/자체 생성 analyzer 모두 model_sha256을 사진 analyze 전에 대조한다. 검증용 listing 호출자가 사전hash를 넘긴다. 기존 API 주입 호출은 기본값 None으로 동작 유지.
- threshold/사진선택/사람관찰 masking/정답/운영 routing/품질 주장은 바꾸지 않는다. 실제 사진 추론·새 학습·외부AI 호출 없이 합성/Mock만 검사.
structure: listing_inference1→1, observation1→1, 기존 검사4→4, 신규 검사<=7. infer→observation_evidence→analyze 기존 경로 유지, 추가 wrapper 없음. load_probe_model 기존 경로에 BytesIO만 전달.
checks: path 재개방시 임시 다른 metadata 로드 후 원복으로 기존 최종hash검사를 통과하는 반례; 변경 전후 snapshot fixture, 읽기전 교체거절, observation mismatch/동일SHA. 기존114 + 실제사진 없는 listing 합성회귀, AST/compile/diff/HTML/main push.
experiment: 없음. 합성 로딩/계약 검사이며 성능 실험 아님.
handoff: 실제 검사/미측정/파일·diff/리스크·메모리 비용/롤백/원격/HTML 기록.진척30/100 유지.

완료:95eb546.121합성회귀PASS24.451s/AST/compile/diffPASS. 리스크·롤백·미측정은 보고서.진척30/100.
