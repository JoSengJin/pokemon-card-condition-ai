// CLI 어댑터. mock은 로컬 스크립트, 실제 codex/claude는 설치·--help로 확인한 옵션만 사용한다.
// 실제 모델 요청은 config.allowRealModelCalls=true와 필수 옵션 확인이 모두 있어야 시작한다(기본 차단).
import fs from 'node:fs';
import path from 'node:path';
import { run } from './git.ts';
import type { Agent, TaskInputT } from './contract.ts';
import type { PairConfig } from './config.ts';
import { codexLoginIsChatgpt, scanArgs, scanClaudeSettings, scanCodexConfig, scanEnv, type ChargeRisk } from './nocharge.ts';

export interface Probe {
  agent: Agent;
  installed: boolean;
  binary: string | null;
  version: string | null;
  verifiedFlags: string[];
  missingFlags: string[];
  note: string;
  checkedAt: string;
  /** 줄 단위 이벤트 출력 옵션(claude --output-format·--verbose, codex --json)이 --help에서 확인됨 */
  stream?: boolean;
  /** codex만: `codex login status` 출력 한 줄(모델 요청 없음). */
  loginStatus?: string;
}

export interface LaunchPlan { command: string; args: string[]; display: string[]; permission: string }

/** 실제 실행에 필요하다고 가정하는 옵션. 설치된 CLI의 --help에서 실제로 보여야 사용한다. */
const REQUIRED: Record<'codex' | 'claude', { help: string[]; flags: string[] }> = {
  codex: { help: ['exec', '--help'], flags: ['--cd', '--sandbox'] },
  claude: { help: ['--help'], flags: ['--print', '--permission-mode', '--allowedTools'] },
};

const STREAM_FLAGS = { codex: ['--json'], claude: ['--output-format', '--verbose'] };

function findOnPath(name: string): string | null {
  for (const dir of (process.env.PATH ?? '').split(path.delimiter)) {
    const p = path.join(dir, name);
    try { fs.accessSync(p, fs.constants.X_OK); return p; } catch { /* next */ }
  }
  return null;
}

export async function probe(agent: 'codex' | 'claude', cfg: PairConfig): Promise<Probe> {
  const checkedAt = new Date().toISOString();
  const binary = cfg.cli[agent] || findOnPath(agent);
  const base = { agent, binary, checkedAt, verifiedFlags: [] as string[], missingFlags: REQUIRED[agent].flags };
  if (!binary) return { ...base, installed: false, version: null, note: 'PATH/설정에서 실행 파일을 찾지 못함(미설치)' };
  const ver = await run(binary, ['--version'], cfg.toolRoot, 10_000);
  if (ver.code !== 0) return { ...base, installed: false, version: null, note: `--version 실행 실패(code ${ver.code}): ${ver.stderr.slice(0, 120)}` };
  const help = await run(binary, REQUIRED[agent].help, cfg.toolRoot, 10_000);
  const text = help.stdout + help.stderr;
  const seen = (f: string) => new RegExp(`(^|[\\s,])${f.replace(/-/g, '\\-')}(?=[\\s=,]|$)`, 'm').test(text);
  const verified = REQUIRED[agent].flags.filter(seen);
  return {
    ...base, installed: true, version: ver.stdout.trim().slice(0, 80), verifiedFlags: verified,
    missingFlags: REQUIRED[agent].flags.filter((f) => !verified.includes(f)), stream: STREAM_FLAGS[agent].every(seen),
    note: help.code === 0 ? '--help 확인 완료(모델 요청 없음)' : `--help 실패(code ${help.code})`,
    ...(agent === 'codex' ? { loginStatus: await codexLoginStatus(binary, cfg) } : {}),
  };
}

async function codexLoginStatus(binary: string, cfg: PairConfig): Promise<string> {
  const r = await run(binary, ['login', 'status'], cfg.toolRoot, 10_000);
  return (r.stdout + r.stderr).trim().split('\n')[0].slice(0, 120);
}

export function mockPlan(task: TaskInputT, cfg: PairConfig): LaunchPlan {
  const script = path.join(cfg.toolRoot, 'mock', 'mock-agent.mjs');
  const args = [script, '--scenario', task.mockScenario, '--task', task.taskId, '--allowed', task.allowedFiles[0], '--contract', `docs/collaboration/tasks/${task.taskId}.md`];
  return {
    command: process.execPath, args, display: ['node', 'mock/mock-agent.mjs', ...args.slice(1)],
    permission: 'mock: 현재 사용자 권한으로 실행. 허용 파일은 사후 diff 검사로만 확인하며 실행 중 쓰기를 막지 않음. 모델 요청 없음.',
  };
}

/** 에이전트가 계약 범위에서 커밋까지 할 수 있게 허용하는 도구. 그 밖의 Bash는 -p 모드에서 자동 거부된다(docs: Manual mode). */
export const CLAUDE_ALLOWED_TOOLS = ['Read', 'Edit', 'Write', 'Bash(git status *)', 'Bash(git diff *)', 'Bash(git log *)', 'Bash(git add *)', 'Bash(git commit *)',
  // 읽기 전용 탐색과 단위 테스트. 복합 명령(; | &&)은 조각마다 허용돼야 하므로 head/grep 등도 포함한다.
  'Bash(ls *)', 'Bash(cat *)', 'Bash(head *)', 'Bash(tail *)', 'Bash(grep *)', 'Bash(wc *)',
  'Bash(.venv/bin/python -m pytest *)', 'Bash(.venv/bin/python --version)'];

