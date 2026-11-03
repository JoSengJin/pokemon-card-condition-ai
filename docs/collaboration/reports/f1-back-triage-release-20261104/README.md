# F1 릴리스 패키지·연결·롤백 검증 (2026-11-04)

후면 점검 묶음(엣지·모서리·표면·관찰 제한) 릴리스 0.6.0의 고정·설치·장애·복구 검증 기록이다. 점검 우선순위 용도이며 결함·정상 판정이 아니다. 소비 서비스(PokeCollector 등) 연결·배포는 하지 않았다.

## 고정한 것
- 패키지 `pokemon-card-condition` 0.6.0 휠 SHA-256 `4f6a2f471bb014de3b6b5101ef7ab742140622ec6e44ee69c4ad1e6b846e25da`(빌드: `pip wheel . --no-deps --no-build-isolation`).
- 입력 계약 `back-triage-request-v1`(id·side='back'·image·box·box_reviewed=True). 출력은 부분별 ranked/scored/held, `complete=false`, 센터링·앞면은 `unsupported_human_review`.
- 릴리스 manifest `release.json`(SHA-256 `fef9f9c814ee3879da1543528ca356dbeab1c738a4c9cc9d0e78ca72112c85d5`): head 4개·백본 가중치·백본 hub 코드 트리 SHA-256, 패키지 버전. 불일치면 추론 전에 `held`+`fallback=existing_path`(종료코드 2).
  - 엣지 `4b0412c43338…` 모서리 `3dafe0553df7…` 표면 `cb862aa608c0…` 관찰 제한 `e28e655e8317…` 백본 가중치 `b938bf1bc15c…`
- 코드: `card_condition/back_triage_release.py`(함수 4) `back_triage_cli.py`(함수 2), 호출 경로 `main → load_suite/read_release`(최대 2회), 도구 `tools/build_back_triage_release.py`·`tools/back_triage_release_check.py`.

## 검증(실제 실행)
1. 깨끗한 가상환경(`python -m venv`, 저장소 소스 없음)에 휠 설치: `pip install torch==2.14.1 torchvision==0.29.1 pillow==12.3.0 <휠>`(PyPI). 저장소 밖 작업 디렉터리에서 CLI 실행, 장치 cpu.
2. 정상 요청(D1 후면 1장, 사람 확인 상자): 4개 부분 ranked/scored, 저장소 실행(mps) 대비 최대 절대차 4.1e-6.
3. 장애 케이스(모두 정상 판정 없이 held): 사진 없음·깨진 파일·잘못된 상자·앞면·상자 미확인 → 부분별 held, `fallback=existing_path`; 요청 계약 위반 → 종료코드 3; head 파일 변조(표면)·백본 가중치 삭제 → 종료코드 2 `release_unavailable:checksum_mismatch:*`. 결과 `failure-cases-0.6.0.json`.
4. 이전 버전 복구: 0.6.1(버전만 다른 휠·릴리스)로 업그레이드해 정상 실행(0.6.0과 점수 최대차 0.0) → 0.6.0 manifest를 0.6.1 패키지에 쓰면 `package_version_mismatch`로 held → 0.6.0 휠 강제 재설치 후 0.6.0 릴리스로 재실행한 출력이 업그레이드 전 출력과 **완전히 동일**(JSON 일치).
5. 단위 테스트 13개 통과(release·CLI 장애·묶음·엣지 기존 테스트). 비유한 점수 보류는 기존 단위 테스트로만 확인(실제 모델로 비유한 입력을 만들지 못함).

## 한계·미확인
- 0.6.1은 버전 번호만 다른 모의 신버전이라 실제 모델 교체 복구는 아니다(복구 절차 검증용).
- "승인된 소비경로"는 사용자 승인이 필요한 항목이다. 이 검증은 독립 CLI 경로만 다뤘고 소비 서비스 통합은 하지 않았다.
- 같은 장치·같은 라이브러리 버전에서만 재현을 확인했다(cpu vs mps 차 4.1e-6). 다른 하드웨어는 미확인.
- 표면 후보는 D1 미충족 후 보충 시험셋에서 충족한 이력이 있다(§80~§82).

## 롤백
새 파일과 `pyproject.toml`의 버전 0.5.0→0.6.0·스크립트 항목 되돌리기(기존 모듈 변경 없음).
