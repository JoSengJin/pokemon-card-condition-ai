
export const AGENTS = ['codex', 'claude'] as const;

export const MODES = ['mock', 'real', 'manual'] as const;

export type Agent = (typeof AGENTS)[number];

export const MOCK_SCENARIOS = ['success', 'fail', 'hang', 'spawn-child', 'touch-forbidden', 'paid-message', 'slow-success', 'edit-contract', 'stream', 'stream-quote', 'stream-api-key', 'stream-error-event'] as const;

export const FORBIDDEN_PREFIXES = ['data/', 'artifacts/', '.backups/', '.venv/', '.git/', 'build/', 'dist/'];

export const FORBIDDEN_FILES = ['development-review.json', 'nemotron-review.json', '.env', 'trusted-experiment.json'];

export const SHARED_CONFIG = ['pyproject.toml', 'requirements-tested.txt', 'AGENTS.md', 'PAIR_CODING.md', 'README.md',
  'development-progress.json', 'PROGRESS_CRITERIA.md', '.gitignore', 'develop', 'experiment', 'review'];

export const DEVELOP_LOCK_PREFIXES = ['card_condition/', 'tools/experiments/'];

export const CHECK_EXECUTABLES = ['git', 'node', '.venv/bin/python'] as const;

export const CHECK_PLACEHOLDERS = ['{base}', '{contract}', '{head}'];

export const ENV_PROFILES = ['none', 'python', 'python-project'] as const;
