# 입력 해상도 비교

- 변경: card_condition/data.py, model.py, cli.py. 추가: tests/test_resolution.py.
- train --image-size 448 옵션. 기본 224, 기존 checkpoint에 image_size가 없으면 224로 읽음. 학습과 추론 전처리를 checkpoint로 일치시킴.
- 고정 expanded-20261008.jsonl (학습23/val10/회귀평가3), 동일 backbone/head, seed42, epochs5, MPS.
- 224와 448 모두 최저 val loss epoch3. 각각 0.56518, 0.56133. 작은 차이를 일반 성능 향상으로 해석하지 않음.
- 회귀평가 혼동행렬은 모든 항목에서 동일. 센터링1, 모서리1, 엣지2, 표면1 결함 모두 누락. 평가불가1개를 가능으로 오판.
- 추론 초: 224 [0.370,0.076,0.062], 448 [0.507,0.090,0.096]. 최초 호출 포함 3건 단일 측정이므로 정식 속도 벤치마크 아님.
- 테스트 12개 통과: 448 학습/추론 왕복, 미지정 기존 모델 224 호환, 잘못된 해상도 거부 포함.
- 결론: 기본 해상도 유지, 운영 연결 안 함. Gemini 호출/절감 0건.
- 제한: 카드 경계 검출이나 모서리 타일은 구현하지 않음. 전체 사진 해상도 실험이며 결함 위치 탐지가 아님. 3개는 이미 확인한 회귀셋이므로 새로운 최종평가 필요.

## 다음 라벨 기준
- 앞면과 뒷면 각각: 사진 존재, 평가 가능 여부, 모서리/엣지/표면 결함을 1/0/null로 기록.
- 결함 위치는 사람이 사진에서 확인해 기록. 기존 전체 카드 라벨을 양면으로 복제하지 않는다.
- 카드 테두리를 지정한 뒤 전체+확대 입력을 비교한다. 임의의 사진 모서리를 카드 모서리로 간주하지 않는다.

## 실행
```sh
TORCH_HOME=artifacts/torch-cache .venv/bin/card-condition train data/expanded-20261008.jsonl artifacts/new448.pt --image-size 448 --epochs 5
.venv/bin/card-condition evaluate data/expanded-20261008.jsonl artifacts/new448.pt
```

## 롤백
.backups/step4의 data.py, model.py, cli.py를 card_condition/에 복원하고 tests/test_resolution.py 및 artifacts/resolution448-20261008*를 제거. 원본 라벨과 운영 코드는 변경하지 않음.
