task_id: pilot-short-write-20261026
owner: Codex
status: integrated
base_sha: be3d0b86c8e00d666f9f1ccec5be8916c3790874
branch: codex/pilot-short-write-20261026
goal: F2 usage로그의os.write가짧게쓰는경우기록성공/요청성공/warm완료로계수되지않게한다.
allowed_files:
- card_condition/pilot_record.py
- tests/test_pilot_short_write.py
- docs/collaboration/tasks/pilot-short-write-20261026.md
- docs/collaboration/reports/pilot-short-write-20261026.md
- ignored artifacts/pilot-short-write-20261026/index.html
forbidden_files: 나머지소스/원본/라벨/모델/기존계측·실험/기준·진척/소비서비스/Claude소유파일
contract:
- 기존singleO_APPEND write와fsync/close를유지하고반환바이트수가line길이와다르면OSError로요청을실패시킨다. 부분입력을자동재시도/재작성/truncate하지않는다(다른동시쓰기훼손금지).
- finish는부분로그쓰기실패시completed/warm을증가시키지않는다. CLI는기존stderrJSON·exit1·stdoutempty로실패하며성공예측을내보내지않는다. 손상로그는기존strictJSONL요약에서거절한다.
- 정상전체쓰기의로그스키마/시간/지표/집계는불변이다. API키·실사진·사람정답·과거로그에접근하지않는다.
structure: pilot_record함수7→7, 테스트파일<=7함수, 호출경로추가없음.
checks: 실제부분prefix쓰기/zero쓰기/정상line/fsync·close/완료계수/CLI실패 합성회귀. 수정전실패를기록하고수정후통과, 관련pilot 및기존검사, AST/diff/HTML/main/push. 학습·실사진추론·외부AI0.
experiment: 없음
handoff: 실제검사/부분로그보존의운영리스크/롤백/원격상태기록.

완료: main72c7854,85합성회귀PASS/compileall/diff PASS. pilot_record7/검사6함수. 실제로그수정·실사진추론·학습·외부AI0. 손상로그보존과운영감사의존/롤백/HTML은 reports/pilot-short-write-20261026.md.
