"""봉인 경로 판정(읽기 없음). Supervisor처럼 sandbox 밖에서 도는 코드가 파일을 열기 전에 봉인 목록과 대조하는 데 쓴다(2026-11-28 신뢰 경계 조사).

목록·실제 경로 해석은 claude_perm.sealed_paths 그대로다(목록이 없거나 링크·형식 오류면 ValueError = fail-closed). 위치 비교는 stage_inputs와 같이
(장치, inode)로 한다(대소문자·NFD 이름 우회 방지). 호출 깊이: load·under 모두 claude_perm의 말단(sealed_paths·_ids)을 부른다(1).
"""
import os

from . import claude_perm


def load(bases):
    """bases 아래 봉인 경로(claude_perm.sealed_paths)의 (장치, inode) 집합. 목록 오류는 ValueError."""
    return claude_perm._ids(claude_perm.sealed_paths(bases))


def under(path, sealed):
    """path의 실제 경로나 그 상위 폴더가 load가 돌려준 sealed 집합에 있는가. 파일을 열지 않고 stat만 한다(없는 경로는 상위 폴더만 본다)."""
    chain = [os.path.realpath(path)]
    while os.path.dirname(chain[-1]) != chain[-1]:
        chain.append(os.path.dirname(chain[-1]))
    return bool(claude_perm._ids(chain) & sealed)
