# Codex push 승인 규칙 비교

`check_push_rules.py`는 **현재 파일만 넣었을 때**와 **현재 파일에 제안 파일을 함께 넣었을 때**의 Codex 판정을 18개 명령형으로 비교한다. 검사기는 두 파일의 임시 사본만 Codex CLI에 전달하며, Git 명령형은 판정에 쓰는 인자로만 전달한다. `미일치`는 제공한 파일에서 일치한 규칙이 없다는 뜻이다.

저장소 루트에서 실행한다. Codex CLI 0.164.0과 Python 3에서 검증했다.

```sh
task_dir=tools/diagnostics/codex-push-rule-20261128
python3 "$task_dir/check_push_rules.py" \
  --rules "$HOME/.codex/rules/default.rules" \
  --candidate "$task_dir/proposed.rules"
python3 "$task_dir/test_check_push_rules.py"
```

종료 코드 0은 필수 5행과 보존 6행의 통과를 뜻한다. 관찰 7행은 제한 규칙에 일치하면 ‘일치’, 미일치하거나 `allow`면 ‘한계’로 표시한다. 어느 행이든 CLI 실패나 출력 해석 실패가 있으면 종료 코드는 0이 아니다.

## 사용자가 직접 적용하고 확인하기

위 비교에서 종료 코드 0을 확인한 뒤, 사용자 규칙 디렉터리에 **새 파일**로 설치한다. 아래 명령은 같은 이름의 기존 파일을 덮어쓰지 않는다.

```sh
task_dir=tools/diagnostics/codex-push-rule-20261128
proposal_path="$HOME/.codex/rules/codex-push-rule-20261128.rules"
(set -C; cat "$task_dir/proposed.rules" > "$proposal_path")
```

현재 `default.rules`의 기존 `allow`는 그대로 둔다. 두 규칙에 모두 일치하면 `prompt`가 `allow`보다 우선하며, 변경안과 무관한 명령에는 해당 `allow`가 계속 작동한다. 공식 문서는 Codex를 재시작하면 활성 설정 계층의 `rules/` 파일을 읽는다고 설명한다. [OpenAI Codex 규칙 문서](https://learn.chatgpt.com/docs/agent-configuration/rules)

재시작한 뒤 설치한 파일이 제안과 같은지 확인하고, 설치 파일을 대상으로 비교를 다시 실행한다.

```sh
task_dir=tools/diagnostics/codex-push-rule-20261128
proposal_path="$HOME/.codex/rules/codex-push-rule-20261128.rules"
cmp "$task_dir/proposed.rules" "$proposal_path" &&
  python3 "$task_dir/check_push_rules.py" \
    --rules "$HOME/.codex/rules/default.rules" \
    --candidate "$proposal_path"
```

이 명령은 두 파일을 명시적으로 지정한 오프라인 검증이다. 이번 작업에서는 현재 앱이 새 파일을 로딩하는지, 재시작 효과, 실제 승인창 표시를 확인하지 않았다. 로컬 Codex CLI의 판정은 관리형 환경이나 실행 하네스의 추가 규칙과 다를 수 있다.

## 롤백

설치본이 제안 파일과 일치할 때 그 파일만 삭제하고 Codex를 재시작한다. 설치본에 사용자 편집이 섞여 있으면 아래 명령은 삭제를 건너뛴다.

```sh
task_dir=tools/diagnostics/codex-push-rule-20261128
proposal_path="$HOME/.codex/rules/codex-push-rule-20261128.rules"
cmp "$task_dir/proposed.rules" "$proposal_path" && rm -- "$proposal_path"
```

## 확인한 범위

제안은 `git push`와 `./develop -- git push`의 토큰 접두사에만 적용된다. 관찰표의 7개 변형은 이번 검사기에서 모두 한계로 나왔다. 셸 래퍼 처리, 다른 Git 실행 경로, 다른 도구를 포함한 실제 실행 차단 여부는 이 판정으로 확인할 수 없다. 규칙 적용 후 두 접두사에 일치하는 Codex 명령에는 추가 승인이 요청될 수 있다. [검증 보고서](report.html)
