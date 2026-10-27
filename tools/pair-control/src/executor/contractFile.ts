// 작업 계약 파일: docs/collaboration/tasks/<task-id>.md 를 작업 브랜치에 커밋하고 그 SHA·해시를 실행 기준으로 쓴다.
// 개인 절대경로(worktree)는 기록하지 않는다. main/통합 checkout에는 커밋하지 않는다.
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import * as G from './git.ts';
import type { CheckSpecT, TaskInputT } from './contract.ts';

export const contractPath = (taskId: string) => `docs/collaboration/tasks/${taskId}.md`;
export const sha256 = (s: string) => crypto.createHash('sha256').update(s).digest('hex');

function checkLine(c: CheckSpecT) {
  return `- \`${c.id}\` ${c.name}: \`${[c.executable, ...c.args].join(' ')}\` (cwd \`${c.cwd}\`)`;
}

export function renderContract(t: TaskInputT): string {
  const machine = {
    task_id: t.taskId, owner: t.agent, branch: t.branch, base_sha: t.baseSha, mode: t.mode, goal: t.goal,
    done_criteria: t.doneCriteria, allowed_files: t.allowedFiles, conflict_groups: t.conflictGroups, env: t.env,
    required_modules: t.requiredModules, checks: t.checks, post_checks: t.postChecks,
    // 값이 있을 때만 넣어, 읽을 문서가 없는 기존 계약의 내용(해시)은 바뀌지 않는다.
    ...(t.readDocs?.length ? { read_docs: t.readDocs } : {}),
  };
  const list = (xs: string[], empty: string) => (xs.length ? xs.map((x) => `- ${x}`).join('\n') : `- ${empty}`);
  return `# 작업 계약: ${t.taskId}

pair-control이 작업 준비 시 작업 브랜치에 커밋한 계약이다. 실행·검사·승인은 이 파일의 커밋 SHA와 내용 해시를 기준으로 한다.
에이전트는 이 파일을 수정하지 않는다(수정하면 Git 계약 검사가 실패한다).

- task_id: \`${t.taskId}\`
- owner: ${t.agent}
- branch: \`${t.branch}\`
- base_sha: \`${t.baseSha}\`
- worktree: 로컬 경로는 커밋하지 않음
- 실행 환경: ${t.env}${t.requiredModules.length ? ` (필요 모듈: ${t.requiredModules.join(', ')})` : ''}

## 목표

${t.goal}

## 완료 조건

${list(t.doneCriteria, '(지정 없음)')}

${t.readDocs?.length ? `## 읽을 문서

${list(t.readDocs.map((f) => `\`${f}\``), '')}

` : ''}## allowed_files

${list(t.allowedFiles.map((f) => `\`${f}\``), '(없음)')}

이 목록 밖 파일은 수정하지 않는다. 데이터·라벨·모델·비밀 설정은 다루지 않는다.

## 작업 테스트 (에이전트 종료 후 실행기가 별도 실행)

${t.checks.length ? t.checks.map(checkLine).join('\n') : '- (지정 없음 — 승인 불가)'}

## 통합 후 검사 (통합 checkout에서 실행)

${t.postChecks.length ? t.postChecks.map(checkLine).join('\n') : '- (지정 없음 — 통합 후 검사 미실행으로 표시)'}

## 상세 지시

${t.prompt.trim() || '(없음)'}

## 금지

학습·모델 비교·사진 추론·라벨 수정·자동 교차 검토·외부 AI 호출·의존성 설치·push를 하지 않는다.

## 기계 판독용

\`\`\`json
${JSON.stringify(machine, null, 2)}
\`\`\`
`;
}

export interface ContractCommit { contractSha: string; contractHash: string; reused: boolean }

/** 계약을 작업 worktree에 쓰고 커밋한다. 같은 내용이 이미 있으면 새 커밋 없이 재사용한다. */
export async function commitContract(worktree: string, t: TaskInputT): Promise<ContractCommit> {
  const rel = contractPath(t.taskId);
  const abs = path.join(worktree, rel);
  const text = renderContract(t);
  const hash = sha256(text);
  if (fs.existsSync(abs)) {
    const current = fs.readFileSync(abs, 'utf8');
    if (sha256(current) !== hash) throw new Error(`이미 다른 내용의 계약이 있음: ${rel} (다른 task ID를 쓰거나 기존 계약을 확인)`);
    const dirty = await G.dirtyFiles(worktree);
    if (dirty.includes(rel)) throw new Error(`계약 파일이 커밋되지 않은 상태: ${rel}`);
    const last = (await G.git(worktree, 'log', '-1', '--format=%H', '--', rel)).stdout.trim();
    if (!G.FULL_SHA.test(last)) throw new Error('기존 계약 커밋을 찾지 못함');
    return { contractSha: last, contractHash: hash, reused: true };
  }
  const dirty = await G.dirtyFiles(worktree);
  if (dirty.length) throw new Error(`worktree에 미커밋 변경이 있어 계약을 커밋하지 않음: ${dirty.slice(0, 5).join(', ')}`);
  const email = (await G.git(worktree, 'config', 'user.email')).stdout.trim();
  if (!email) throw new Error('git user.email 미설정 — 계약 커밋 작성자를 정할 수 없음');
  fs.mkdirSync(path.dirname(abs), { recursive: true });
  fs.writeFileSync(abs, text);
  const add = await G.git(worktree, 'add', '--', rel);
  const commit = add.code === 0 ? await G.git(worktree, 'commit', '-q', '-m', `docs(task): ${t.taskId} 작업 계약`, '--', rel) : add;
  if (commit.code !== 0) {
    fs.rmSync(abs, { force: true });
    await G.git(worktree, 'reset', '-q', '--', rel);
    throw new Error(`계약 커밋 실패: ${commit.stderr.trim()}`);
  }
  const sha = await G.revParse(worktree, 'HEAD');
  return { contractSha: sha!, contractHash: hash, reused: false };
}

/** 특정 커밋에 있는 계약 파일 해시. 없으면 null. */
export async function contractHashAt(worktree: string, taskId: string, sha: string): Promise<string | null> {
  const r = await G.git(worktree, 'show', `${sha}:${contractPath(taskId)}`);
  return r.code === 0 ? sha256(r.stdout) : null;
}
