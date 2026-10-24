# 0.4.51 배치 추론 메모리·실패 경계 검증

## 가설과 범위

상단 CONDITION_ANALYSIS_TODO에 수용기준을 먼저 추가하고 구현했다. 0.4.50의 속도 개선에는 메모리 사용 증가 가능성이 남아 있었다. 선택 진단으로 같은 모델/입력의 할당량을 측정하고, 오류 시 부분 분석이 성공으로 오인되지 않는지 검증한다. 새 학습·라벨 변경·운영 fallback 변경은 없다.

`listing-infer --profile-memory --device mps`가 구역 백본 leaf module 경계의 MPS 텐서/Metal driver 할당량을 샘플링한다. `--batch-views`와 함께 사용할 수 있다. 기본 비활성이다. start 값과 샘플 최대치를 구분하며 진짜 peak·프로세스 RAM·시스템 사용량은 측정하지 않는다. 관찰 모델은 이 구역 백본 진단 범위 밖이다. PyTorch 설치 소스의 current_allocated_memory/driver_allocated_memory 설명을 확인했다: 전자는 텐서, 후자는 캐시 및 MPS 프레임워크 할당도 포함한다.

## 실제 결과

같은 source/checkpoint, MPS15매물/160구역을 각각 별도 CLI 프로세스로 실행했다.

|구역 백본 측정|순차|배치|
|---|---:|---:|
|시작 텐서 bytes|3,797,248|3,797,248|
|시작 driver bytes|8,798,208|8,798,208|
|샘플 최대 텐서 MiB|6.435|16.203|
|샘플 최대 driver MiB|19.750|61.766|
|샘플 수|108,802|21,762|

배치는 0.4.50에서 빨라졌지만 이번 샘플에서도 메모리를 더 사용한다. 작은 수치만으로 장치 여유/운영 안전성을 단정하지 않는다. 모듈 사이 일시적 peak 및 비동기 할당은 놓칠 수 있다. driver 수치에는 캐시가 포함되므로 살아 있는 텐서 메모리와 혼동하지 않는다. 측정 hook의 오버헤드가 있으므로 이번 elapsed로 속도 개선을 다시 주장하지 않는다.

각 프로파일 결과를 0.4.50의 해당 비프로파일 실행과 대조: 모든160구역 점수 차이0, 정상/결함/보류·사유·매물 정책 일치. live 라벨 SHA c61e11649ed52cd86af1b40ee4eafab45bb604f71c4ccfdf64d69b118ebdbf94 유지. 모델/source SHA는 각 JSON에 기록됐고 기존 기준과 일치. actual_calls_saved=0, requires_gemini=true.

산출물: artifacts/memory-profile-20261011/{sequential.json,batched.json,comparison.json}.

## 실패 검증

- 구역 하나를 처리한 뒤 두 번째 구역에서 torch.OutOfMemoryError를 주입했다. 부분 보고서 미생성, 같은 출력 경로로 순차 재실행 성공, 기존 점수와 일치.
- profiler 내부 RuntimeError를 주입해 진단 hook이 모두 제거되고 오류가 전파됨을 확인했다. 성공 시에도 제거된다.
- torch.OutOfMemoryError와 MPS RuntimeError에 대해 CLI stdout 성공 결과 없음·stderr requires_gemini=true·exit1 확인.
- CPU에 MPS 메모리 진단을 요청하면 수치 조작 없이 거부하고 보고서를 저장하지 않는다.

실제 장치의 메모리를 고의로 소진하지 않았다. OOM 이후 실제 장치 복구 능력은 이 주입 검사로 증명되지 않는다. 자동 OOM 재시도/순차 전환을 추가하지 않았으며 호출자가 오류를 보고 기존 fallback을 유지해야 한다. 독립 최종평가 자료 없음 상태는 그대로다.

## 변경 파일과 diff

- card_condition/inference_memory.py 신규: context manager 기반 선택 진단·할당량 분리·sample 한계·성공/오류 hook 정리.
- card_condition/listing_inference.py: profile_memory 선택 인자, 구역 추론에만 진단 context 적용, 결과 별도 필드 추가. 기본 경로·마스킹·정답 불변.
- card_condition/cli.py: --profile-memory.
- tests/test_inference_memory.py 신규: 샘플값·출력 불변·정리·CPU 거부·CLI 오류 계약.
- tests/test_listing_inference.py: 부분 추론 OOM 미저장·같은 경로 순차 재실행·CPU profile 거부.
- pyproject.toml:0.4.51. README.md:사용법·한계·오류 후 재실행 안내.
- 본 보고서·메모리 JSON3개·소비 프로젝트 CONDITION_ANALYSIS_TODO.md:수용기준/실행 기록.

## 최종 검사

전체113테스트 통과. 메모리 helper/CLI3테스트 별도 통과, 실제 순차·배치 CLI 실행 및 source/model SHA 대조 통과. 0.4.51 wheel의 Python/HTML43파일이 현재 소스와 byte 일치. 실제 OOM·CPU/RSS·운영 동시 부하는 검증하지 않았다.

## 리스크·롤백

프로파일링은 느려질 수 있고 관찰 모델/프로세스 전체/진짜 peak/동시 부하는 측정하지 않는다. 기본 추론 및 운영 소비 코드/DB/라벨 UI는 변경하지 않았다. 즉시 복귀는 --profile-memory 생략, 배치도 끄려면 --batch-views 생략. 소스는 .backups/memory-profile-0451의 5파일을 복원하고 신규 inference_memory.py와 test_inference_memory.py를 제거하되 후속 수정이 있으면 이번 diff만 제거한다. 데이터/모델 복원은 필요 없다.

에튜: 속도가 빨라져도 메모리를 더 쓸 수 있다. tensor 할당, 캐시 포함 driver 할당, 실제 peak를 구분해야 배포 가능한지 판단할 수 있다.
