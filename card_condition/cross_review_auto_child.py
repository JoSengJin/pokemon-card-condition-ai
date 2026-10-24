"""Codex child isolation, usage, and safe launch replay helpers."""
import os
import tomllib
from pathlib import Path
from .experiment_record import read


def codex_child_config(root):
    args=['-c','project_doc_max_bytes=0','-c','memories.use_memories=false',
          '-c','memories.generate_memories=false','-c','web_search="disabled"',
          '-c','suppress_unstable_features_warning=true']
    for feature in ('memories', 'shell_tool', 'code_mode', 'apps', 'plugins',
                    'multi_agent', 'skill_search', 'browser_use', 'computer_use', 'image_generation', 'view_image'):
        args += ['--disable', feature]
    config_paths = [Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex'))) / 'config.toml', root / '.codex/config.toml']
    servers = set()
    for config_path in config_paths:
        if config_path.exists():
            config = tomllib.loads(config_path.read_text())
            servers.update(config.get('mcp_servers', {}))
            for profile in config.get('profiles', {}).values():
                servers.update(profile.get('mcp_servers', {}))
    for server in sorted(servers):
        if not server or not server.isascii() or any(not (ch.isalnum() or ch in '_-') for ch in server):
            raise ValueError('Unsupported MCP server name; do not construct an ambiguous override')
        args += ['-c', 'mcp_servers.'+server+'.enabled=false']
    args += ['--enable','code_mode_host','--enable','skip_host_skill_discovery']
    env = {k:v for k,v in os.environ.items() if k not in (
        'POKEMON_CARD_CONDITION_GEMINI_API_KEY','GEMINI_API_KEY','GOOGLE_API_KEY',
        'OPENAI_API_KEY','CODEX_API_KEY','NVIDIA_API_KEY','NEMOTRON_API_KEY','POKEMON_CARD_CONDITION_NVIDIA_API_KEY',
        'CODEX_APP_TOOLS_PIPE_PATH','CODEX_SESSION_ID','CODEX_THREAD_ID')}
    env['CARD_CONDITION_AUTO_CHILD']='1'
    return args,env


def sum_usage(usages, keys):
    return {key: sum(u[key] for u in usages) if usages and all(isinstance(u, dict) and type(u.get(key)) is int for u in usages) else None
            for key in keys}


LAUNCH_BLOCKED = '[codex-launch-blocked]'
MAX_LAUNCH_RETRIES = 3


def launch_not_sent(directory):
    """True only when the app-server provably never received a turn: no model request, no usage."""
    try:
        value = read(directory / 'execution.json')
    except (OSError, ValueError):
        return False
    return (value.get('transport') == 'app-server' and value.get('turn_requests') == 0
            and not value.get('turn_completions') and value.get('usage') is None)


def archive_launch_failure(folder, directory):
    """Move a never-sent attempt out of codex/ so it counts neither as a call nor as unknown usage."""
    target_root = folder / 'superseded-codex'
    target_root.mkdir(exist_ok=True)
    taken = sorted(target_root.glob(directory.name.split('-')[0] + '-*'))
    if len(taken) >= MAX_LAUNCH_RETRIES:
        raise ValueError(LAUNCH_BLOCKED + ' Codex app-server did not start ' + str(len(taken)) + ' times; fix the environment first')
    target = target_root / (directory.name + '-launch-failure-' + str(len(taken) + 1))
    directory.rename(target)
    return target


def stored_phase_one_correction(folder, phase, payload, directory):
    """A review folder holds one verify and one correction; replay the stored pre-critique correction.

    Its error list can differ from today's only because validators changed, which must not orphan the
    already-paid response (the digest would differ and the one-correction cap would otherwise block it).
    """
    if phase != 'correct' or 'correction' not in payload or 'critiques' in payload:
        return None
    stored = [p for p in (folder / 'codex').glob('correct-*/call.json') if p.parent != directory]
    if len(stored) != 1:
        return None
    try:
        entry, previous = read(stored[0]), read(stored[0].parent / 'input.json')
    except (OSError, ValueError):
        return None
    if entry.get('status') != 'complete' or 'correction' not in previous or 'critiques' in previous:
        return None
    return dict(entry, directory=str(stored[0].parent))


def launch_failure_detail(directory):
    if launch_not_sent(directory):
        return (' ' + LAUNCH_BLOCKED + ' codex app-server가 모델 요청 전에 시작되지 못했습니다(모델 호출·토큰 사용 0). '
                'Codex 샌드박스 밖의 일반 터미널(또는 권한 상승 실행)에서 ./review --auto를 다시 실행하면 저장 상태에서 이어갑니다.')
    return ''
