import fs from 'node:fs';
import { probe } from './adapters.ts';
import { effectiveGroups } from './contract.ts';
import { UserError } from './errors.ts';
import type { Executor, Task } from './executor.ts';

export function logTail(ex: Executor, execId: string, from = 0, max = 64_000) {
  const execution = ex.state.executions[execId];
  if (!execution) throw new UserError('실행 없음');
  try {
    const size = fs.statSync(execution.logPath).size;
    const start = Math.max(from, size - max);
    const fd = fs.openSync(execution.logPath, 'r'), buffer = Buffer.alloc(size - start);
    fs.readSync(fd, buffer, 0, buffer.length, start); fs.closeSync(fd);
    return { text: buffer.toString(), next: size };
  } catch { return { text: '', next: from }; }
}

export async function refreshProbes(ex: Executor) {
  ex.probes.codex = await probe('codex', ex.cfg);
  ex.probes.claude = await probe('claude', ex.cfg);
  return ex.probes;
}

export function groupsOf(task: Task) { return effectiveGroups(task); }

export function turnOf(t: Task): { who: 'user' | 'implementer' | 'main' | 'tool'; agent?: 'codex' | 'claude'; label: string; next: string } {
    const impl = { who: 'implementer' as const, agent: t.agent };
    switch (t.status) {
      case 'assigned': case 'blocked': case 'cancelled': case 'rejected': case 'abandoned': case 'failed':
        return { who: 'user', label: '사용자', next: '시작(또는 사유 확인 후 다시 시작)' };
      case 'manual_working': return { ...impl, label: `${t.agent} 세션에서 작업 중`, next: '에이전트가 끝나면 "작업 완료 — 결과 수집"' };
      case 'starting': case 'running': case 'collecting': case 'cancelling': return { ...impl, label: `${t.agent} 실행 중(도구가 감독)`, next: '종료 확인을 기다림' };
      case 'orphan_running': case 'exit_observed': case 'unknown': return { who: 'user', label: '사용자', next: '재시작 후 상태 확인' };
      case 'review_pending': {
        const h = t.handoff;
        if (!h || h.cancelledAt) return { who: 'user', label: '사용자', next: '작업 테스트·diff 확인 후 "메인에게 인계"' };
        if (h.headSha !== t.result?.headSha) return { who: 'user', label: '사용자', next: '인계 후 코드가 바뀜 — 다시 인계' };
        if (!h.confirmedAt) return { who: 'main', agent: h.to, label: `${h.to} 확인 중`, next: '메인이 확인을 끝내면 "메인 확인 완료"' };
        return { who: 'user', label: '사용자', next: '메인 확인 완료 — 승인 또는 거절' };
      }
      case 'approved': case 'integration_blocked': return { who: 'user', label: '사용자', next: '통합 실행' };
      case 'integrating': return { who: 'tool', label: '도구가 통합 중', next: '완료를 기다림' };
      case 'integrated': return { who: 'user', label: '사용자', next: '푸시 준비' };
      default: return { who: 'user', label: '사용자', next: '상태 확인' };
    }
  }
