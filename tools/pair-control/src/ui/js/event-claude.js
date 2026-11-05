import { clip, toolLine, resultText } from './event-text.js';

export function claudeEvent(o) {
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
