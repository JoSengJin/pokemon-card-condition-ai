// CLI의 줄 단위 이벤트(JSONL)를 로그 창에 보일 읽기 쉬운 줄로 바꾼다(표시용). 원문 JSON은 로그 파일에 그대로 남는다.
// 모르는 이벤트나 JSON이 아닌 줄은 원문 그대로 보여 준다(잘못 숨기지 않는다). 비용 필드는 보여 주지 않는다(도구는 비용 미측정).
const MAX = 300;

export const clip = (s, n = MAX) => { const t = String(s ?? '').replace(/\s+$/, ''); return t.length > n ? t.slice(0, n) + ' …' : t; };

/** 도구 호출 한 줄. Bash는 명령, 파일 도구는 경로. */
function toolLine(name, input) {
  const i = input || {};
  return name === 'Bash' ? '$ ' + clip(i.command) : '[' + name + '] ' + clip(i.file_path || i.path || i.pattern || '', 160);
}

/** 도구 결과 본문(문자열 또는 {text} 블록 목록)을 한 덩어리 글로. */
function resultText(c) {
  return Array.isArray(c) ? c.map((b) => (b && b.text) || '').join('\n') : String(c ?? '');
}

function claudeEvent(o) {
  if (o.type === 'system') return o.subtype === 'init' ? ['[시작] 모델 ' + o.model + ' · 도구 ' + ((o.tools && o.tools.length) || 0) + '개 · 인증 ' + o.apiKeySource] : [];
  if (o.type === 'assistant' || o.type === 'user') {
    const out = o.error ? ['오류: ' + clip(o.error)] : [];
    for (const b of (o.message && o.message.content) || []) {
      if (b.type === 'text' && o.type === 'assistant') out.push(...clip(b.text, 1200).split('\n'));
      else if (b.type === 'tool_use') out.push(toolLine(b.name, b.input));
      else if (b.type === 'tool_result') { const first = clip(resultText(b.content).split('\n').find((l) => l.trim()) || '', 160); if (first || b.is_error) out.push('  → ' + (b.is_error ? '오류: ' : '') + first); }
    }
    return out;
  }
  if (o.type === 'result') return ['[완료] ' + (o.is_error ? '오류로 종료' : '정상 종료') + ' · ' + Math.round((o.duration_ms || 0) / 1000) + '초 · ' + (o.num_turns || 0) + '턴'].concat(o.is_error && o.result ? ['오류: ' + clip(o.result)] : []);
  if (o.type === 'rate_limit_event') return o.rate_limit_info && o.rate_limit_info.status !== 'allowed' ? ['[한도] ' + o.rate_limit_info.status] : [];
  return null;
}

function codexEvent(o) {
  const it = o.item || {};
  if (o.type === 'thread.started') return ['[시작] 스레드 ' + String(o.thread_id || '').slice(0, 8)];
  if (o.type === 'turn.started') return [];
  if (o.type === 'turn.completed') return ['[완료] 정상 종료'];
  if (o.type === 'turn.failed') return ['[완료] 오류로 종료', '오류: ' + clip(o.error && o.error.message)];
  if (o.type === 'error') return ['오류: ' + clip(o.message)];
  if (o.type === 'item.started' && it.type === 'command_execution') return ['$ ' + clip(it.command)];
  if (o.type !== 'item.completed') return o.type === 'item.started' || o.type === 'item.updated' ? [] : null;
  if (it.type === 'agent_message') return clip(it.text, 1200).split('\n');
  if (it.type === 'command_execution') return ['  → 종료 코드 ' + it.exit_code].concat(String(it.aggregated_output || '').split('\n').filter((l) => l.trim()).slice(0, 3).map((l) => '    ' + clip(l, 160)));
  if (it.type === 'file_change') return (it.changes || []).map((c) => '[수정] ' + clip(c.path, 160));
  return it.type === 'reasoning' ? [] : null;
}

/** 로그 한 줄(원문)을 보일 줄들로. [] 이면 그 줄은 숨긴다(진행 알림 등). */
export function fmtLine(raw) {
  if (!raw.startsWith('{')) return [raw];
  let o = null;
  try { o = JSON.parse(raw); } catch { return [raw]; }
  if (!o || typeof o.type !== 'string') return [raw];
  return claudeEvent(o) || codexEvent(o) || [clip(raw)];
}

/**
 * 받은 글에서 끝난 줄만 읽기 쉬운 줄로 바꿔 log.rows에 쌓고(JSON 이벤트는 fmtLine이 변환), 끝나지 않은 조각은 다음 주기까지 보류한다.
 * 줄마다 받은 시각(HH:MM:SS)을 매긴다. 처음 열 때 이미 있던 줄은 실제 출력 시각을 모르므로 비운다. 실행이 끝났으면 남은 조각도 내보낸다.
 */
export function appendLog(log, chunk, firstFetch, live) {
  const data = log.pending + chunk, cut = data.lastIndexOf('\n') + 1;
  const d = new Date(), now = firstFetch ? '' : [d.getHours(), d.getMinutes(), d.getSeconds()].map((n) => String(n).padStart(2, '0')).join(':');
  const raws = data.slice(0, cut).split('\n').slice(0, -1);
  log.pending = data.slice(cut);
  if (!live && log.pending) { raws.push(log.pending); log.pending = ''; }
  for (const raw of raws) for (const s of fmtLine(raw)) log.rows.push({ t: now, s });
  if (log.rows.length > 5000) log.rows.splice(0, log.rows.length - 5000); // 너무 길면 앞쪽 줄부터 버린다
}
