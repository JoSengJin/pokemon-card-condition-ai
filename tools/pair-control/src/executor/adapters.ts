// CLI 어댑터. mock은 로컬 스크립트, 실제 codex/claude는 설치·--help로 확인한 옵션만 사용한다.
// 실제 모델 요청은 config.allowRealModelCalls=true와 필수 옵션 확인이 모두 있어야 시작한다(기본 차단).
import fs from 'node:fs';
import path from 'node:path';
import { run } from './git.ts';
import type { Agent, TaskInputT } from './contract.ts';
import type { PairConfig } from './config.ts';

export interface Probe {
  agent: Agent;
  installed: boolean;
  binary: string | null;
  version: string | null;
  verifiedFlags: string[];
  missingFlags: string[];
  note: string;
  checkedAt: string;
}

export interface LaunchPlan { command: string; args: string[]; display: string[]; permission: string }

/** 실제 실행에 필요하다고 가정하는 옵션. 설치된 CLI의 --help에서 실제로 보여야 사용한다. */
const REQUIRED: Record<'codex' | 'claude', { help: string[]; flags: string[] }> = {
  codex: { help: ['exec', '--help'], flags: ['--cd', '--sandbox'] },
  claude: { help: ['--help'], flags: ['--print', '--permission-mode'] },
};

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
  const verified = REQUIRED[agent].flags.filter((f) => new RegExp(`(^|[\\s,])${f.replace(/-/g, '\\-')}(?=[\\s=,]|$)`, 'm').test(text));
  return {
    ...base, installed: true, version: ver.stdout.trim().slice(0, 80), verifiedFlags: verified,
    missingFlags: REQUIRED[agent].flags.filter((f) => !verified.includes(f)),
    note: help.code === 0 ? '--help 확인 완료(모델 요청 없음)' : `--help 실패(code ${help.code})`,
  };
}

export function mockPlan(task: TaskInputT, cfg: PairConfig): LaunchPlan {
  const script = path.join(cfg.toolRoot, 'mock', 'mock-agent.mjs');
  const args = [script, '--scenario', task.mockScenario, '--task', task.taskId, '--allowed', task.allowedFiles[0]];
  return {
    command: process.execPath, args, display: ['node', 'mock/mock-agent.mjs', ...args.slice(1)],
    permission: 'mock: 현재 사용자 권한으로 실행. 허용 파일은 사후 diff 검사로만 확인하며 실행 중 쓰기를 막지 않음. 모델 요청 없음.',
  };
}

export function realPlan(task: TaskInputT, p: Probe, cfg: PairConfig): LaunchPlan | { refused: string } {
  if (!cfg.allowRealModelCalls) return { refused: '실제 모델 호출은 별도 승인 작업입니다(config.allowRealModelCalls=false).' };
  if (!cfg.confirmedSubscriptionAuth) return { refused: '무료 가드: CLI가 기존 구독 로그인으로 동작하는지 미확인(config.confirmedSubscriptionAuth=false). API 과금 전환 방지를 위해 시작하지 않음.' };
  if (!p.installed || !p.binary) return { refused: `${task.agent} CLI 미설치: ${p.note}` };
  if (p.missingFlags.length) return { refused: `--help에서 확인되지 않은 옵션: ${p.missingFlags.join(', ')}` };
  const prompt = `${task.goal}\n\n허용 파일: ${task.allowedFiles.join(', ')}\n${task.prompt}`;
  if (task.agent === 'codex') {
    // 옵션 이름은 --help로 확인하지만 값(workspace-write)은 실제 CLI에서 별도 확인 필요.
    const args = ['exec', '--cd', task.worktree, '--sandbox', 'workspace-write', prompt];
    return { command: p.binary, args, display: [p.binary, ...args.slice(0, -1), '<prompt>'],
      permission: 'codex --sandbox workspace-write(값 미검증): worktree 쓰기 허용. 허용 파일 단위 제한은 아님(사후 검사).' };
  }
  const args = ['--print', '--permission-mode', 'acceptEdits', prompt];
  return { command: p.binary, args, display: [p.binary, ...args.slice(0, -1), '<prompt>'],
    permission: 'claude --permission-mode acceptEdits(값 미검증): 편집 자동 승인. 허용 파일 단위 제한은 아님(사후 검사).' };
}

export interface Blocker { code: 'cli_missing' | 'cli_error' | 'flags_unverified' | 'real_calls_disabled' | 'subscription_unconfirmed' | 'not_checked'; message: string; fix: string }

/** 실제 모드 실행 가능 여부와 차단 원인. 원인마다 해결 조건을 함께 돌려준다(모델 요청 없이 판단). */
export function realReadiness(agent: 'codex' | 'claude', p: Probe | undefined, cfg: PairConfig): { available: boolean; blockers: Blocker[] } {
  const b: Blocker[] = [];
  if (!p) b.push({ code: 'not_checked', message: 'CLI 확인 전', fix: '"CLI 다시 확인"을 누르세요(--version/--help만 실행)' });
  else if (!p.installed && !p.binary) b.push({ code: 'cli_missing', message: `${agent} CLI 미설치`, fix: `${agent} CLI를 설치하거나 config.cli.${agent}에 실행 파일 경로를 지정` });
  else if (!p.installed) b.push({ code: 'cli_error', message: `${agent} 실행 실패: ${p.note}`, fix: '터미널에서 --version이 동작하는지 확인' });
  else if (p.missingFlags.length) b.push({ code: 'flags_unverified', message: `--help에서 확인되지 않은 옵션: ${p.missingFlags.join(', ')}`, fix: 'CLI 버전을 확인하고 어댑터 옵션을 갱신(별도 작업)' });
  if (!cfg.allowRealModelCalls) b.push({ code: 'real_calls_disabled', message: '실제 모델 호출 차단(기본값)', fix: '별도 승인 작업에서 config.allowRealModelCalls=true' });
  if (!cfg.confirmedSubscriptionAuth) b.push({ code: 'subscription_unconfirmed', message: '구독 로그인 사용 여부 미확인', fix: '사용자가 CLI가 API 키가 아닌 기존 구독 로그인임을 확인한 뒤 config.confirmedSubscriptionAuth=true' });
  return { available: b.length === 0, blockers: b };
}
