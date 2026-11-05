import { clip } from './event-text.js';
import { claudeEvent } from './event-claude.js';
import { codexEvent } from './event-codex.js';

export function fmtLine(raw) {
  if (!raw.startsWith('{')) return [raw];
  let o = null;
  try { o = JSON.parse(raw); } catch { return [raw]; }
  if (!o || typeof o.type !== 'string') return [raw];
  return claudeEvent(o) || codexEvent(o) || [clip(raw)];
}

export function splitLogChunk(log, chunk, firstFetch, live) {
  const data = log.pending + chunk, cut = data.lastIndexOf('\n') + 1;
  const d = new Date(), now = firstFetch ? '' : [d.getHours(), d.getMinutes(), d.getSeconds()].map((n) => String(n).padStart(2, '0')).join(':');
  const raws = data.slice(0, cut).split('\n').slice(0, -1);
  log.pending = data.slice(cut);
  if (!live && log.pending) { raws.push(log.pending); log.pending = ''; }
  return { raws, now };
}

export function appendLogRows(log, lines, now) {
  for (const s of lines) log.rows.push({ t: now, s });
  if (log.rows.length > 5000) log.rows.splice(0, log.rows.length - 5000);
}

export function appendLog(log, chunk, firstFetch, live) {
  const batch = splitLogChunk(log, chunk, firstFetch, live);
  for (const raw of batch.raws) appendLogRows(log, fmtLine(raw), batch.now);
}
