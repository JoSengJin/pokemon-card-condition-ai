# 검증용 매물 추론 모델 결속

개발 진척률 30/100(usable-card-analysis-v1.0), 이번 +0점. 별도 probe 로더에도 사전 SHA와 deserialize 바이트를 결속했다. 모델 품질은 미평가.

검증 코드 main95eb546, 원본 계약d6ba955 / 구현5344e9c.

## 변경 파일·핵심 diff
- card_condition/listing_inference.py: checkpoint bytes를 한 번 읽어 사전 SHA와 대조한 뒤 BytesIO로 기존 load_probe_model에 전달한다. raw buffer 참조는 로딩 후 해제. 기존 종료 시 입력 불변 검사는 유지. observation 사전 SHA도 전달.
- card_condition/listing_observation.py: optional expected_model_sha256를 제공하면 주입/자체생성 analyzer 모두 사진 analyze 전에 대조. 기존 기본값 None 호출 호환.
- tests/test_listing_inference.py: 정상 mock 관찰 모델 SHA를 실제 fixture 바이트 SHA로 명시.
- tests/test_listing_loaded_checkpoint.py: 실제 metadata deserialize, 읽기전교체거절, 임시교체후원복, 관찰 SHA/주입 경계 4검사. 이 보고서와 task 추가.

## 실제 검사
- 변경 전2732efb 소스를 메모리에 로드한 합성 재현: 원래image_size224인데 임시448 checkpoint 로드 후 원복으로 기존 최종hash통과, 보고448. 실제 모델 forward0. 최초 재현 명령은 새 helper가 main에 아직 없어 import error; 통합 후 같은 합성 재현 성공.
- 변경 후 임시교체해도 snapshot224만 로드/보고, 읽기전 SHA변경은 deserialize전에 실패/결과없음. 잘못된 observation SHA는 analyze0.
- base PYTHONPATH=tests .venv/bin/python unittest runner: 이전114 + 신규4 + 기존listing inference1/observation2 =121 PASS24.451s, torch threads1. 실제 사진 없는 합성 이미지·랜덤 모델 forward/mock만 실행. 새 학습·실사진 추론·외부AI0.
- AST 함수수1/1/4/7, compileall/diff PASS. 기존 helper/filelike 지원 재사용, 새 wrapper나 호출깊이 증가 없음.
- 실제 FN/FP/분모·일반화·검토시간·Gemini절감은 새로 평가하지 않았다. 합성회귀 수치는 모델 정확도가 아니다.

## 리스크·미완료
- checkpoint 원본 바이트와 deserialize buffer가 로딩 동안 메모리를 추가 사용한다. 소형 현재 checkpoint와 동일한 기존 Analyzer snapshot 방식이며 대형모델 메모리 실측은 하지 않았다.
- optional observation guard 기본값None은 API 주입 호출의 호환을 유지한다. 검증용 listing 명령은 사전hash를 항상 제공한다. 기존 사진선택/관찰mask/threshold/routing은 불변.
- 이 명령은 validation 진단이다. D1/D2/D3 독립 인증·C품질/실제점조건·F2실사용 충족을 증명하지 않는다.

## 롤백
main 구현 git revert95eb546(명령은 git revert 95eb546) 후 관련 회귀/일반push. 실제 모델·정답·사진·과거보고서 불변.

HTML artifacts/listing-loaded-checkpoint-20261026/index.html. 열기 요청과 실제 렌더는 구분한다.

열기도구 queued: 요청 전달, 실제 렌더 미확인.
