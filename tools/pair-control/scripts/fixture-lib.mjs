// 테스트·demo용 합성 Git 저장소. 실제 프로젝트 데이터·라벨은 사용하지 않는다.
// ./develop은 이 저장소의 card_condition/workspace_lock.py 복사본(실제 잠금 코드)을 system python3로 실행한다.
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const git = (cwd, ...args) => execFileSync('git', ['-c', 'user.name=fixture', '-c', 'user.email=fixture@localhost', ...args], { cwd, stdio: 'pipe' }).toString().trim();

export function makeFixture(dir, toolRoot, workers = [['claude', 'task-a'], ['codex', 'task-b'], ['claude', 'task-c'], ['codex', 'task-d']]) {
  fs.rmSync(dir, { recursive: true, force: true });
  const repo = path.join(dir, 'repo');
  fs.mkdirSync(path.join(repo, 'card_condition'), { recursive: true });
  git(repo, 'init', '-q', '-b', 'main');
  // 계약 커밋 작성자(로컬 저장소 설정, worktree 공유)
  execFileSync('git', ['config', 'user.name', 'fixture'], { cwd: repo });
  execFileSync('git', ['config', 'user.email', 'fixture@localhost'], { cwd: repo });
  const lockSrc = path.join(toolRoot, '..', '..', 'card_condition', 'workspace_lock.py');
  fs.copyFileSync(lockSrc, path.join(repo, 'card_condition', 'workspace_lock.py'));
  fs.writeFileSync(path.join(repo, 'card_condition', '__init__.py'), '');
  fs.writeFileSync(path.join(repo, 'develop'), '#!/bin/sh\nset -eu\ntask_root=$(cd "$(dirname "$0")" && pwd)\ncd "$task_root"\nexec "$task_root/.venv/bin/python" -m card_condition.workspace_lock "$@"\n', { mode: 0o755 });
  fs.writeFileSync(path.join(repo, '.gitignore'), 'artifacts/\n__pycache__/\n.venv/\n');
  fs.writeFileSync(path.join(repo, 'README.md'), '# fixture\n');
  for (const d of ['src_a', 'src_b', 'src_c', 'shared']) {
    fs.mkdirSync(path.join(repo, d), { recursive: true });
    fs.writeFileSync(path.join(repo, d, 'file.txt'), `${d}\n`);
  }
  git(repo, 'add', '-A');
  git(repo, 'commit', '-q', '-m', 'fixture base');
  const baseSha = git(repo, 'rev-parse', 'HEAD');
  // 실제 프로젝트처럼 기본(통합) checkout은 자체 .venv를 가진다. worktree에는 만들지 않는다(실행 준비 검사 대상).
  makeVenv(repo);
  // 로컬 bare 원격(합성). 실제 GitHub에는 연결하지 않는다.
  const origin = path.join(dir, 'origin.git');
  execFileSync('git', ['init', '-q', '--bare', '-b', 'main', origin], { stdio: 'pipe' });
  git(repo, 'remote', 'add', 'origin', origin);
  git(repo, 'push', '-q', 'origin', 'main');
  const worktrees = {};
  for (const [agent, name] of workers) {
    const wt = path.join(dir, `wt-${agent}-${name}`);
    git(repo, 'worktree', 'add', '-q', '-b', `${agent}/${name}`, wt, baseSha);
    worktrees[name] = { agent, branch: `${agent}/${name}`, path: fs.realpathSync.native(wt) };
  }
  return { dir, repo: fs.realpathSync.native(repo), origin: fs.realpathSync.native(origin), baseSha, worktrees };
}

export function writeConfig(file, fixture, port = 4111) {
  fs.writeFileSync(file, JSON.stringify({ repo: fixture.repo, integration: { checkout: fixture.repo, branch: 'main' }, port, allowRealModelCalls: false }, null, 2));
}

/** 표준 라이브러리만 있는 자체 가상환경(pip 없음). 사용자가 직접 만드는 단계를 테스트·demo에서 흉내낸다. */
export function makeVenv(checkout) {
  execFileSync('python3', ['-m', 'venv', '--without-pip', path.join(checkout, '.venv')], { stdio: 'pipe' });
}
