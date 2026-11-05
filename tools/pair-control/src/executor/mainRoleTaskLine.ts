import { turnOf } from './executorView.ts';
import type { Task } from './executor.ts';

  export function taskLine(t: Task) {
    const turn = turnOf(t);
    const h = t.handoff && !t.handoff.cancelledAt ? ` · 인계 대상 ${t.handoff.to}${t.handoff.confirmedAt ? '(확인됨)' : '(확인 전)'}` : '';
    return `- \`${t.taskId}\` [${t.agent}/${t.mode}] ${t.status} · 차례: ${turn.label} → ${turn.next}${h}`;
  }
