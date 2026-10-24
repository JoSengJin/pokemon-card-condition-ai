// 무료 가드 신호 목록. 서버(freeGuard.ts)와 실행기(scripts/start.mjs)가 같은 목록을 쓴다.
/** 존재만으로 구독 대신 API 과금 경로가 열릴 수 있는 환경변수. 값은 읽거나 기록하지 않는다. */
export const PAID_ENV_KEYS = [
  'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_USE_VERTEX',
  'AWS_BEARER_TOKEN_BEDROCK', 'OPENAI_API_KEY', 'CODEX_API_KEY', 'AZURE_OPENAI_API_KEY',
  'GOOGLE_API_KEY', 'GEMINI_API_KEY', 'GOOGLE_GENERATIVE_AI_API_KEY', 'OPENROUTER_API_KEY',
  'MASTRA_CLOUD_ACCESS_TOKEN', 'MASTRA_API_KEY',
];

/** 실행 로그의 과금·크레딧·업그레이드 신호 문구. */
export const PAID_LOG_PATTERNS = [
  /credit balance/i, /insufficient[_ ]quota/i, /\bbilling\b/i, /usage[- ]based (pricing|billing)/i,
  /pay[- ]as[- ]you[- ]go/i, /extra usage/i, /purchase (more )?credits/i, /upgrade (to|your) (pro|plus|max|team|plan)/i,
  /api usage (charges|billing)/i, /\$\d+(\.\d+)? (charged|per)/i, /payment (required|method)/i,
];

/** 유료 클라우드/배포로 이어질 수 있어 이 도구가 절대 실행하지 않는 mastra 하위 명령. */
export const FORBIDDEN_MASTRA_COMMANDS = ['deploy', 'server', 'auth', 'factory', 'connect', 'env', 'studio deploy'];
