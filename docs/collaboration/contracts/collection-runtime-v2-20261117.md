# 합성 collection 후보 v2 wire 계약

이 버전은 synthetic_fixture 전용이다. 실제 자료/사람 수신 활성화는 없다. kind=synthetic_collection_contract, schema_version=2. exact keys: schema_version,kind,contract_id,spec_sha256,packet_id,data_origin,collection_status,human_truth,eligible_for_collection,display_profile,zoom_policy,assignment_ref,seal_policy_ref,access_policy_ref. contract_id는 자신을 제외한 모든 필드의 sort_keys/separators=(',',':')/ensure_ascii=True/allow_nan=False UTF-8 SHA256. spec_sha256/packet_id도 소문자64hex.

display_profile은 기존 v1 synthetic profile 스키마 그대로이며 null은 미정. zoom_policy exact keys scale_min,scale_max,pan_x_limit,pan_y_limit: 각각 null 또는 유한 수, scale은양수/pan한계는0이상, scale_min/max는 둘다null 또는 순서가맞는 값. 세 ref는 null 또는 공백아닌 문자열. 실제 기종/배정/수치 승인으로 간주하지 않는다.

readiness 결과: synthetic_ready는 display viewport/image_css/DPR·H zoom policy·세 ref가 갖춰진 합성 시험 조건일 때만true. collection_ready/eligible_for_collection/human_truth는항상false. missing에 미정항목과 actual_collection_not_authorized를 반환한다. synthetic_ready는 실사용 적격이 아니다.

후보 응답 exact keys: schema_version=2,kind=synthetic_collection_response,contract_id,packet_id,data_origin=synthetic_fixture,collection_status,human_truth=false,eligible_for_collection=false,base_response(그대로인v1),viewport_events,zoom_events,claimed_actor. claimed_actor는 human/ai/unknown 중 브라우저 주장일 뿐, 보관자 문맥/배정과 별도로 검증한다. 추가 관측은 v1키에 넣지 않는다. S1/S2 이벤트 스키마는 해당 구현 전에 아래에 고정하고 S3가 독립 검사한다. 실제 input을 v1 synthetic으로 위장하지 않는다.
