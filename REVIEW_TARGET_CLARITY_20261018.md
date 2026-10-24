# 검토 대상 위치 명확화 · 2026-10-18

## 결과

사용자의 “모서리에 화이트닝 처럼 하얀점 결함 있어”를 현재표시photo10의유일하게보이는좌하단모서리손상1로별도보존했다. 실제점좌표는제공되지않아만들지않았다. 요청했던곧은하단엣지구간정답은여전히null이며모서리답변을엣지1이나정상0으로바꾸지않았다. photo6으로라벨을자동전달하지않았다.

원본전체사진에확인구간표시가없어다른위치를대답할수있는문제가있었다. 공용원본검토도구는별도context.png에주황A상자만추가한다. A는정상/결함예측이아닌위치안내다. source.png와native.png픽셀은그대로보존한다.

## 변경 파일·핵심 diff

- `card_condition/region_review.py`: 원본을복사한context.png에정확한crop경계A표시. 기본전체사진표시를context로변경하고표시없는원본링크는유지. 모델·라벨생성없음.
- `tests/test_region_review.py`: context좌표일치·원본/crop픽셀불변·예측표시아님검사1개추가, 기존검사포함4개통과.
- `artifacts/clean-edge-intake2-20261018/eevee-closeup-bottom-review/human-corner-observation.json`: 사용자원문·모서리손상1·엣지미확인·좌표없음·학습0.
- `artifacts/review-target-clarity-20261018/`: 변경전소스백업·실제CLI출력·검증·HTML.
- `REVIEW_TARGET_CLARITY_20261018.md`, 소비프로젝트TODO: 근거·의존기록.

## 검증·성능

원본JPEG를EXIF적용후PNG로변환한픽셀과source.png일치, exact pixelbox[752,1208,1008,1272]의nativePNG도직접crop과일치. context상자가같은pixelbox임검증. 공용원본검토테스트4개통과. 원래70행JSONL SHA불변. 이번모델추론/학습0이며정확도향상을주장하지않는다. 마지막개발평가누락0/4·오탐5/22·사람점누락0/4는이전결과다.

## 리스크·롤백

주황상자를결함표시로오해하지않도록문구로구분했다. 사진에정밀좌표없는모서리판단은국소점지도학습에직접쓸수없다. 부분사진사용허용도아직사용자답변이없어학습에넣지않았다. 운영모델/Gemini/OpenCV/소비API변경0. 원복은source-before/region_review.py와test_region_review.py를각원래경로로복사하면되며기존1:1도구는유지된다. 사람관찰기록은삭제하지않는다.

## 남은 사용자 결정

처음온전한뒷면만사용하라는조건이있었으므로,온전한뒷면이확보된매물의부분사진을보조국소학습에도허용할지답변전보류한다. 모서리결함·완료된판독불가구간은다시질문하지않는다.