export function agentPrompt(task: Pick<TaskInputT, 'taskId' | 'goal'>) {
  // 긴 지시는 커밋된 계약 파일에 있다. CLI 인자에는 계약 경로만 넘겨 인자 길이 제한을 피한다.
  return `작업 계약 docs/collaboration/tasks/${task.taskId}.md 를 읽고 그대로 수행하세요. 계약 파일은 수정하지 마세요. 목표: ${task.goal}`;
}

/** 시작 전 무과금 검사. 하나라도 있으면 실제 실행을 시작하지 않는다. */
export function chargeRisks(agent: 'codex' | 'claude', cfg: PairConfig, ctx: { worktree?: string; env?: NodeJS.ProcessEnv; args?: string[] } = {}): ChargeRisk[] {
  const home = cfg.homeDir;
  return [
    ...scanEnv(ctx.env ?? process.env),
    ...(agent === 'claude' ? scanClaudeSettings({ worktree: ctx.worktree, env: ctx.env, home }) : scanCodexConfig({ env: ctx.env, home })),
    ...(ctx.args ? scanArgs(ctx.args) : []),
  ];
}

/** startPrompt는 실행기가 만든 시작 프롬프트(AGENTS.md 읽기·허용 파일·진행 방식 포함). 없으면 계약 경로만 넘기는 짧은 지시를 쓴다. */
export function realPlan(task: TaskInputT, p: Probe, cfg: PairConfig, startPrompt?: string): LaunchPlan | { refused: string } {
  if (!cfg.allowRealModelCalls) return { refused: '실제 모델 호출은 별도 승인 작업입니다(config.allowRealModelCalls=false).' };
  if (!cfg.confirmedSubscriptionAuth) return { refused: '무과금 가드: CLI가 구독 로그인으로 동작하고 추가 크레딧이 꺼져 있음을 확인했다는 표시가 없음(config.confirmedSubscriptionAuth=false).' };
  if (!p.installed || !p.binary) return { refused: `${task.agent} CLI 미설치: ${p.note}` };
  if (p.missingFlags.length) return { refused: `--help에서 확인되지 않은 옵션: ${p.missingFlags.join(', ')}` };
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

export type BlockerCode = 'cli_missing' | 'cli_error' | 'flags_unverified' | 'real_calls_disabled' | 'subscription_unconfirmed' | 'not_checked'
  | 'paid_env' | 'login_not_chatgpt' | 'settings_api_key' | 'settings_login_method' | 'settings_unreadable' | 'forbidden_flag' | 'limit_hit';
export interface Blocker { code: BlockerCode; message: string; fix: string }

/** 실제 모드 실행 가능 여부와 차단 원인. 원인마다 해결 조건을 함께 돌려준다(모델 요청 없이 판단). */
export function realReadiness(agent: 'codex' | 'claude', p: Probe | undefined, cfg: PairConfig, ctx: { worktree?: string; limit?: { detail: string } | null; env?: NodeJS.ProcessEnv } = {}): { available: boolean; blockers: Blocker[] } {
  const b: Blocker[] = [];
  if (!p) b.push({ code: 'not_checked', message: 'CLI 확인 전', fix: '"CLI 다시 확인"을 누르세요(--version/--help만 실행)' });
  else if (!p.installed && !p.binary) b.push({ code: 'cli_missing', message: `${agent} CLI 미설치`, fix: `${agent} CLI를 설치하거나 config.cli.${agent}에 실행 파일 경로를 지정` });
  else if (!p.installed) b.push({ code: 'cli_error', message: `${agent} 실행 실패: ${p.note}`, fix: '터미널에서 --version이 동작하는지 확인' });
  else if (p.missingFlags.length) b.push({ code: 'flags_unverified', message: `--help에서 확인되지 않은 옵션: ${p.missingFlags.join(', ')}`, fix: 'CLI 버전을 확인하고 어댑터 옵션을 갱신(별도 작업)' });
  if (agent === 'codex' && p?.installed && !codexLoginIsChatgpt(p.loginStatus)) {
    b.push({ code: 'login_not_chatgpt', message: `codex 로그인이 ChatGPT 구독으로 확인되지 않음(${p.loginStatus || '출력 없음'})`, fix: '`codex login`으로 ChatGPT 로그인(API 키 로그인은 API 요금)' });
  }
  if (!cfg.allowRealModelCalls) b.push({ code: 'real_calls_disabled', message: '실제 모델 호출 차단(기본값)', fix: '별도 승인 작업에서 config.allowRealModelCalls=true' });
  if (!cfg.confirmedSubscriptionAuth) b.push({ code: 'subscription_unconfirmed', message: '구독 로그인·추가 크레딧 꺼짐 미확인', fix: '계정에서 구독 로그인(API 키 아님)과 추가 사용 크레딧이 꺼져 있음을 직접 확인한 뒤 config.confirmedSubscriptionAuth=true' });
  for (const r of chargeRisks(agent, cfg, { worktree: ctx.worktree, env: ctx.env })) b.push({ code: r.code, message: r.message, fix: r.fix });
  if (ctx.limit) b.push({ code: 'limit_hit', message: `구독 사용 한도 도달 상태: ${ctx.limit.detail}`, fix: '한도가 풀린 것을 확인한 뒤 "한도 해제 확인"(재시도·크레딧 구매는 하지 않음)' });
  return { available: b.length === 0, blockers: b };
}
