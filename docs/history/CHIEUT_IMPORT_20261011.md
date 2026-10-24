# ㅊ 신규 자료 확인 반영

사용자가 서로 다른 신규 실물2장임을 확인했다. back의 바깥 테두리8구역은 충분히 확인했고 정상, light는 전반적으로 상태가 안 좋고 빛 때문에 상단 중앙이 보이지 않는 사례다.

변경 파일: data/chieut-review-20261011.jsonl, artifacts/import-chieut-20261011/{unassigned.jsonl,audit.json,confirmation.json,live-check.json}, 본 문서, 소비 프로젝트 CONDITION_ANALYSIS_TODO.md.
핵심 변경: back 엣지8구역0만 저장, light glare/upper_center만 저장하고 구체적 결함은 null 유지. 기존69행 및 신규 eBay2행 파일·모델 변경 없음. light=train/back=test 사전 분리, 모델 출력 노출 없음.

검증: 기존 두 inventory의 모든 사진과 EXIF 적용 RGB 픽셀 해시 대조에서 중복0. ReviewStore 검증 통과. 실행 서버8768 /api/review에서 두 실물/분할/정상8구역/상단중앙 반사/표면 정답null 검산 통과. 전체 테스트 및 재학습 미실행.

남은 사람 개입: 두 사진의 카드 영역 지정·box_reviewed 확인만 필요. full-photo box는 임시 입력이며 검토 완료로 표시하지 않았다. 기존 정답은 다시 작성할 필요 없다. 사진이 한 면씩이므로 동일 실물 앞뒤 확인은 요청하지 않는다.

위험: back290×403·light344×456 해상도 한계, 슬리브/배경을 카드 영역에 섞으면 입력 불일치 발생. PSA10급이라는 설명을 등급 인증이나 모든 결함 정상으로 전환하지 않았다. 학습용 light로 독립 최종 성능을 주장하지 않는다.
롤백: 아직 기존 학습/시험 inventory에 합치지 않았으므로8768 서버 중지 후 신규 data/chieut-review-20261011.jsonl만 격리하면 된다. 후속 사용자 저장이 있으면 파일을 삭제하지 말고 보존한다. artifacts는 이력으로 보존.

진척률67% 유지, 이번은 정답 입력 준비이며 정확도 개선 미측정·Gemini절감0.
