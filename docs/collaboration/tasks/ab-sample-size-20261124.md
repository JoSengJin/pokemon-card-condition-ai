# 독립 A/B 시험 표본 수 계산 도구와 시험 규칙 (2026-11-24)

task_id: ab-sample-size-20261124
owner: Claude Opus 5.5 (하위 에이전트), 검토 Claude(관리자)
status: assigned
base_sha: 이 문서를 추가한 커밋(부모 18825ee4e779fd4f279280a98898a7b85cbbe160)
branch: claude/ab-sample-size-20261124
goal: 시험 전에 필요한 카드 수와 통과 확률을 정확 합산으로 출력하고, 결과를 보기 전 고정할 시험 규칙을 문서로 둔다. 시험 실행 도구·학습·추론·채택 판정 없음.
allowed_files:
- tools/diagnostics/ab-sample-size-20261124/size.py
- tests/test_ab_sample_size.py
- docs/collaboration/plans/ab-independent-test-rules-20261124.md
forbidden_files: 위 3개 밖 전부(이 계약 포함), 라벨·점수·artifacts 자료, 봉인 468장·독립 350장
contract: 표준 라이브러리, 읽기 전용, JSON 표준 출력, 판정 문구 없음, 종료 코드 0/2. 설계: Fable 5.2 독립 2안(정확 계산·시뮬레이션) 대조 뒤 심판 1회. FINAL.md SHA256 edf0034d841c0b06bd5c160c6f17451617ee39fe1cfdce41e8d4c4c1e2162f42(Git 제외), 규칙 전문 SHA256 2d05be6181eec15aef634938836fa13ea224e93505324f7864fec66d194e46d6
structure: size.py 함수 0→7, 호출 깊이 ≤4; 테스트 파일 함수 ≤7
checks: 새 테스트 -W error, git diff --check, 허용 파일 대조, 고정값 대조, 관리자 별도 계산 대조
experiment: 없음
handoff: 채팅 보고(통합·push는 별도 승인)
