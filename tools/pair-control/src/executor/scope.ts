// 허용 파일 범위를 사람이 직접 몰라도 정할 수 있게 돕는다. 전달받은 프롬프트의 "허용 파일" 목록을 글자 그대로 옮기고(언어 모델·추측 없음),
// 모르겠을 때를 위한 "코드·테스트·문서" 프리셋을 준다. 어느 쪽도 저장소 전체(./)는 만들지 않는다.
import { isForbidden } from './contract.ts';

export const SCOPE_PRESET = { name: '코드·테스트·문서', files: ['card_condition/', 'tests/', 'tools/experiments/', 'docs/collaboration/'] };

export interface Rejected { path: string; why: string }
export interface Extracted { found: boolean; files: string[]; rejected: Rejected[]; note: string }

const MARK = /(허용\s*파일|허용\s*범위|allowed[_ ]files)/i;
const ITEM = /^\s*(?:[-*+]|\d+[.)])\s+(.*)$/;
const HEADING = /^\s{0,3}#{1,6}\s/;

/** 한 줄에서 경로 후보를 뽑는다: 백틱으로 감싼 토큰, 없으면 목록 항목의 첫 토큰. */
function pathsIn(line: string, listItem: boolean): string[] {
  const ticks = [];
  for (const match of line.matchAll(/`([^`\n]+)`/g)) ticks.push(match[1].trim());
  if (ticks.length) return ticks;
  const m = ITEM.exec(line);
  return listItem && m ? [m[1].trim().split(/\s+/)[0].replace(/[,;:]+$/, '')] : [];
}

/** 표시 이름이 아니라 실제 경로 모양인지와 금지·전체 표기를 거른다. 통과하면 정리된 경로, 아니면 사유. */
function checkPath(raw: string): string | Rejected {
  let p = raw.replace(/^\.\//, '');
  if (raw === '.' || raw === './' || p === '') return { path: raw, why: '저장소 전체 표기는 허용하지 않음' };
  if (p.startsWith('/') || p.startsWith('~') || /^[A-Za-z]:/.test(p)) return { path: raw, why: '상대경로만 허용(절대경로 제외)' };
  if (/[*?[\]\\\0\s]/.test(p) || p.includes('..') || p.includes('//') || p.includes('/./')) return { path: raw, why: 'glob·공백·상위 경로는 허용하지 않음' };
  if (!p.includes('/') && !/\.[A-Za-z0-9]+$/.test(p)) return { path: raw, why: '경로로 보이지 않음(파일 확장자나 폴더 / 가 없음)' };
  if (isForbidden(p)) return { path: raw, why: '금지 경로(데이터·라벨·산출물·비밀 설정은 기본 checkout 단일 담당자 소관)' };
  return p;
}

/** 표식 줄에서 시작해 이어지는 목록을 모은다. 제목이나 목록 밖 문장을 만나면 멈춘다. */
function gather(lines: string[], at: number): string[] {
  const out = [...pathsIn(lines[at].replace(MARK, ''), false)];
  for (const line of lines.slice(at + 1)) {
    if (HEADING.test(line) || (line.trim() && !ITEM.test(line))) break; // 제목이나 목록 밖 문장에서 멈춘다
    if (line.trim()) out.push(...pathsIn(line, true));
  }
  return out;
}

/** 프롬프트 글에서 허용 파일 목록을 찾는다. 첫 표식이 아니라 경로가 하나라도 나오는 첫 표식을 쓴다. */
export function extractScope(text: string): Extracted {
  const lines = String(text ?? '').split('\n');
  const files: string[] = [], rejected: Rejected[] = [];
  for (let i = 0; i < lines.length && !files.length && !rejected.length; i++) {
    if (!MARK.test(lines[i])) continue;
    for (const raw of gather(lines, i).slice(0, 400)) {
      const r = checkPath(raw);
      if (typeof r === 'string') { if (!files.includes(r)) files.push(r); } else rejected.push(r);
    }
  }
  const cap = files.slice(0, 200);
  if (!cap.length) return { found: false, files: cap, rejected, note: '프롬프트에서 쓸 수 있는 "허용 파일" 목록을 찾지 못했습니다.' + (rejected.length ? ` (후보 ${rejected.length}개는 모두 제외됨)` : ' 붙여 넣은 글에 허용 파일 줄과 `경로` 목록이 있는지 확인하거나 프리셋을 쓰세요.') };
  return { found: true, files: cap, rejected, note: `허용 파일 ${cap.length}개를 옮겼습니다.` + (rejected.length ? ` ${rejected.length}개는 제외했습니다.` : '') };
}
