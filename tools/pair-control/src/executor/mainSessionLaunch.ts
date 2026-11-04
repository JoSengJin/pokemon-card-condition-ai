// 저장된 메인 세션 실행을 probe→exec 한 단계씩 진행한다. exec 진입 뒤 재시작은 결과 불명으로 보존하고 재실행하지 않는다.
import { failSession } from './mainHandover.ts';
import type { Executor } from './executor.ts';
import type { MainSession } from './mainTypes.ts';

export async function advanceSessionLaunch(ex: Executor, s: MainSession) {
  if (s.launchLifetime !== ex.lifetime) {
    failSession(ex, s, '서버 재시작 전 메인 실행 단계 진입 — 결과 불명, 재시도하지 않음');
    return;
  }
  try {
    if (s.launchStage === 'probe') {
      await ex.probeMainAgent(s.agent);
      s.launchStage = 'exec'; ex.store.save(); return;
    }
    if (s.launchStage !== 'exec' || !s.bundleDir || !s.launchPrompt) throw new Error('저장된 메인 실행 입력이 없음');
    s.execId = await ex.launchMainProcess({ agent: s.agent, bundleDir: s.bundleDir, prompt: s.launchPrompt, sessionId: s.id });
    delete s.launchStage; delete s.launchLifetime; delete s.bundleDir; delete s.launchPrompt;
    ex.store.save();
  } catch (e) { failSession(ex, s, `새 메인 실행 실패: ${(e as Error).message}`); }
}
