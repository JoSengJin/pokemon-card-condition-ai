// 진행률 항목 기반 계약 초안. development-progress.json의 미완료 항목 원문을 인용해 만들며 LLM·추측을 쓰지 않는다.
// 판단이 필요한 값(어느 항목을 할지, 허용 파일을 어디까지 열지)은 사람이 정한다. 증거 파일은 "제안"일 뿐 자동 선택하지 않는다.
// 읽는 곳은 통합 브랜치에 커밋된 파일(git show)이라, 미커밋 편집이나 다른 checkout의 값에 영향받지 않는다.
import * as G from './git.ts';
import { isForbidden } from './contract.ts';
import { UserError, type Executor } from './executor.ts';

export interface ProgressItem {
  id: string; title: string; category: string; weight: number; status: string; earned: number;
  criterion: string; assessment: string; evidence: string[];
}
export interface ProgressSource { file: string; ref: string; sha: string; criterionVersion: string | null; score: number | null; maxScore: number | null }

const FILE = 'development-progress.json';

export async function progressItems(ex: Executor): Promise<{ source: ProgressSource; items: ProgressItem[] }> {
  const cwd = ex.cfg.integration.checkout;
  if (!cwd) throw new UserError('config.integration.checkout 미설정');
  const ref = `refs/heads/${ex.cfg.integration.branch}`;
  const sha = await G.revParse(cwd, ref);
  if (!sha) throw new UserError(`${ex.cfg.integration.branch} 브랜치를 읽지 못함`);
  const r = await G.git(cwd, 'show', `${sha}:${FILE}`);
  if (r.code !== 0) throw new UserError(`${FILE}이(가) 통합 브랜치에 없음 — 진행률 항목으로 초안을 만들 수 없음`);
  let j: any;
  try { j = JSON.parse(r.stdout); } catch { throw new UserError(`${FILE}을(를) 읽지 못함(JSON 오류)`); }
  const items: ProgressItem[] = [];
  for (const c of j.categories ?? []) {
    for (const m of c.milestones ?? []) {
      if (m.status === 'verified') continue; // 완료 항목은 대상이 아님. pending·unknown은 미완료로 본다(점수 규칙: 증거 없는 항목은 0점)
      items.push({
        id: String(m.id), title: String(m.title ?? ''), category: String(c.title ?? c.id ?? ''), weight: Number(m.weight ?? 0), status: String(m.status ?? 'pending'),
        earned: Number(m.earned ?? 0), criterion: String(m.completion_criterion ?? ''), assessment: String(m.assessment ?? ''),
        evidence: Array.isArray(m.evidence) ? m.evidence.map(String) : [],
      });
    }
  }
  return { source: { file: FILE, ref: ex.cfg.integration.branch, sha, criterionVersion: j.criterion_version ?? null, score: j.score ?? null, maxScore: j.max_score ?? null }, items };
}

/**
 * 항목 원문을 인용한 계약 초안. 구현 worktree에서는 학습·성능 평가를 하지 않으므로(PAIR_CODING) 작업을 코드·단위 검증 구현으로
 * 한정하고, 점수·진척률·판정 변경 금지를 상세 지시에 못박는다. 제안 파일은 기준 커밋에 실제 있고 금지 경로가 아닌 증거 파일만이다.
 */
export async function progressDraft(ex: Executor, id: string) {
  const { source, items } = await progressItems(ex);
  const it = items.find((x) => x.id === id);
  if (!it) throw new UserError(`미완료 진행률 항목 없음: ${id}`);
  const cwd = ex.cfg.integration.checkout;
  const suggestedFiles: string[] = [];
  const skippedEvidence: { path: string; why: string }[] = [];
  for (const e of it.evidence) {
    if (isForbidden(e) || e.startsWith('/') || e.includes('..')) { skippedEvidence.push({ path: e, why: '데이터·산출물 경로(허용 불가)' }); continue; }
    const ok = (await G.git(cwd, 'cat-file', '-e', `${source.sha}:${e}`)).code === 0;
    if (!ok) { skippedEvidence.push({ path: e, why: '기준 커밋에 없음' }); continue; }
    if (!suggestedFiles.includes(e)) suggestedFiles.push(e);
  }
  const quote = (s: string) => s.split('\n').map((l) => `> ${l}`).join('\n');
  const prompt = [
    `출처: ${source.file} @ ${source.ref} ${source.sha}${source.criterionVersion ? ` (기준 ${source.criterionVersion})` : ''} — 항목 ${it.id} ${it.title} (${it.category}, 배점 ${it.weight}, 현재 ${it.earned}점)`,
    '', '완료 조건(원문):', quote(it.criterion || '(없음)'), '', '현재 평가(원문):', quote(it.assessment || '(없음)'),
    ...(it.evidence.length ? ['', '기존 증거 파일:', ...it.evidence.map((e) => `- ${e}`)] : []),
    '', '범위 제한:',
    '- 이 작업은 구현 worktree에서 가능한 코드·단위 검증 구현까지다. 학습·모델 비교·사진 추론·성능 수치 평가는 기본 checkout의 단일 담당자가 공통 실행기로 수행한다.',
    '- development-progress.json·PROGRESS_CRITERIA.md의 점수·진척률·배점·판정을 바꾸지 않는다. 위 완료 조건을 달성했다고 주장하지 않는다.',
    '- 사람 정답·라벨·평가 기준을 추정하거나 바꾸지 않는다.',
  ].join('\n');
  return {
    item: it, source,
    draft: { goal: `[${it.id}] ${it.title} — 완료 조건 달성을 위한 구현·단위 검증`, doneCriteria: [`완료 조건 원문과의 간극을 분석하고 구현 가능한 부분을 코드와 단위 검증으로 남긴다(${it.id})`, '성능·점수 판정은 하지 않고 미검증으로 보고한다'], prompt },
    suggestedFiles, skippedEvidence,
  };
}
