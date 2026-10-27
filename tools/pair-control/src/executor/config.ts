// 로컬 설정. 개인 절대경로는 Git 제외 파일(config.local.json)이나 환경변수로만 받는다.
import fs from 'node:fs';
import path from 'node:path';

export interface PairConfig {
  /** worktree 검증 기준 저장소(기본 checkout) 경로 */
  repo: string;
  /** 통합 대상 checkout과 브랜치. 이 checkout의 ./develop 잠금 안에서만 cherry-pick 한다. */
  integration: { checkout: string; branch: string; remote?: string };
  /** 새 worktree를 만들 상위 폴더. 비우면 repo의 상위 폴더(기존 worktree 관례와 같음). */
  worktreeRoot: string;
  port: number;
  /** 실제 Codex/Claude 모델 요청 허용. 기본 false이며 이번 구현 범위에서는 켜지 않는다. */
  allowRealModelCalls: boolean;
  /** 사용자가 각 CLI가 API 키가 아닌 기존 구독 로그인으로 동작함을 직접 확인했다는 표시. 없으면 실제 시작 거부. */
  confirmedSubscriptionAuth: boolean;
  /** 실제 CLI를 줄 단위 이벤트(JSONL) 출력으로 실행한다(기본 true). 옵션이 --help에서 확인되지 않으면 텍스트 모드로 돌아간다. */
  streamOutput: boolean;
  /** 실제 CLI 실행 파일 경로(선택). 없으면 PATH에서 찾는다. */
  cli: { codex?: string | null; claude?: string | null };
  stateDir: string;
  toolRoot: string;
  /** Claude 설정 검사에 쓰는 홈 폴더. 테스트에서만 바꾼다(기본 os.homedir()). */
  homeDir?: string;
}

export function findToolRoot(start = process.cwd()): string {
  if (process.env.PAIR_CONTROL_ROOT) return path.resolve(process.env.PAIR_CONTROL_ROOT);
  let dir = path.resolve(start);
  for (;;) {
    const pkg = path.join(dir, 'package.json');
    if (fs.existsSync(pkg)) {
      try { if (JSON.parse(fs.readFileSync(pkg, 'utf8')).name === 'pair-control') return dir; } catch { /* keep walking */ }
    }
    const up = path.dirname(dir);
    if (up === dir) throw new Error('pair-control 루트를 찾지 못했습니다. PAIR_CONTROL_ROOT를 설정하세요.');
    dir = up;
  }
}

export function loadConfig(overrides: Partial<PairConfig> = {}): PairConfig {
  const toolRoot = overrides.toolRoot ?? findToolRoot();
  const file = process.env.PAIR_CONTROL_CONFIG ?? path.join(toolRoot, 'config.local.json');
  const raw = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : {};
  const cfg: PairConfig = {
    repo: raw.repo ?? '',
    integration: { checkout: raw.integration?.checkout ?? '', branch: raw.integration?.branch ?? 'main', remote: raw.integration?.remote ?? 'origin' },
    worktreeRoot: raw.worktreeRoot ?? '',
    port: Number(process.env.PAIR_CONTROL_PORT ?? raw.port ?? 4111),
    allowRealModelCalls: raw.allowRealModelCalls === true,
    confirmedSubscriptionAuth: raw.confirmedSubscriptionAuth === true,
    streamOutput: raw.streamOutput !== false,
    cli: { codex: raw.cli?.codex ?? null, claude: raw.cli?.claude ?? null },
    stateDir: process.env.PAIR_CONTROL_STATE_DIR ?? path.join(toolRoot, '.state'),
    toolRoot,
    ...overrides,
  };
  for (const p of [cfg.repo, cfg.integration.checkout, cfg.worktreeRoot]) {
    if (p && !path.isAbsolute(p)) throw new Error('repo/integration.checkout/worktreeRoot는 절대경로여야 합니다.');
  }
  return cfg;
}
