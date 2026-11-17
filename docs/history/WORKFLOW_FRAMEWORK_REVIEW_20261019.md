# AutoGen / LangGraph 검토 및 라벨 재개 — 2026-10-19

결론: 둘 중 LangGraph가 연구 파이프라인의 사람 대기·재개·지속 실행 관리에 적합하다. 이번에는 검토만 했으며 패키지 설치·마이그레이션·운영 교체는 하지 않았다.

## 현재 코드 근거
- tools/collect_ebay_dataset.py: screening 미요청 시 collection_only로 반환하고 Gemini 객체 생성 전 종료. 기존 수집/요약 파일을 활용한다.
- card_condition/review.py: ReviewStore.save의 revision/hash 검사와 atomic_write는 그대로 재사용한다. 오케스트레이터가 라벨 원장을 대체하지 않는다.
- card_condition/detail_data.py: 사람 답변·사진 SHA·전체 back anchor·그룹/split 검증 뒤 국소 row를 만든다. 미확인을 정상으로 바꾸지 않는다.
- card_condition/detail_bag.py: 실제점과 구역존재 감독을 구분하고 두 클래스 없으면 학습을 거부한다.
- pyproject.toml: 현재 torch/torchvision/Pillow. LangGraph·AutoGen 의존성은 추가하지 않았다.

## 비교
AutoGen: 에이전트 간 대화·역할 분업에 적합했던 프레임워크. 현재 공식 README는 archived/no longer maintained라고 명시한다. 신규 도입 비추천. 여러 에이전트 토론은 호출·컨텍스트를 늘릴 수 있고 절감 보장이 없다.
LangGraph: 프로그램이 정한 단계·조건 분기·checkpoint·human interrupt/resume에 적합. 우리 연구의 수집→선별→사람 확인→입력 검증→특징 추출→고정 실험→회귀 검사→HTML에 한정해 검토한다. 실행 관리가 실제로 복잡해질 때 도입하며, 현재 Python/파일 저장으로 해결되는 부분은 유지한다.

## 적합한 사용 설계 (미구현)
1. 수집/선별: 기존 CLI를 호출. 단일 카드/로고/네 변/모서리 적합성과 상태 정답은 별도 저장.
2. 사람 확인: 이미지 SHA+ROI+종류+질문 ID를 interrupt payload로 저장. 답변은 기존 라벨 원장에 기록. 완료/판단불가 항목은 재질문하지 않는다.
3. 준비: 그룹 누출/양음성 클래스/영역 근거 검사. 정상 모서리0이면 해당 학습만 대기하며 독립된 작업을 계속한다.
4. 실행: 사진 SHA+ROI+전처리+백본 버전으로 특징 캐시. 동일 설정을 재개 시 중복 실행하지 않는다.
5. 평가: 고정 비교 cohort/실제점 누락/오탐 분모/새 오류를 코드로 계산하고 HTML 저장. 모델 채택은 정해진 회귀 기준으로 결정.
6. LLM은 모호한 새 후보의 짧은 진단에만 선택적으로 사용. 메시지 전체/사진 base64/긴 로그 대신 경로·해시·요약 전달. 호출/토큰/재시도 상한을 별도로 둔다.

LangGraph interrupt 재개 시 해당 node 처음부터 실행되므로 외부 호출·파일 쓰기를 멱등 처리하거나 별도 task로 분리해야 한다. checkpoint만 넣고 중복 방지를 생략하면 오히려 재실행 비용이 생긴다.

## 성능/토큰 측정 원칙
- CV 정확도: 프레임워크로 개선됐다고 주장하지 않는다. 같은 cohort FN/FP/실제점 누락과 독립 자료로 평가한다.
- 프로젝트 LLM: 호출 수, input/output tokens, 캐시 적중, 재개 중복 호출을 도입 전후 측정. 수집 기본 흐름은 Gemini0이므로 현재 절감 실적0.
- Codex 세션: 저장된 증거/짧은 실행 요약으로 반복 조사를 줄일 여지는 있지만, repo 프레임워크 설치가 이 대화의 모델/주간 토큰 한도를 제어하지 않는다. 절감 비율 미측정.

## 이번 라벨 및 검증
A·B 각각 사용자 ‘모서리 결함 있음’을 corner1로 저장. 이전 photo10 포함 국소3곳, 기존 실제점14곳과 합계17 양성/정상0. 새 정확점 생성0·엣지/표면 정답 생성0. 새 특징 추출/학습/추론0이므로 정확도 변화는 측정하지 않았다. 두 클래스가 없어서 새 모서리 모델 학습은 대기한다. 기존14점 데이터/이전 실행 계획은 보존.

## 변경 파일 / 핵심 diff
- artifacts/workflow-review-20261019/: 확인 답변2개, 검증된 국소3행 manifest, readiness/verification/tests.log, 사진 HTML, 실행 재현 script.
- WORKFLOW_FRAMEWORK_REVIEW_20261019.md: 이 검토문서.
- 소비 프로젝트 CONDITION_ANALYSIS_TODO.md: 현재 체크포인트 한 항목 추가.
실행 검증: 관련 unittest 32개 통과(실제 tests.log), canonical70행 SHA 불변. 새 프레임워크 실행/토큰 절감은 검증하지 않았다.

## 리스크 / 롤백
새 답변은 crop 내 모서리 존재 정답이며 정확한 픽셀 위치가 아니다. 정상0 데이터 부족으로 분류 경계 학습에 사용할 수 없다. LangGraph는 제안 단계이고 런타임 변경 없음. 롤백은 이번 artifact 디렉토리와 본 문서를 제거하고 TODO의 이번20261019 항목만 되돌린다. 원본 라벨·이전 artifacts·운영 모델은 변경하지 않았다.

## 공식 근거
- [AutoGen official repository](https://github.com/microsoft/autogen)
- [LangGraph human interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
