import path from 'node:path';
import { scanArgs, codexLoginIsChatgpt } from './nocharge.ts';
import type { TaskInputT } from './contract.ts';
import type { PairConfig } from './config.ts';
import type { Probe } from './adapterProbe.ts';

export interface LaunchPlan { command: string; args: string[]; display: string[]; permission: string }

export function mockPlan(task: TaskInputT, cfg: PairConfig): LaunchPlan {
  const script = path.join(cfg.toolRoot, 'mock', 'mock-agent.mjs');
  const args = [script, '--scenario', task.mockScenario, '--task', task.taskId, '--allowed', task.allowedFiles[0], '--contract', `docs/collaboration/tasks/${task.taskId}.md`];
  return {
    command: process.execPath, args, display: ['node', 'mock/mock-agent.mjs', ...args.slice(1)],
    permission: 'mock: 현재 사용자 권한으로 실행. 허용 파일은 사후 diff 검사로만 확인하며 실행 중 쓰기를 막지 않음. 모델 요청 없음.',
  };
}

export const CLAUDE_ALLOWED_TOOLS = ['Read', 'Edit', 'Write', 'Bash(git status *)', 'Bash(git diff *)', 'Bash(git log *)', 'Bash(git add *)', 'Bash(git commit *)',
  // 읽기 전용 탐색과 단위 테스트. 복합 명령(; | &&)은 조각마다 허용돼야 하므로 head/grep 등도 포함한다.
  'Bash(ls *)', 'Bash(cat *)', 'Bash(head *)', 'Bash(tail *)', 'Bash(grep *)', 'Bash(wc *)',
  'Bash(.venv/bin/python -m unittest *)', 'Bash(.venv/bin/python -m pytest *)', 'Bash(.venv/bin/python --version)'];

export function agentPrompt(task: Pick<TaskInputT, 'taskId' | 'goal'>) {
  // 긴 지시는 커밋된 계약 파일에 있다. CLI 인자에는 계약 경로만 넘겨 인자 길이 제한을 피한다.
  return `작업 계약 docs/collaboration/tasks/${task.taskId}.md 를 읽고 그대로 수행하세요. 계약 파일은 수정하지 마세요. 목표: ${task.goal}`;
}

export function realPlan(task: TaskInputT, p: Probe, cfg: PairConfig, startPrompt?: string): LaunchPlan | { refused: string } {
  if (!cfg.allowRealModelCalls) return { refused: '실제 모델 호출은 별도 승인 작업입니다(config.allowRealModelCalls=false).' };
  if (!cfg.confirmedSubscriptionAuth) return { refused: '무과금 가드: CLI가 구독 로그인으로 동작하고 추가 크레딧이 꺼져 있음을 확인했다는 표시가 없음(config.confirmedSubscriptionAuth=false).' };
  if (!p.installed || !p.binary) return { refused: `${task.agent} CLI 미설치: ${p.note}` };
  if (p.missingFlags.length) return { refused: `--help에서 확인되지 않은 옵션: ${p.missingFlags.join(', ')}` };
  if (task.agent === 'codex' && !codexLoginIsChatgpt(p.loginStatus)) return { refused: '무과금 가드: Codex ChatGPT 구독 로그인이 확인되지 않음 — 실행하지 않음' };
  const prompt = startPrompt || agentPrompt(task);
  let plan: LaunchPlan;
  if (task.agent === 'codex') {
    // exec/--cd/--sandbox 이름은 --help로 확인한다. 값(workspace-write)은 실제 CLI에서 별도 확인 필요.
    const stream = cfg.streamOutput && p.stream === true; // 줄 단위 이벤트 출력(실시간 로그용). 옵션이 확인되지 않으면 텍스트 모드
    const args = ['exec', ...(stream ? ['--json'] : []), '--cd', task.worktree, '--sandbox', 'workspace-write', prompt];
    plan = { command: p.binary, args, display: [p.binary, ...args.slice(0, -1), '<prompt>'],
      permission: 'codex --sandbox workspace-write(값 미검증): worktree 쓰기 허용. 허용 파일 단위 제한은 아님(사후 검사).' };
  } else {
    // --print/--permission-mode(acceptEdits)/--allowedTools는 Claude Code 문서의 옵션이다. --bare는 구독 로그인을 쓰지 않으므로 쓰지 않는다.
    // --allowedTools는 값을 여러 개 받으므로 띄어 쓰면 뒤의 프롬프트까지 도구로 삼킨다(실제 CLI에서 재현). `=`로 붙여 한 값으로 넘긴다.
    const stream = cfg.streamOutput && p.stream === true; // stream-json은 --print에서 --verbose와 함께 쓴다
    const args = ['--print', ...(stream ? ['--output-format=stream-json', '--verbose'] : []), '--permission-mode', 'acceptEdits', `--allowedTools=${CLAUDE_ALLOWED_TOOLS.join(',')}`, prompt];
    plan = { command: p.binary, args, display: [p.binary, ...args.slice(0, -1), '<prompt>'],
      permission: `claude --permission-mode acceptEdits + --allowedTools(${CLAUDE_ALLOWED_TOOLS.length}개): 편집 자동 승인, git 커밋·읽기 전용 탐색·pytest만 허용. 허용 파일 단위 제한은 아님(사후 검사).` };
  }
  const risks = scanArgs(plan.args);
  if (risks.length) return { refused: `무과금 가드: ${risks.map((r) => r.message).join('; ')}` };
  return plan;
}
