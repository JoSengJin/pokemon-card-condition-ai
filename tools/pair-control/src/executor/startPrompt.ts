// 에이전트 세션에 붙여 넣을 시작 프롬프트. 규칙 기반 조립이며 LLM을 쓰지 않는다.
// 로컬 절대경로는 복사 시점에만 넣고 어떤 파일에도 커밋하지 않는다(PAIR_CODING §2).
import * as G from './git.ts';
import type { Task } from './executor.ts';

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
    const r = await G.git(worktree, 'cat-file', '-e', `HEAD:${d}`);
    if (r.code !== 0) throw new Error(`시작 HEAD에 없는 문서: ${d}`);
    out.push(d);
  }
  return [...new Set(out)];
}

export async function buildStartPrompt(t: Task, mainAgent: 'codex' | 'claude', o: PromptOptions = {}) {
  const head = await G.revParse(t.worktree, 'HEAD');
  if (!head) throw new Error('worktree HEAD를 읽지 못함');
  const extra = await validateExtraDocs(t.worktree, o.extraDocs ?? []);
  const lines: string[] = [];
  const add = (...x: string[]) => lines.push(...x);
  add('작업 위치:', t.worktree, '', `브랜치: ${t.branch}`, `시작 HEAD: ${head}`, `기준 SHA: ${t.baseSha} (계약 커밋 ${t.contractSha})`, '');
  add(`AGENTS.md와 PAIR_CODING.md를 읽고, ${t.contractPath}(작업 계약)${extra.length ? ` 및 ${extra.join(', ')}` : ''}를 따르세요.`,
    '계약 파일은 수정하지 마세요.' + (t.prompt.trim() ? ' 상세 지시는 계약 파일의 "상세 지시" 절에 있습니다.' : ''), '');
  add('목표:', t.goal, '');
  if (t.doneCriteria.length) add('완료 조건:', ...t.doneCriteria.map((c) => `- ${c}`), '');
  add(`허용 파일 ${t.allowedFiles.length}개만 변경하세요:`, ...t.allowedFiles.map((f) => `- ${f}`),
    '이 밖의 파일, 다른 worktree, 기본 checkout, 다른 브랜치는 읽기 전용입니다.');
  if (t.usesDevelopLock) add('card_condition/·tools/experiments/ 파일 수정은 `./develop -- <수정 명령>` 안에서 수행하세요(AGENTS.md). 이 worktree의 자체 `.venv/bin/python`이 필요합니다.');
  add('');
  if (t.checks.length) add('검사 (에이전트 종료 후 실행기가 별도로 실행하며, 미실행·실패는 통과가 아닙니다):', ...t.checks.map((c) => `- ${c.name}: ${[c.executable, ...c.args].join(' ')}`), '');
  add('진행 방식:', '단계별로 커밋하고 다음 단계로 계속 진행하세요. 어떤 항목이 막히면 사유를 기록하고 독립 작업을 이어가세요.');
  if (o.unattended) add('사용자는 자리에 없습니다. 사람 정답을 추정하거나 재요청하지 마세요.');
  add('', '금지: 실제 학습·모델 비교·사진 추론·라벨 수정·외부 AI 호출·자동 교차 검토, 의존성 설치·모델 다운로드, push.', '');
  add(`완료하면 전체 커밋 SHA 순서·검사 결과·미해결·리스크·롤백을 한 번에 인계하세요. main 통합과 push는 ${AGENT_LABEL[mainAgent]}가 담당합니다.`);
  return { text: lines.join('\n'), head, extraDocs: extra };
}
