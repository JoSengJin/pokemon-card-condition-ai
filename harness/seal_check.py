"""봉인 경로 판정(읽기 없음). Supervisor처럼 sandbox 밖에서 도는 코드가 파일을 열기 전에 봉인 목록과 대조하는 데 쓴다(2026-11-28 신뢰 경계 조사).

목록·실제 경로 해석은 stage_inputs와 같이 claude_perm.sealed_paths + outside_roots(저장소 밖 봉인 사본 루트, 2026-11-29 독립 검증 D1) 그대로다
(목록이 없거나 링크·형식 오류·중첩 worktree면 ValueError = fail-closed). 위치 비교는 (장치, inode)로 한다(대소문자·NFD 이름 우회 방지).
호출 깊이: load·under 모두 claude_perm의 말단(sealed_paths·outside_roots·_ids)을 부른다(1).
"""
import os

from . import claude_perm


def load(bases):
    """bases 아래 봉인 경로(claude_perm.sealed_paths)와 저장소 밖 봉인 루트(claude_perm.outside_roots)의 (장치, inode) 집합. 목록 오류는 ValueError."""
    return claude_perm._ids(claude_perm.sealed_paths(bases) + claude_perm.outside_roots(bases))


def under(path, sealed):
    """path의 실제 경로나 그 상위 폴더가 load가 돌려준 sealed 집합에 있는가. 파일을 열지 않고 stat만 한다(없는 경로는 상위 폴더만 본다). 봉인이 아닌 일반 파일이 하드 링크(nlink>1)면 ValueError."""
    chain = [os.path.realpath(path)]
    while os.path.dirname(chain[-1]) != chain[-1]:
        chain.append(os.path.dirname(chain[-1]))
    if claude_perm._ids(chain) & sealed:
        return True
    if os.path.isfile(chain[0]) and os.stat(chain[0]).st_nlink > 1:  # 하드 링크는 봉인 파일의 다른 이름일 수 있다(stage_inputs F11과 같은 처리)
        raise ValueError("하드 링크 파일은 봉인 여부를 판별할 수 없다: %s" % path)
    return False
