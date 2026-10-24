# eBay 수집과 외부 비전 판독 분리

사용자 지적: 사용자가 카드 사진을 계속 제공하지 않아도 되도록 별도 수집 프로그램을 구성하자는 요청이었다. 기존 도구의 Gemini 자동 사진 선별까지 실행한 것은 범위를 넓힌 판단이었다. 이후 기본 수집 실행에서 외부 비전 초기화·호출을 차단했다.

## 변경 파일·diff
- card_condition/ebay_dataset.py: 제목에 명백한 묶음/선택형 매물이면 상세·이미지 다운로드 전에 제외. 제목은 부적합 제외에만 사용하며 적합·상태 정답을 생성하지 않는다.
- tools/collect_ebay_dataset.py: 기본은 collection_only. GeminiProvider를 초기화하지 않고 사진 수집·중복제외·HTML·collection-summary.json 생성 후 반환. --quota-db도 이 경로에서는 불필요. 명시적인 --screen-limit 옵션만 기존 외부 판독 경로에 진입하며 0은 기존 캐시/사람 선별 재개용 호환성을 유지한다. 기존 캐시 내 명백한 묶음도 판독 전에 제외한다.
- tests/test_ebay_dataset.py: 제목 제외/다운로드 차단/기본 CLI의 Gemini 초기화·한도예약 차단 테스트3개 추가.
- artifacts/ebay-mixed-surface-20261017: 원본18사진, 수집결과, Codex 사진 선별1쌍, 상태 null 검토manifest, AI초안2개, human-review.html, pending-human.json. 후딘 원본1~6을 직접 확인, 동일 실물은 사람 미확인 유지. 팬텀69ee 사진1/2의 서로 다른 카드 관찰로 제외. Gemini 성공으로 표시하지 않음.

## 실제 실행
새 eBay 후보4매물18사진 확보. 초기 Gemini 판독2시도는 일시혼잡으로 실패. 기본경로 수정 후 같은 캐시를 실제 CLI로 실행해 Gemini0·사진18재사용·정답0 확인. 관련 unittest test_ebay_dataset/test_label_drafts 27개 통과(로컬HTTP 포함). 후딘 초안은 카드영역확인 전 차단됨을 검증했다. 기존 사용자 라벨 불변·모델 재학습0·정확도 변화 미측정·개발4/6 유지.

## 실행
.venv/bin/python tools/collect_ebay_dataset.py --consumer-root "$POKECOLLECTOR_ROOT" --learn "$POKECOLLECTOR_ROOT/learn" --output artifacts/새수집폴더 --limit 4

기본 사진 수집은 eBay API만 사용한다. 앞뒤 자동선별 완료를 뜻하지 않는다. Codex가 준비한 후보는 사람 검토 전 상태 라벨로 학습되지 않는다.

## 리스크·롤백
제목 제외는 보수적 필터라 일부 적합한 사진을 가진 묶음 매물도 제외될 수 있다. 사람 승인 전 정상/손상은 보장되지 않는다. 외부 판독은 명시 옵션에만 남아 있다. 기본 변경으로 기존 명령은 자동 Gemini선별을 하지 않으므로 의도된 동작 변경이다.
artifacts/ebay-mixed-surface-20261017의 ebay_dataset.before.py, collect_ebay_dataset.before.py, test_ebay_dataset.before.py로 파일을 복원하면 이번 전체 코드 변경을 되돌릴 수 있다. 새 연구파일은 보관하고 사용자 저장 이후 labels-review.jsonl을 삭제/덮어쓰지 않는다. 실제 호출장부를 롤백하지 않는다.
