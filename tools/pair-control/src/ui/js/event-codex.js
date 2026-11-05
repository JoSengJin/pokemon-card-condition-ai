import { clip } from './event-text.js';

export function codexEvent(o) {
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
