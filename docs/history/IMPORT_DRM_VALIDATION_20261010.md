# ㄷ·ㄹ·ㅁ 신규 사진 등록

사용자가 learn/ㄷ, learn/ㄹ, learn/ㅁ에 뒷면 엣지 손상 있는 사진을 제공했다. 각 img.png는 앞면, img_1.png는 뒷면임을 직접 이미지로 확인했다. 총6장 등록,55→58항목. 새 사진의 정확한 디코딩 픽셀 해시가 기존/새 사진과 중복되지 않음을 검사했다. 다른 촬영의 같은 실물인지는 해시만으로 증명할 수 없으므로 사람 확인 필요.

세 항목을 모델 결과 확인 전에 train으로 지정, 사용자 설명에 근거해 전체/뒷면 엣지1만 기록. 앞면의 정상 여부·다른 결함 종류·전체 평가 가능 여부·동일 실물 확인은 추정하지 않았다. 뒷면 box=null, 위치와 정상 구역은 비워 두었다. 기존55항목·val/test 분할 전체 불변 단언 통과. 원본은 백업 후 atomic_write로 등록, ReviewStore에서 전체 행 동등성 검산 통과.

현재 필요한 사람 작업: ㄷ→ㄹ→ㅁ 뒷면 카드 영역 지정, 엣지 손상 위치를 같은 종류의 점이나 구역1로 저장. 손상이 없는 구역을 충분히 관찰했다면 해당 엣지 구역만0으로 저장. 사진이 가려지거나 불분명하면 null 유지. 앞면 라벨 전체 작성이나 같은 실물 확인은 이번 지역 학습의 필수 조건으로 강요하지 않는다. 같은 실물이라면 그룹 일치로 누수 방지 필요.

ㄹ 뒷면은351×466, 나머지 뒷면716×960 및715×983이다. 저해상도 때문에 보이지 않는 세부를 정상으로 채우지 않는다. 앞뒤 파일 크기와 경로는 inventory에 보존했다. 정상 뒷면 엣지 자료0실물은 아직 해결된 것이 아니다. 위치 자료가 없어서 이번 등록만으로 재학습하지 않는다.

변경 파일: data/learn-review.jsonl(새3항목), data/learn-review-before-drm-20261010.jsonl.bak, artifacts/import-korean-drm-20261010.json, 마스터 CONDITION_ANALYSIS_TODO.md, 이 문서. card_condition/review.html의 오래된 ‘점은 학습에 사용하지 않는다’ 안내를 실제 point_dataset 동작에 맞춰 수정, pyproject.toml0.4.21. 제품의 저장/학습 동작은 변경하지 않음.

검증: 기존 행 불변·이미지 중복0·load_manifest(train/val, require_gradable=False)·validate_annotations·ReviewStore roundtrip·쓰기 전 revision 검사 통과. JS 회귀 및 wheel 결과 /private/tmp/condition-import-drm-ui-tests.log, /private/tmp/condition-import-drm-wheel.log. 원본 등록 후 SHA2568482421b1b9fccd8c5c3f91ced2d0f2c331812088c87636c03ae785ebf1537c3.

롤백: 기존 백업과 현재 파일을 비교해 이번3항목만 분리하고 이후 사용자 저장을 덮어쓰지 않는다. 안내 문구/버전/문서/TODO는 되돌릴 수 있다. 기존 학습 모델은 변경하지 않았으며 Gemini 호출 없음. 위험: 손상 양성만 추가하면 정상 자료 부족과 오탐을 해결하지 못하므로 정상 구역은 사람이 관찰한 경우만 별도 확보한다.

브라우저에서 ㄷ 사진 묶음·뒷면 위치 도구 펼침·엣지 종류 선택 확인, 카드 영역은 미지정으로 사람 입력 대기. 스크린샷 /private/tmp/condition-drm-review.png. UI 회귀·0.4.21 wheel 빌드 성공, wheel review.html 소스 일치·등록 후 원본 SHA256 불변 검산 통과.
