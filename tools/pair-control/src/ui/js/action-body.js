import { ui } from './core.js';

export function bodyOf(act, t, el) {
  switch (act) {
    case 'handoffauto': return { auto: true };
    case 'prompt': return { unattended: !!ui.keep.pUnattended, extraDocs: String(ui.keep.pDocs || '').split(',').map((x) => x.trim()).filter(Boolean) };
    case 'review': return { mode: 'mock', mockScenario: ui.keep.revScenario || 'approve' };
    case 'approve': return { sha: t.result.headSha };
    case 'mainhandover': case 'mainlimit': return { agent: ui.state.main.agent === 'codex' ? 'claude' : 'codex', reason: document.getElementById('mainReason').value, limit: act === 'mainlimit' };
    case 'mainclear': return { agent: el.dataset.agent };
    case 'apprrevoke': return { id: el.dataset.id };
    case 'apprgrant': {
      const v = (id) => document.getElementById(id).value.split(',').map((x) => x.trim()).filter(Boolean);
      return { basis: document.getElementById('apprBasis').value, actions: v('apprActions'), targets: v('apprTargets').length ? v('apprTargets') : '*' };
    }
    case 'discard': { const reason = prompt('폐기 사유(다른 사람이 볼 수 있게 기록됩니다)'); return reason === null ? null : { reason }; }
    case 'reject': { const reason = prompt('거절 사유'); return reason === null ? null : { reason }; }
    case 'push': return { confirm: String(ui.keep.pushConfirm || '').trim() };
    case 'pushack': return { fingerprints: ui.state.push.plan.findings.filter((f) => f.kind === 'secret_pattern' && !f.acknowledged).map((f) => f.fingerprint) };
    case 'verify': case 'revert': return { id: el.dataset.id };
    case 'archive': return { archived: true };
    case 'unarchive': return { archived: false };
    case 'mainswap': return { agent: el.dataset.to, reason: document.getElementById('mainReason').value };
    default: return {};
  }
}
