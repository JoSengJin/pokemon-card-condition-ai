# 데이터 원천 비교표 (2026-10-25)

조사 방법: 공개 페이지와 공개 썸네일만 읽기 전용으로 확인했다(Claude 내장 브라우저, WebFetch). 로그인, 키, 결제, 약관 동의, 다운로드, 스크래핑은 하지 않았다. 표의 "확인"은 이번에 직접 본 값이고, "미확인"은 공개 페이지로 판단할 수 없었던 값이다. 소개 문구만으로 품질을 판정하지 않았다.

## 1. 카드 결함 공개 자료

| 항목 | PokeFrontBackDamage | pokemon-card-damage | Card Grader |
|---|---|---|---|
| 공식 원천 | [universe.roboflow.com/pokemonfyp/pokefrontbackdamage](https://universe.roboflow.com/pokemonfyp/pokefrontbackdamage) | [universe.roboflow.com/rafets-workspace/pokemon-card-damage](https://universe.roboflow.com/rafets-workspace/pokemon-card-damage) | [universe.roboflow.com/kvitteringer/card-grader-rr2yt](https://universe.roboflow.com/kvitteringer/card-grader-rr2yt) |
| 라이선스 표시 | CC BY 4.0 (확인) | CC BY 4.0 (확인) | CC BY 4.0 (확인) |
| 원 사진 권리 | 미확인. 연속 번호 `IMG_xxxx`로 보아 직접 촬영일 가능성이 있으나 근거가 없다. | **위험.** 파일명이 eBay 이미지 이름 형식(`s-l1600 (n)`)이다. 판매자 사진의 권리가 업로더의 CC BY 표시로 해소됐는지 미확인. | 미확인 |
| 버전·수량 | 프로젝트 2,633장. v1(2023-05-08) 4,973장 = train 4,680 / valid 193 / test 100 (확인) | 프로젝트 761장. v6(2026-05-17) 4,393장 = 3,079 / 878 / 436, "No augmentations". v1 671장 (확인). **프로젝트 수와 v6 수가 불일치하며 원인은 미확인.** | 632장, 버전 0, 모델 0 (확인) |
| 증강 | v1: 학습 예제당 출력 2, 상하·좌우 반전, 90° 회전, ±15° 회전, 밝기 ±3% (확인). train 4,680 = 원본 2,340 × 2로 보인다(추정). | v6: 증강 없음 표시 (확인) | 해당 없음(버전 없음) |
| 해상도 | v1 전처리 **Stretch 300×300** (확인). 원본 해상도는 미확인. | v1 640×640 Stretch 표시. v6 크기는 미표시. | 미확인 |
| 색 | **흑백** (공개 썸네일과 관련 보고서 모두 확인) | 컬러 (썸네일 확인) | 미확인 |
| 라벨 정의 | 9클래스: Scratch, Damage, Hole, Corner, Crease, Damaged Corner, Edge Wear, Heavy Wear, Tear. 클래스 정의 문서 없음. | 7클래스: Scratch, stain, Clean, Crease, General_Damage, worn_corner, worn_edge. 정의 문서 없음. | 4클래스: Scratch, Card, Corner Wear, Edge Wear |
| 앞뒤 | 이름에 FrontBack이 있으나 짝 연결 정보는 없음. 첫 화면 표본 12장은 모두 뒷면 (확인) | 앞면과 뒷면 썸네일이 섞여 있음. 짝 연결은 미확인. | 미확인 |
| 실물 구분 | 실물 ID 없음. 같은 뒷면을 연속 촬영한 사진이 다수 (표본 확인) | 실물 ID 없음. 같은 이름의 jpg/`_png.png` 사본이 반복됨 (표본 확인) | 미확인 |
| 중복 | 첫 화면 파일명 50개 중 `IMG_1002`, `IMG_0693`이 2회씩 나옴 (확인) | 동일 이름 사본 반복 (확인) | 미확인 |
| 정상 주석 완전성 | 정상 클래스 없음. 박스가 없는 영역이 정상인지는 근거가 없다. 공개 표본에 박스가 거의 없는 사진이 있으나 누락 여부는 판단 불가. | `Clean` 박스 클래스가 있으나 구역 단위 정상 정답과 같은 뜻인지 미확인. | 정상 클래스 없음 |
| 확인 범위 | 개요·버전 페이지, 첫 화면 썸네일 12장, 파일명 50개 | 개요·버전 페이지, 썸네일 12장 | 개요 페이지 |
| 판단 | **학습 보조 후보.** 평가·정상 대조·실제 결함점으로 승격 불가. 300px 흑백은 미세 표면·엣지 결함을 잃었을 위험이 크다. | 권리·중복 위험이 해소되기 전에는 사용 보류 | 우선순위 최하 |

### 같은 자료를 쓴 연구

[Automatic Trading Card Identification and Grading (Kedar Krishnan 등)](https://kedarkrishnan.com/assets/media/proj_cv.pdf). PDF 본문을 직접 읽어 확인했다.

- 2,633장의 흑백 이미지를 무작위로 70/20/10 분할했다. 전처리는 640×640 stretch다. 실물 단위 분할 여부는 기술돼 있지 않다.
- YOLOv5s 전체 결과(인스턴스 1,519개): P 0.512, R 0.444, mAP50 0.395. 표 4의 클래스별 인스턴스는 Corner 728, Damaged Corner 313, Scratch 294, Crease 100, Damage 37, Edge Wear 30, Heavy Wear 8, Hole 5, Tear 4개다. 이 표가 어느 분할(valid/test)에서 나왔는지는 본문에서 확인하지 못했다.
- 보고서 스스로 "모든 클래스가 배경과 혼동된다"고 적었다. Damaged Corner와 Tear 사이의 혼동도 적었다.
- 해석: 클래스 불균형이 크고, 실물 단위 분리가 확인되지 않는 박스 자료의 한계를 보여 주는 사례다. 측정 단위가 다르므로(박스 IoU 대 구역 판정) **우리 FN/FP와 직접 비교하지 않는다.**

## 2. 방법·사전학습 참고 자료

| 자료 | 라이선스 (확인) | 무엇을 줄이나 | 여전히 필요한 것 | 카드 특유 위험 |
|---|---|---|---|---|
| [PatchCore](https://openaccess.thecvf.com/content/CVPR2022/html/Roth_Towards_Total_Recall_in_Industrial_Anomaly_Detection_CVPR_2022_paper.html) / [코드](https://github.com/amazon-science/patchcore-inspection) | 코드 Apache-2.0. 백본은 ImageNet 사전학습 WideResNet50 | 결함 종류별 박스 라벨 | **사람이 확인한 정상 사진 다양성**과 실제 결함 평가 자료 | 그림·홀로그램·판본·언어 차이와 촬영 조명이 "정상에서 벗어남"으로 잡힌다. 정상 메모리를 판본이나 뒷면 단위로 나눠야 할 수 있다. 2026-10-10 기록과 같은 판단이다. |
| [CutPaste](https://openaccess.thecvf.com/content/CVPR2021/html/Li_CutPaste_Self-Supervised_Learning_for_Anomaly_Detection_and_Localization_CVPR_2021_paper.html) | 논문(코드 라이선스 미확인) | 결함 예시 수집 | 실제 결함 평가 | 잘라 붙인 패치가 카드 인쇄 패턴과 비슷하면 쉬운 지름길 학습이 생긴다. |
| [DRAEM](https://arxiv.org/abs/2108.07610) / [코드](https://github.com/VitjanZ/DRAEM) | 코드 MIT. 이상 원천은 DTD 텍스처(DTD 라이선스는 페이지에 없음) | 결함 예시 수집 | 실제 결함 평가 | 합성 텍스처는 실제 화이트닝이나 미세 긁힘과 모양이 다르다. |
| [Core-set Active Learning](https://arxiv.org/abs/1708.00489) | 논문 | 검토 대상 선별(학습용) | 대표 표집된 시험 | 최종 시험을 모델이 어려워하는 사례로만 채우면 사용 환경을 대표하지 못한다. 시험은 사전 무작위 표집으로 만든다. |
| [MVTec AD](https://www.mvtec.com/research-teaching/datasets/mvtec-ad) | **CC BY-NC-SA 4.0, 상업 사용 금지** | 방법 검증 | 카드 자료 | 상업 경로가 생기면 사용할 수 없다. |
| [VisA](https://github.com/amazon-science/spot-diff) | 데이터 CC BY 4.0, 코드 Apache-2.0. 10,821장(정상 9,621, 이상 1,200), 픽셀 마스크 | 방법 검증·사전학습 | 카드 자료 | 산업 부품 자료라 카드로 옮길 수 있는지는 미검증이다. |
| [CVAT Auto QA](https://docs.cvat.ai/docs/qa-analytics/auto-qa/) / [Consensus](https://docs.cvat.ai/docs/qa-analytics/consensus/) | 문서에 CVAT Online/Enterprise 대상 표시. Community 판에서 쓸 수 있는지는 미확인. | 검수자 품질 관리 방식 참고 | — | 도구는 도입하지 않는다. 기준 예제 비율(문서 제안: 5~15%, 작은 작업은 약 30%)과 복제 판정 후 병합하는 개념만 차용한다. 기존 검토 UI를 재사용한다. |
| [TAG DIG](https://help.taggrading.com/en/articles/6747781-what-is-the-tag-dig-report) / [과정](https://help.taggrading.com/en/articles/10091666-what-are-the-steps-of-tag-s-grading-process) | 재사용 권리 언급 없음 | — | — | photometric stereo 특수 촬영이다. 모든 결함을 표시하는지도 명시가 없다. 휴대폰 사진의 정답으로 옮길 수 없고, 수집하지 않는다. |

## 3. 이전 프로젝트 기록과의 대조

- `CONSULTING_CONSENSUS_20261010.md`: PatchCore는 "정상 뒷면 다양성 확보 후 작은 기준선"으로 판단했고, YOLO와 대형 VLM은 "병목 근거 부족"으로 제외했다. 이번 감사는 이 판단을 뒤집지 않는다. 이번 새 근거는 공개 카드 박스 자료의 해상도, 흑백, 실물 ID 부재, 중복을 직접 확인한 것이다.
- 다른 외부 카드 자료 검토 기록은 저장소의 md/json/py에서 찾지 못했다(`roboflow`, `kaggle`, `mvtec`, `cvat` 등 검색).

## 4. 다운로드가 필요할 때의 다음 행동 명세 (실행하지 않음)

| 대상 | 정확한 대상 | 크기 | 필요한 권한·동의 | 예상 검토 부담 |
|---|---|---|---|---|
| PokeFrontBackDamage | v1 export(COCO JSON 권장, 증강 포함 4,973장). **원본 해상도 2,633장 export가 가능한지 먼저 확인해야 한다.** 증강이 없는 원본이 필요하다. | 미확인(페이지에 용량 표시 없음) | Roboflow 로그인과 API 키(사용자 계정), Roboflow 약관 동의, CC BY 4.0 표기 의무 | 자동: 디코드 SHA와 지각 해시로 중복·연속 촬영 묶음을 추정한다. 사람: 무작위 100장으로 클래스 정의와 누락 박스를 표본 감사한다(제안값). 평가 셀에는 넣지 않는다. |
| pokemon-card-damage | 사용 보류 | — | 원 판매자 사진 권리를 먼저 확인해야 한다 | — |

외부 자료를 학습에 넣는 일은 별도의 단일 가설 실험이다(`./experiment --plan`). 기존 train과 섞을 때는 val·D1 실물과 겹치지 않음을 해시로 증명해야 한다.
