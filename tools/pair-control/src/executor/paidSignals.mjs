// 무료 가드 신호 목록. 서버(freeGuard.ts)와 실행기(scripts/start.mjs)가 같은 목록을 쓴다.
/** 존재만으로 구독 대신 API 과금 경로가 열릴 수 있는 환경변수. 값은 읽거나 기록하지 않는다. */
export const PAID_ENV_KEYS = [
  'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_USE_VERTEX',
  'AWS_BEARER_TOKEN_BEDROCK', 'OPENAI_API_KEY', 'CODEX_API_KEY', 'AZURE_OPENAI_API_KEY',
  'GOOGLE_API_KEY', 'GEMINI_API_KEY', 'GOOGLE_GENERATIVE_AI_API_KEY', 'OPENROUTER_API_KEY',
  'MASTRA_CLOUD_ACCESS_TOKEN', 'MASTRA_API_KEY',
];

/** 과금 상태를 뜻하는 billing 구절: "billing is required/not enabled", "billing error/issue/limit", "enable/update/add billing" 등. */
export const BILLING_STATE = /\b(billing (is |has been |was )?(not )?(enabled|set up|required|failed|disabled|error|issue|problem|limit)|(enable|update|add|set up|fix) (your |a )?billing|billing (details|information) (are |is )?(required|missing))\b/i;

/** API 과금이 실제로 시작됐거나 곧 시작될 때 나오는 문구. 서비스를 즉시 종료한다. */
export const PAID_LOG_HARD = [
  /credit balance/i, /insufficient[_ ]quota/i, /payment (required|method)/i, /\$\d+(\.\d+)? (charged|per)/i,
  /api usage (charges|billing)/i, /pay[- ]as[- ]you[- ]go/i, /usage[- ]based (pricing|billing)/i,
  // Claude Code 오류 문서: 사용 크레딧(구독 초과분 과금)이 쓰이고 있거나 필요하다는 뜻이다.
  /hit your monthly spend limit/i, /usage credits required/i,
];
/** 구독 한도 안내문에도 섞여 나올 수 있는 권유성 문구. 한도 도달 문구와 함께 나오면 정지로만 처리한다. */
export const PAID_LOG_SOFT = [
  // "billing" 단독 단어는 코드·지침 문서 예시(billing/close_day.py 등)에도 나와 오탐이 난다. 과금 상태를 뜻하는 구절만 잡는다.
  BILLING_STATE, /extra usage/i, /purchase (more )?credits/i, /add credits to continue/i, /upgrade (to|your) (pro|plus|max|team|plan)/i,
];
export const PAID_LOG_PATTERNS = [...PAID_LOG_HARD, ...PAID_LOG_SOFT];

/** 구독 사용 한도 도달 문구. 과금이 아니라 "정지" 신호다(재시도·크레딧 구매를 시도하지 않는다). */
export const LIMIT_LOG_PATTERNS = [
  /hit your (\w+ )?limit/i, /reached your [\w ]{0,20}limit/i, /usage limit (has been )?(reached|exceeded|hit)/i,
  /(session|weekly|five-hour|5-hour) limit/i, /limit reached/i,
];
// 실제 CLI의 한도 안내 문구는 버전마다 다를 수 있다. 목록에 없는 문구는 일반 실패로 끝나며, 어떤 경우에도 자동 재시도·구매는 하지 않는다.

/** 유료 클라우드/배포로 이어질 수 있어 이 도구가 절대 실행하지 않는 mastra 하위 명령. */
export const FORBIDDEN_MASTRA_COMMANDS = ['deploy', 'server', 'auth', 'factory', 'connect', 'env', 'studio deploy'];
