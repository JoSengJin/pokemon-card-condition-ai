import * as G from './git.ts';

/** 기준 커밋의 추적 파일·폴더 목록(파일 선택 화면용). */
export async function listTracked(repo: string, ref: string) {
  const r = await G.run('git', ['ls-tree', '-r', '-t', '-z', ref], repo);
  const files = new Set<string>(), dirs = new Set<string>();
  for (const entry of r.stdout.split('\0')) {
    const tab = entry.indexOf('\t');
    if (tab < 0) continue;
    const type = entry.slice(0, tab).split(' ')[1];
    const p = entry.slice(tab + 1);
    if (type === 'tree') dirs.add(`${p}/`); else if (type === 'blob') files.add(p);
  }
  return { files, dirs };
}
