// 실행 준비 검사: worktree가 만들어진 것과 실행할 수 있는 것은 다르다.
// 가상환경 생성·의존성 설치·모델 다운로드는 하지 않고, 필요한 명령을 안내만 한다.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { run } from './git.ts';
import type { TaskInputT } from './contract.ts';
import type { Check } from './executor.ts';

export interface EnvReadiness { needed: 'none' | 'python' | 'python-project'; ready: boolean; checks: Check[]; fixes: string[]; checkedAt: string }

export function neededEnv(t: Pick<TaskInputT, 'env' | 'checks' | 'postChecks'>, usesDevelopLock: boolean): EnvReadiness['needed'] {
  if (t.env === 'python-project') return 'python-project';
  const py = t.env === 'python' || usesDevelopLock || [...t.checks, ...t.postChecks].some((c) => c.executable === '.venv/bin/python');
  return py ? 'python' : 'none';
}

/** checkout 하나의 자체 .venv 검사. 다른 checkout의 가상환경 공유(symlink·prefix 불일치)를 실패로 본다. */
export async function checkVenv(checkout: string, needed: EnvReadiness['needed'], requiredModules: string[] = []): Promise<EnvReadiness> {
  const checks: Check[] = [];
  const fixes: string[] = [];
  const add = (name: string, ok: boolean, detail: string) => checks.push({ name, ok, detail });
  const done = () => ({ needed, ready: checks.every((c) => c.ok), checks, fixes, checkedAt: new Date().toISOString() });
  if (needed === 'none') { add('실행 환경', true, 'Python 불필요(계약 env=none, ./develop 미사용)'); return done(); }

  const venv = path.join(checkout, '.venv');
  const lst = fs.existsSync(venv) ? fs.lstatSync(venv) : null;
  if (!lst) {
    add('자체 .venv', false, '없음');
    fixes.push(`cd ${JSON.stringify(checkout)} && python3 -m venv .venv`);
    if (needed === 'python-project') fixes.push(`.venv/bin/python -m pip install -e .   # 의존성은 requirements-tested.txt 기준으로 사용자가 설치`);
    return done();
  }
  if (lst.isSymbolicLink()) { add('자체 .venv', false, '.venv가 심볼릭 링크 — 다른 checkout과 공유 금지'); fixes.push('링크를 지우고 이 worktree에서 python3 -m venv .venv'); return done(); }
  add('자체 .venv', fs.existsSync(path.join(venv, 'pyvenv.cfg')), fs.existsSync(path.join(venv, 'pyvenv.cfg')) ? '있음' : 'pyvenv.cfg 없음(가상환경 아님)');
  const py = path.join(venv, 'bin', 'python');
  const probe = await run(py, ['-I', '-c', 'import sys,json;print(json.dumps([sys.prefix, sys.version.split()[0]]))'], os.tmpdir(), 15_000);
  if (probe.code !== 0) { add('.venv/bin/python 실행', false, `실행 실패(code ${probe.code})`); fixes.push('가상환경을 다시 만드세요: rm -rf .venv && python3 -m venv .venv (사용자 실행)'); return done(); }
  const [prefix, version] = JSON.parse(probe.stdout.trim());
  const own = fs.realpathSync.native(prefix) === fs.realpathSync.native(venv);
  add('.venv/bin/python 실행', own, own ? `Python ${version}, prefix가 이 worktree의 .venv` : `prefix가 다른 위치: ${prefix}`);
  if (needed === 'python-project') {
    const pkg = path.join(checkout, 'card_condition', '__init__.py');
    if (fs.existsSync(pkg)) {
      // -I: 현재 폴더를 import 경로에 넣지 않으므로 설치된(editable) 경로만 확인된다.
      const r = await run(py, ['-I', '-c', 'import card_condition;print(card_condition.__file__)'], os.tmpdir(), 30_000);
      const file = r.stdout.trim();
      const inside = r.code === 0 && fs.realpathSync.native(file).startsWith(fs.realpathSync.native(checkout) + path.sep);
      add('card_condition import 경로', inside, r.code !== 0 ? 'import 실패 — 프로젝트가 이 .venv에 설치되지 않음' : inside ? '이 worktree를 가리킴' : `다른 checkout을 가리킴: ${file}`);
      if (!inside) fixes.push('.venv/bin/python -m pip install -e .   (사용자 실행, 자동 설치 안 함)');
    }
    for (const m of requiredModules) {
      const r = await run(py, ['-I', '-c', `import importlib.util,sys;sys.exit(0 if importlib.util.find_spec(${JSON.stringify(m)}) else 1)`], os.tmpdir(), 15_000);
      add(`모듈 ${m}`, r.code === 0, r.code === 0 ? '찾음(import 실행은 안 함)' : '없음');
      if (r.code !== 0) fixes.push(`${m} 설치 필요 — requirements-tested.txt 기준으로 사용자가 설치`);
    }
  }
  return done();
}
