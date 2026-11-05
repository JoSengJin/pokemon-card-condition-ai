import { esc } from './core.js';

export function runInfo(t, ui) {
  const e = t.exec, m = t.mastra;
  const open = ui.keep.infoOpen ? ' open' : '';
  return '<details class="info" data-keep="infoOpen"' + open + '><summary>실행 정보 · 계약</summary><div class="kv small">' +
    '<div>목표</div><div>' + esc(t.goal) + '</div>' +
    '<div>완료 조건</div><div>' + ((t.doneCriteria || []).map(esc).join('<br>') || '<span class="muted">(지정 없음)</span>') + '</div>' +
    '<div>계약 파일</div><div class="mono">' + esc(t.contractPath + ' @ ' + (t.contractSha || '').slice(0, 12)) + '</div>' +
    '<div>Mastra 실행</div><div class="mono">' + esc((t.runId || '—') + (m ? ' · ' + m.status + (m.suspendedStep ? ' @ ' + m.suspendedStep : '') : '')) + '</div>' +
    '<div>실행 ID</div><div class="mono">' + esc(e ? e.execId : '—') + '</div><div>실행 권한</div><div>' + esc(t.permission || '—') + '</div></div></details>';
}
