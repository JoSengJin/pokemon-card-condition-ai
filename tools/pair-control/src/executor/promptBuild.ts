import * as G from './git.ts';
import type { Task } from './executor.ts';
import { identitySections, scopeSections, type Ctx } from './promptIdentityScope.ts';
import { deliverySections } from './promptDelivery.ts';

export interface PromptOptions {
  /** 사용자가 자리에 없는 장시간 작업(사람 정답 추정·재요청 금지 문구를 넣는다). */
  unattended?: boolean;
  /** 계약 외에 먼저 읽을 문서(저장소 상대경로). 시작 HEAD에 있는 파일만 허용한다. */
  extraDocs?: string[];
}

export const AGENT_LABEL = { codex: 'Codex', claude: 'Claude' } as const;

export async function validateExtraDocs(worktree: string, docs: string[]): Promise<string[]> {
  const out: string[] = [];
  for (const d of docs.map((x) => x.trim()).filter(Boolean)) {
    if (d.startsWith('/') || d.split('/').includes('..') || d.includes('\0') || /[*?[\]]/.test(d)) throw new Error(`읽을 문서 경로가 올바르지 않음: ${d}`);
    const r = await G.run('git', ['cat-file', '-e', `HEAD:${d}`], worktree);
    if (r.code !== 0) throw new Error(`시작 HEAD에 없는 문서: ${d}`);
    out.push(d);
  }
  return [...new Set(out)];
}

export async function buildStartPrompt(t: Task, mainAgent: 'codex' | 'claude', o: PromptOptions = {}) {
  const head = await G.revParse(t.worktree, 'HEAD');
  if (!head) throw new Error('worktree HEAD를 읽지 못함');
  const extra = await validateExtraDocs(t.worktree, [...(t.readDocs ?? []), ...(o.extraDocs ?? [])]);
  const c: Ctx = { t, head, extra, main: AGENT_LABEL[mainAgent], impl: AGENT_LABEL[t.agent] };
  return { text: [...identitySections(c), ...scopeSections(c), ...deliverySections(c, o)].join('\n'), head, extraDocs: extra };
}
