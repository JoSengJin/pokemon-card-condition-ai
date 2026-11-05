import { bullets, contractPaths } from './contract-paths.js';

export const SECTION = { goal: /^목표$/, done: /^완료\s*조건$/, files: /^허용\s*파일$/, docs: /^읽을\s*문서$/, prompt: /^상세\s*지시$/ };

export function parseContractReply(text) {
  const parts = {};
  let key = null;
  for (const line of String(text || '').split('\n')) {
    const h = line.match(/^#{1,3}\s*(.+?)\s*$/);
    const name = h && Object.keys(SECTION).find((k) => SECTION[k].test(h[1].replace(/[`*]/g, '').trim()));
    if (name) { key = name; parts[key] = []; continue; }
    if (key) parts[key].push(line);
  }
  const body = (k) => (parts[k] || []).join('\n').trim();
  const rejected = [];
  // 허용 파일 절의 "금지: …"·"무시 산출물: …" 같은 비목록 줄은 경로가 아니라 지시이므로 상세 지시에 덧붙인다.
  const fileNotes = body('files').split('\n').map((l) => l.trim()).filter((l) => l && !/^([-*]|\d+[.)])\s+/.test(l));
  const out = {
    goal: body('goal').split('\n').map((l) => l.trim()).find(Boolean) || '',
    doneCriteria: bullets(body('done')),
    allowedFiles: contractPaths(body('files'), rejected),
    readDocs: contractPaths(body('docs'), rejected),
    prompt: [body('prompt'), fileNotes.length ? '허용 파일 절의 부가 지시:\n' + fileNotes.join('\n') : ''].filter(Boolean).join('\n\n'),
    rejected,
  };
  const empty = { 목표: !out.goal, '완료 조건': !out.doneCriteria.length, '허용 파일': !out.allowedFiles.length, '상세 지시': !out.prompt };
  out.missing = Object.keys(empty).filter((k) => empty[k]);
  return out;
}
