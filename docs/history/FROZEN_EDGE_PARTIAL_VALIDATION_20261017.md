# 고정 전후 모델의 새 피카츄 부분 확인

라벨 저장 완료 답변 뒤 실제 파일을 확인: 고우스트 뒷면 모서리1/엣지1점은 저장됐으나 box_reviewed=false. 피카츄 앞뒤영역true, 뒷면엣지1점 저장. 정상구역은두카드모두0개. 사용자 점/종류/영역을 변경하지 않았다. 표면면라벨1만 있고 좌표가 없는 항목은 이번 엣지평가에서 추정하지 않는다.

영역 확인된 피카츄 back upper_center 엣지결함1구역에만 frozen-plan에 사전 고정된 전후back checkpoint를 첫 적용했다. 전0.2808323·후0.2571878로 모두 누락1/1(100%, 변화0%p), 새정상정답0이라 오탐률은null/계산불가이며0%로 표시하지 않았다. 하나의확인구역으로전체성능/실물독립일반화를 주장하지 않는다. 독립실물여부는사진만으로확정되지않음. 기존연구182구역의1곳회복이새사진에서재현됐다는증거없음·운영교체0·기반4/6유지.

검증: 모든4checkpointSHA와4사진SHA를frozen-plan과대조. test split유지,확인된back만추출,모델development ID/decodedpixels 교집합0,requires_gemini true/production_ready false,입력라벨파일/원시plan바이트불변assert. 실제RegionAnalyzer로전후추론실행. 새학습/임계값선택0. 원시frozen-plan은수정하지않고evaluation-progress에평가된row와부분상태를별도기록했다.

변경파일: artifacts/edge-frozen-pikachu-20261017/human-frozen.jsonl·result.json·run.py·index.html·구역사진; artifacts/edge-frozen-intake-20261017/evaluation-progress.json; 본문서와소비TODO. 패키지소스/사용자원본라벨/모델변경0.

남은사람의존: 고우스트back카드영역확인false이므로그사진평가만보류. 피카츄상단중앙외에정상으로충분히확인한엣지범위가있는지확인필요. 이미저장된점은재요청하지않는다. 추가정답이들어와도동일고정모델을유지하며이미평가된row를새독립시험으로중복계수하지않고동일코호트의부분완료로기록한다.

리스크: 단1구역·정상0·실물독립미확정이라서비스성능추정불가. 롤백은후보미적용상태라운영에필요없다. 새연구폴더는감사이력으로보존하고실제로발생한첫추론기록을삭제해미사용사진인것처럼재사용하지않는다. 모델을새사진오류에맞춰재학습하지않는다.
